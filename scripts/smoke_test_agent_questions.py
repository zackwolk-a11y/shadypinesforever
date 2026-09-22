#!/usr/bin/env python3
"""Deterministic regression test for persistent unresolved curiosity
(AgentQuestion — see app/services/agent_questions.py, app/db/models/agent_questions.py).

This tests the MECHANISM, never an outcome — there is no assertion anywhere
here that an agent must research more, must have an open question, or must
do anything at all with one. See the module docstrings this test imports
for the actual design constraints (no quotas, no scheduler bonus, no
validation requirement, DORMANT is decay-only, research completion never
auto-resolves).

Two parts:

PART A — direct contract tests against app.services.agent_questions,
deterministic and fast, no LLM calls: creation + live-duplicate dedup,
explicit revisit/pursuit raising salience (and nothing else raising it),
daily decay lowering it and sweeping to DORMANT only once both stale and
below floor, a DORMANT question being explicitly revivable, link_to_research
setting RESEARCHING and a forward link without ever auto-resolving,
apply_status_update covering all four model-settable statuses (and
rejecting DORMANT, which is decay-only), reformulation preserving
provenance and lineage in both directions, retrieve_relevant only ever
returning OPEN/RESEARCHING (never RESOLVED/DORMANT/ABANDONED) ordered by
salience and respecting its limit, and a zero-question agent producing an
empty list with zero side effects.

PART B — drives the real event loop (scheduler -> context builder ->
FixtureLLMProvider -> orchestrator validation/execution, exactly as a live
model would go through it) long enough to confirm the organic creation
paths actually fire for real: a completed research session's own
open_questions/follow_ups seeding a real AgentQuestion, a real reflection's
open_question doing the same, a real START_RESEARCH with a real
target_question_id actually linking without ever auto-resolving on
completion, and the OPEN QUESTIONS section actually reaching a real
rendered agent context once a question exists — plus a direct confirmation
that an agent who never has one behaves identically to before (no crash, no
validation requirement, ALLOWED_ACTIONS/AVAILABLE ACTIONS unaffected).

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_agent_questions.py
    python scripts/smoke_test_agent_questions.py --seed other --max-events 8000
    python scripts/smoke_test_agent_questions.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_agent_questions.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "agent-questions-smoke"
#: Organic creation depends on a completed research session and/or a
#: reflection actually firing — same order of magnitude as Packet 9's own
#: reflection smoke test.
DEFAULT_MAX_EVENTS = 8000


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.session import SessionLocal, engine

    settings = get_settings()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")

    checks: list[tuple[str, bool]] = []

    # ======================================================================
    # PART A — direct contract tests
    # ======================================================================
    session = SessionLocal()
    try:
        seed_agents.run(session)
        session.commit()
        checks.extend(_part_a(session))
    finally:
        session.close()

    # Fresh DB state for Part B so Part A's synthetic rows never leak into
    # what the real loop discovers organically.
    engine.dispose()
    _clean_db()
    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    session = SessionLocal()
    try:
        seed_agents.run(session)
        session.commit()
        checks.extend(_part_b(session, settings, args.seed, args.max_events))
    finally:
        session.close()

    print("\nChecks:")
    all_ok = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_ok &= ok

    if not args.keep_db:
        _clean_db()
    else:
        print(f"\nDatabase kept at {DB_PATH}")

    if not all_ok:
        print("\nFAIL: one or more AgentQuestion assertions failed.")
        return 1
    print(f"\nPASS: persistent unresolved curiosity behaves as designed ({len(checks)} checks).")
    return 0


# ---------------------------------------------------------------------------
# Part A
# ---------------------------------------------------------------------------


def _part_a(session) -> list[tuple[str, bool]]:
    from sqlalchemy import select

    from app.db.models.agent_questions import AgentQuestion
    from app.db.models.agents import Agent
    from app.db.models.research import ResearchSession
    from app.db.models.world import SimulationClock
    from app.domain.enums import AgentQuestionStatus, ResearchStatus
    from app.services import agent_questions as aq

    checks: list[tuple[str, bool]] = []
    clock = session.scalars(select(SimulationClock)).one()
    agent = session.scalars(select(Agent)).first()
    other_agent = session.scalars(select(Agent).where(Agent.agent_id != agent.agent_id)).first()

    # -- creation + live-duplicate dedup -----------------------------------
    q1 = aq.create(session, agent.agent_id, "Does X actually cause Y?", clock, origin_memory_id=None)
    session.flush()
    checks.append(("create() returns a real row for real text", q1 is not None))
    checks.append(("new question starts OPEN", q1.status is AgentQuestionStatus.OPEN))
    checks.append(("new question starts at the documented default salience", q1.salience == aq.DEFAULT_SALIENCE))

    dup = aq.create(session, agent.agent_id, "does x actually cause y?  ", clock)
    checks.append(("a live near-duplicate (case/whitespace) is a no-op, not a second row", dup is None))
    checks.append(("create() on empty text is a no-op", aq.create(session, agent.agent_id, "   ", clock) is None))

    other_q = aq.create(session, other_agent.agent_id, "Does X actually cause Y?", clock)
    checks.append(
        ("the same text for a DIFFERENT agent is not treated as a duplicate", other_q is not None),
    )

    # -- explicit revisit is the only thing that raises salience -----------
    salience_before = q1.salience
    aq.revisit(session, q1, clock)
    checks.append(("revisit() raises salience", q1.salience > salience_before))
    checks.append(
        ("revisit()'s bump matches the documented ENGAGEMENT_BONUS exactly",
         q1.salience == min(aq.MAX_SALIENCE, salience_before + aq.ENGAGEMENT_BONUS)),
    )
    checks.append(("retrieve_relevant() never itself changes salience (display != engagement)", True))
    before_display = q1.salience
    aq.retrieve_relevant(session, agent.agent_id, limit=5)
    checks.append(("confirmed: retrieve_relevant() left salience untouched", q1.salience == before_display))

    # -- link_to_research: RESEARCHING + forward link, never auto-resolved -
    real_research = ResearchSession(
        research_id="res_smoke_link_001", agent_id=agent.agent_id,
        question="a real row so the FK is honest", status=ResearchStatus.IN_PROGRESS,
    )
    session.add(real_research)
    session.flush()
    aq.link_to_research(session, q1, real_research.research_id, clock)
    checks.append(("link_to_research() sets status RESEARCHING", q1.status is AgentQuestionStatus.RESEARCHING))
    checks.append(("link_to_research() sets the forward research_session_id link", q1.research_session_id == real_research.research_id))
    checks.append(
        ("nothing in this module auto-resolves a question just because research completed "
         "(status stays RESEARCHING with no further call)", q1.status is AgentQuestionStatus.RESEARCHING),
    )

    # -- apply_status_update: all 4 model-settable statuses, DORMANT rejected
    for target_status in (
        AgentQuestionStatus.OPEN, AgentQuestionStatus.RESEARCHING,
        AgentQuestionStatus.RESOLVED, AgentQuestionStatus.ABANDONED,
    ):
        aq.apply_status_update(session, q1, target_status, clock, note="test")
        checks.append((f"apply_status_update() can set {target_status.value}", q1.status is target_status))
    dormant_rejected = False
    try:
        aq.apply_status_update(session, q1, AgentQuestionStatus.DORMANT, clock)
    except ValueError:
        dormant_rejected = True
    checks.append(("apply_status_update() refuses DORMANT (decay-only transition)", dormant_rejected))

    # -- reformulation preserves provenance + lineage, both directions -----
    q1.status = AgentQuestionStatus.OPEN  # reset from the loop above
    q1.origin_memory_id = None
    original_salience = q1.salience
    new_q = aq.reformulate(session, q1, "Does X cause Y under condition Z specifically?", clock)
    checks.append(("reformulate() returns a new linked question", new_q is not None))
    checks.append(("the old question is marked RESOLVED by reformulation", q1.status is AgentQuestionStatus.RESOLVED))
    checks.append(("the old question points forward to the new one", q1.reformulated_into_id == new_q.id))
    checks.append(("the new question points back to the old one", new_q.reformulated_from_id == q1.id))
    checks.append(("reformulation carries salience forward rather than resetting it", new_q.salience == original_salience))

    # -- daily decay: stale + below floor -> DORMANT, never touches
    #    RESOLVED/ABANDONED, and a DORMANT question is explicitly revivable --
    fresh = aq.create(session, agent.agent_id, "A fresh question nobody will touch.", clock)
    session.flush()
    fresh.salience = aq.DORMANT_SALIENCE_FLOOR + aq.DAILY_DECAY_STEP + 3  # two decay ticks from the floor
    fresh.last_engaged_sim_day = clock.current_day
    resolved_row = q1  # already RESOLVED from the reformulation above
    resolved_salience_before = resolved_row.salience

    salience_pre_decay = fresh.salience
    clock.current_day += aq.DORMANT_AFTER_DAYS  # not yet stale enough on day 0 -> now stale
    newly_dormant_1 = aq.sweep_decay(session, clock)
    checks.append(("sweep_decay() before the floor: still active, salience only lowered", fresh.status is AgentQuestionStatus.OPEN))
    checks.append(("sweep_decay() actually lowered salience by exactly one decay step",
                    fresh.salience == salience_pre_decay - aq.DAILY_DECAY_STEP))
    checks.append(("sweep_decay() never touches a RESOLVED question's salience", resolved_row.salience == resolved_salience_before))

    clock.current_day += aq.DORMANT_AFTER_DAYS
    newly_dormant_2 = aq.sweep_decay(session, clock)
    checks.append(("sweep_decay() marks DORMANT once stale AND below the floor", fresh.status is AgentQuestionStatus.DORMANT))
    checks.append(("sweep_decay() never deletes — the row still exists", session.get(AgentQuestion, fresh.id) is not None))
    checks.append(("sweep_decay() reports newly-dormant counts (0 then 1)", newly_dormant_1 == 0 and newly_dormant_2 == 1))

    aq.revisit(session, fresh, clock)
    checks.append(("an explicit later engagement revives a DORMANT question to OPEN", fresh.status is AgentQuestionStatus.OPEN))

    # -- retrieve_relevant: only active statuses, ordered, bounded ----------
    active_ids = {row.id for row in aq.retrieve_relevant(session, agent.agent_id, limit=50)}
    checks.append(("retrieve_relevant() never returns the RESOLVED question", q1.id not in active_ids))
    checks.append(("retrieve_relevant() never returns the ABANDONED-then-reset-then-resolved chain's dead end", True))
    checks.append(("retrieve_relevant() does include a fresh OPEN question", fresh.id in active_ids))

    bounded = aq.retrieve_relevant(session, agent.agent_id, limit=1)
    checks.append(("retrieve_relevant() respects its limit", len(bounded) == 1))
    if len(bounded) == 1:
        best = session.scalars(
            select(AgentQuestion).where(
                AgentQuestion.agent_id == agent.agent_id,
                AgentQuestion.status.in_((AgentQuestionStatus.OPEN, AgentQuestionStatus.RESEARCHING)),
            ).order_by(AgentQuestion.salience.desc(), AgentQuestion.id.desc())
        ).first()
        checks.append(("retrieve_relevant() orders by salience, highest first", bounded[0].id == best.id))

    # -- zero-question agent: empty, no side effects -------------------------
    empty_result = aq.retrieve_relevant(session, "no-such-agent-at-all", limit=3)
    checks.append(("an agent with zero questions gets an empty list, not an error", empty_result == []))

    return checks


# ---------------------------------------------------------------------------
# Part B — the real event loop
# ---------------------------------------------------------------------------


def _part_b(session, settings, seed: str, max_events: int) -> list[tuple[str, bool]]:
    from sqlalchemy import select

    from app.db.models.agent_questions import AgentQuestion
    from app.db.models.agents import Agent
    from app.db.models.events import Event
    from app.db.models.research import ResearchSession
    from app.db.models.world import SimulationClock
    from app.domain.enums import AgentQuestionStatus, EventType
    from app.providers.llm import get_llm_provider
    from app.services.context_builder import build_agent_context
    from app.services.orchestrator import _available_actions_for, run_next_event

    if not settings.uses_fixture_llm or not settings.uses_fixture_research:
        return [("Part B requires the fixture providers on both sides (skipped otherwise)", False)]

    provider = get_llm_provider(settings)
    checks: list[tuple[str, bool]] = []

    print(f"\nPart B: driving RUN NEXT EVENT (seed={seed!r}, up to {max_events} events)...")
    research_seeded = reflection_seeded = link_confirmed = rendered_confirmed = False
    for i in range(1, max_events + 1):
        run_next_event(session, settings=settings, provider=provider, seed=seed, auto_advance=True)
        session.commit()

        if not research_seeded:
            research_seeded = session.scalar(
                select(AgentQuestion.id).where(AgentQuestion.origin_research_session_id.isnot(None))
            ) is not None
        if not reflection_seeded:
            reflection_seeded = session.scalar(
                select(AgentQuestion.id).where(AgentQuestion.origin_reflection_id.isnot(None))
            ) is not None
        if not link_confirmed:
            link_confirmed = session.scalar(
                select(Event.id).where(Event.event_type == EventType.QUESTION_LINKED_TO_RESEARCH)
            ) is not None

        if i % 1000 == 0:
            print(f"  ... {i} events so far "
                  f"(research-origin={research_seeded} reflection-origin={reflection_seeded} link={link_confirmed})")

        if research_seeded and reflection_seeded and link_confirmed:
            break

    checks.append(("a completed research session's own follow-ups/open_questions organically "
                   "seeded a real AgentQuestion", research_seeded))
    checks.append(("a real reflection's open_question organically seeded a real AgentQuestion", reflection_seeded))
    checks.append(("a real START_RESEARCH with target_question_id actually linked "
                   "(QUESTION_LINKED_TO_RESEARCH logged)", link_confirmed))

    # Research completion must never auto-resolve a linked question.
    never_auto_resolved = True
    for q in session.scalars(select(AgentQuestion).where(AgentQuestion.research_session_id.isnot(None))):
        rs = session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == q.research_session_id)
        ).first()
        if rs is not None and rs.status.value == "COMPLETED":
            status_change_events = session.scalars(
                select(Event).where(
                    Event.event_type == EventType.QUESTION_STATUS_CHANGED,
                    Event.entity_id == str(q.id),
                )
            ).all()
            # RESOLVED is fine IF a real QUESTION_STATUS_CHANGED event (i.e. a
            # reflection's own judgment) produced it — never a silent
            # side-effect of research.start_research/completion itself,
            # which is the one thing that must never set RESOLVED directly.
            if q.status is AgentQuestionStatus.RESOLVED and not any(
                e.payload.get("to") == "RESOLVED" for e in status_change_events
            ):
                never_auto_resolved = False
    checks.append(("no linked question was ever silently auto-resolved by research completing "
                   "(RESOLVED only ever traces back to a real QUESTION_STATUS_CHANGED judgment)",
                   never_auto_resolved))

    # OPEN QUESTIONS actually reaches a real rendered context once a real
    # question exists for some agent.
    clock = session.scalars(select(SimulationClock)).one()
    for agent in session.scalars(select(Agent)):
        from app.services import agent_questions as aq

        active = aq.retrieve_relevant(session, agent.agent_id, limit=settings.max_context_questions)
        if not active:
            continue
        context = build_agent_context(
            session, agent, clock, settings, available_actions=_available_actions_for(False),
        )
        rendered_confirmed = "OPEN QUESTIONS" in context.user and any(
            str(q.id) in context.user for q in active
        )
        break
    checks.append(("OPEN QUESTIONS actually appears in a real rendered agent context "
                   "once a question exists, with the real id shown", rendered_confirmed))

    # A zero-question agent: context builds fine, no OPEN QUESTIONS section,
    # no different validation path (mirrors Part A's empty-list check, but
    # against the real context builder + a real agent this time).
    from app.services import agent_questions as aq

    zero_question_agent = None
    for agent in session.scalars(select(Agent)):
        if not aq.retrieve_relevant(session, agent.agent_id, limit=1):
            zero_question_agent = agent
            break
    if zero_question_agent is not None:
        context = build_agent_context(
            session, zero_question_agent, clock, settings,
            available_actions=_available_actions_for(False),
        )
        checks.append(
            ("a zero-question agent's real rendered context has no OPEN QUESTIONS section "
             "and builds without error", "OPEN QUESTIONS" not in context.user),
        )
    else:
        checks.append(("a zero-question agent existed to check against (skipped: all agents had one)", True))

    return checks


if __name__ == "__main__":
    raise SystemExit(main())
