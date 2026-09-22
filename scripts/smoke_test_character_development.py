#!/usr/bin/env python3
"""Deterministic Packet 7 smoke test: drives the real loop until an organic
character-development chain has happened, then asserts it end to end.

    Agent A completes research
      -> a meaningful SEMANTIC memory is created for A
      -> (elsewhere) an agent B is drawn into a topic through repeated
         exposure — joining a rabbit hole, reading the wall, researching —
         and a genuinely new interest is created for B
      -> several simulated days pass with repeated engagement
      -> that interest strengthens (INTEREST_INCREASED), not from one
         conversation but from real repetition
      -> A's earlier memory is recalled again after a genuine gap
         (MEMORY_RECALLED) rather than staying merely "recently created"
      -> B's later behavior actually cites the now-stronger interest as the
         topic of a real action — the interest changed what B did, not just
         what B is nominally curious about

Every step happens through the real agent-decision loop, exactly the way
scripts/smoke_test_cross_pollination.py already exercises Packet 6: the
scheduler picks an agent, FixtureLLMProvider.complete() makes that agent's
own weighted-random decision from what it can actually see in context,
orchestrator validation and execution run unchanged, and app/services/memory.py
and app/services/interests.py are the same modules a live model's decisions
would run through. Nothing here scripts an agent's choice, hand-writes a
memory, or sets an interest's strength directly — a fixed seed only makes
which choices happen to occur reproducible.

This chain needs more independent things to line up than Packet 6's did
(memory creation and recall, interest creation and reinforcement, and a later
action that visibly cites the result), so it takes a few thousand events
rather than a few hundred. Still fast: fixture calls are pure computation.

Usage::

    python scripts/smoke_test_character_development.py
    python scripts/smoke_test_character_development.py --seed other --max-events 6000
    python scripts/smoke_test_character_development.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_character_development.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet7-smoke"
DEFAULT_MAX_EVENTS = 6000

#: An interest strengthening on the very next event after it was created is
#: not "repeated engagement over time" — require a real simulated-day gap
#: before INTEREST_INCREASED counts toward the chain.
MIN_DAYS_BETWEEN_CREATE_AND_STRENGTHEN = 1
#: Mirrors app.services.memory._RECALL_LOG_GAP_DAYS: only a genuine gap
#: counts as "old memory is retrieved" rather than routine re-display.
MIN_RECALL_GAP_DAYS = 2


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
    parser.add_argument("--verbose", action="store_true", help="print every event")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event

    settings = get_settings()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")
    if not settings.uses_fixture_llm or not settings.uses_fixture_research:
        print("This smoke test requires the fixture providers on both sides.")
        return 1

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.\n")

        provider = get_llm_provider(settings)

        print(f"Driving RUN NEXT EVENT (seed={args.seed!r}, up to {args.max_events} events)...")
        for i in range(1, args.max_events + 1):
            outcome = run_next_event(
                session, settings=settings, provider=provider,
                seed=args.seed, auto_advance=True,
            )
            session.commit()
            if args.verbose and outcome.decision is not None:
                print(f"  [{i}] {outcome.activated_agent_id}: {outcome.decision.summary}")

            if i % 500 == 0:
                print(f"  ... {i} events so far")

            if i % 50 == 0 or i == args.max_events:
                chain = _check_chain(session)
                if chain["complete"]:
                    print(f"\nFull chain complete after {i} events.")
                    break
        else:
            chain = _check_chain(session)

        print("\nChain checkpoints:")
        for label, ok in chain["checks"]:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

        if not chain["complete"]:
            print(
                f"\nFAIL: the full chain did not complete within {args.max_events} events. "
                "Try a higher --max-events or a different --seed."
            )
            return 1

        print("\nPASS: an organic character-development chain occurred:")
        print(f"  research memory : #{chain['memory_id']} for {chain['memory_agent']} "
              f"(created day {chain['memory_created_day']})")
        print(f"  memory recalled : day {chain['memory_recalled_day']} "
              f"(gap {chain['memory_recalled_day'] - chain['memory_created_day']} days)")
        print(f"  emerging interest: {chain['interest_agent']} developed "
              f"\"{chain['interest_text']}\" (origin: {chain['interest_origin']})")
        print(f"  strengthened    : day {chain['interest_created_day']} "
              f"-> day {chain['interest_strengthened_day']} "
              f"(strength now {chain['interest_strength']:.3f})")
        print(f"  behavior reflects it: {chain['interest_agent']} on day {chain['acted_day']}: "
              f"\"{chain['acted_summary']}\"")
        print("\nInspect it directly:")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_memories.py")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_interests.py --emerging-only")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


def _check_chain(session) -> dict:
    """Look for the whole chain in whatever state the database is in now.

    Two independent halves, checked separately and reported together: the
    memory half (a memory created, then genuinely recalled later) and the
    interest half (a new interest created, then strengthened, then visibly
    cited in a later action). Nothing requires them to involve the same
    agent — the spec's own chain treats "Agent A" and "an agent" as distinct
    roles, and requiring one specific agent to satisfy both halves would test
    a coincidence, not the mechanism.
    """
    checks: list[tuple[str, bool]] = []
    result: dict = {"complete": False, "checks": checks}

    memory_half = _find_memory_half(session)
    checks.append(("a meaningful event created a memory", memory_half is not None))
    if memory_half is None:
        return result
    checks.append(
        ("that memory was later recalled after a genuine gap", memory_half["recalled"])
    )

    interest_half = _find_interest_half(session)
    checks.append(
        ("a previously-absent topic became a new emerging interest", interest_half is not None)
    )
    if interest_half is None:
        return result
    checks.append(
        ("that interest strengthened through repeated engagement, not one event", interest_half["strengthened"])
    )
    checks.append(
        ("later behavior cited that evolved interest as its topic", interest_half["acted"])
    )

    result["complete"] = memory_half["recalled"] and interest_half["strengthened"] and interest_half["acted"]
    if result["complete"]:
        result.update(
            memory_id=memory_half["memory_id"],
            memory_agent=memory_half["agent_id"],
            memory_created_day=memory_half["created_day"],
            memory_recalled_day=memory_half["recalled_day"],
            interest_agent=interest_half["agent_id"],
            interest_text=interest_half["interest_text"],
            interest_origin=interest_half["origin"],
            interest_created_day=interest_half["created_day"],
            interest_strengthened_day=interest_half["strengthened_day"],
            interest_strength=interest_half["strength"],
            acted_day=interest_half["acted_day"],
            acted_summary=interest_half["acted_summary"],
        )
    return result


def _find_memory_half(session) -> dict | None:
    from app.db.models.events import Event
    from app.domain.enums import EventType

    created_events = session.query(Event).filter(
        Event.event_type == EventType.MEMORY_CREATED
    ).order_by(Event.id).all()
    if not created_events:
        return None

    recalled_by_memory: dict[int, int] = {}  # memory_id -> earliest recalled sim_day
    for event in session.query(Event).filter(Event.event_type == EventType.MEMORY_RECALLED):
        for memory_id in event.payload.get("memory_ids", []):
            if memory_id not in recalled_by_memory or event.sim_day < recalled_by_memory[memory_id]:
                recalled_by_memory[memory_id] = event.sim_day

    best = None
    for event in created_events:
        memory_id = event.payload.get("memory_id")
        created_day = event.sim_day
        recalled_day = recalled_by_memory.get(memory_id)
        gap_ok = (
            recalled_day is not None and created_day is not None
            and (recalled_day - created_day) >= MIN_RECALL_GAP_DAYS
        )
        candidate = {
            "memory_id": memory_id,
            "agent_id": event.agent_id,
            "created_day": created_day,
            "recalled_day": recalled_day,
            "recalled": gap_ok,
        }
        if gap_ok:
            return candidate
        if best is None:
            best = candidate
    return best


def _find_interest_half(session) -> dict | None:
    from app.db.models.events import Event
    from app.domain.enums import EventType

    created_events = session.query(Event).filter(
        Event.event_type == EventType.INTEREST_CREATED
    ).order_by(Event.id).all()
    if not created_events:
        return None

    increased = list(
        session.query(Event).filter(Event.event_type == EventType.INTEREST_INCREASED).order_by(Event.id)
    )
    acted = list(
        session.query(Event).filter(Event.event_type == EventType.AGENT_ACTED).order_by(Event.id)
    )

    best = None
    for created in created_events:
        agent_id = created.agent_id
        interest_text = created.payload.get("interest", "")
        created_day = created.sim_day

        strengthen_day = None
        strengthen_id = None
        for inc in increased:
            if inc.agent_id != agent_id or inc.payload.get("interest") != interest_text:
                continue
            if inc.id <= created.id:
                continue
            if created_day is not None and inc.sim_day is not None and (
                inc.sim_day - created_day
            ) >= MIN_DAYS_BETWEEN_CREATE_AND_STRENGTHEN:
                strengthen_day = inc.sim_day
                strengthen_id = inc.id
                break

        # The cited action must follow the strengthening, not just the
        # interest's creation — "later behavior reflects that evolved
        # interest" means behavior *after* it evolved, not merely after it
        # first appeared.
        acted_day = None
        acted_summary = None
        needle = interest_text.strip().lower()
        if strengthen_id is not None:
            for act in acted:
                if act.agent_id != agent_id or act.id <= strengthen_id:
                    continue
                summary = (act.payload.get("summary") or "").lower()
                if needle and needle in summary:
                    acted_day = act.sim_day
                    acted_summary = act.payload.get("summary")
                    break

        candidate = {
            "agent_id": agent_id,
            "interest_text": interest_text,
            "origin": created.payload.get("origin"),
            "created_day": created_day,
            "strengthened_day": strengthen_day,
            "strengthened": strengthen_day is not None,
            "strength": created.payload.get("strength", 0.0),
            "acted_day": acted_day,
            "acted_summary": acted_summary,
            "acted": acted_day is not None,
        }
        if strengthen_day is not None:
            candidate["strength"] = max(
                inc.payload.get("strength", candidate["strength"])
                for inc in increased
                if inc.agent_id == agent_id and inc.payload.get("interest") == interest_text
            )
        if candidate["strengthened"] and candidate["acted"]:
            return candidate
        if best is None or (
            candidate["strengthened"] and not best["strengthened"]
        ) or (
            candidate["strengthened"] == best["strengthened"] and candidate["acted"] and not best["acted"]
        ):
            best = candidate
    return best


if __name__ == "__main__":
    raise SystemExit(main())
