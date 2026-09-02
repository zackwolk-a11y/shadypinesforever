#!/usr/bin/env python3
"""Deterministic regression test for the Packet 12 conversation/scheduler
correctness fix: conversation turn-taking (``next_speaker``) and joining a
conversation (``find_joiner``) each granted a real activation exactly like
the scheduler does, but neither consulted ``Settings.
max_daily_agent_activations`` before picking who goes next — only the
scheduler path did. Reproduced directly: one agent reached 9 activations in
a single simulated day against a configured cap of 6, entirely through
conversation rotation, because an agent who is picked but never actually
speaks keeps winning ``next_speaker``'s "fewest spoken turns" tie-break
forever (their spoken count never moves).

Two layers, deliberately different in kind:

1. A direct contract test against constructed edge-case database state (no
   simulation randomness involved) — proves ``next_speaker``/``find_joiner``
   themselves now refuse an already-capped agent, and that ``next_speaker``
   returns ``None`` (never picks nobody eligible) once every participant is
   capped, rather than a lucky fixture run happening to reach the same
   state.
2. An end-to-end real-simulation drive across several fixture days, proving
   the fix holds under real conditions: the day-wide cap is never exceeded
   by *any* activation-granting path, conversations still open, run, and
   close normally, passive behavior remains fully present in the action
   distribution, and the day still terminates deterministically (no
   deadlock, no infinite loop) — together with a direct check that the
   Day 1 activation-budget fix (RECENT_ACTIVATION_PENALTY) is still in
   place.

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_conversation_activation_cap.py
    python scripts/smoke_test_conversation_activation_cap.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_conversation_activation_cap.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

PASSIVE_ACTIONS = {"REST", "OBSERVE", "LISTEN_TO_MUSIC", "DRINK_COFFEE", "DO_NOTHING"}
DAYS_TO_DRIVE = 3
SEEDS = ("cap-fix-a", "cap-fix-b")


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.conversations import Conversation
    from app.db.models.events import Event
    from app.db.models.world import SimulationClock
    from app.domain.enums import ConversationStatus, ConversationTrigger, EventType
    from app.providers.llm import get_llm_provider
    from app.services import conversations as convo
    from app.services import dialogue, scheduler
    from app.services.orchestrator import run_next_event
    from sqlalchemy import select

    settings = get_settings()
    checks: list[tuple[str, bool]] = []
    cap = settings.max_daily_agent_activations

    # ------------------------------------------------------------------
    # 0. The Day 1 activation-budget fix must still be in place — a direct
    #    arithmetic check, unconditional.
    # ------------------------------------------------------------------
    max_positive = max(scheduler.PERIOD_WEIGHT.values()) + scheduler.CURIOSITY_MAX
    checks.append(
        (
            "the Day 1 activation-budget fix is still in place "
            f"(RECENT_ACTIVATION_PENALTY={scheduler.RECENT_ACTIVATION_PENALTY} x {cap - 1} < {max_positive:.1f})",
            scheduler.RECENT_ACTIVATION_PENALTY * (cap - 1) < max_positive,
        )
    )

    session = None
    try:
        # ------------------------------------------------------------------
        # 1. Direct contract test: constructed edge-case state, no
        #    simulation randomness.
        # ------------------------------------------------------------------
        from app.db.session import SessionLocal, engine

        session = SessionLocal()
        seed_agents.run(session)
        session.commit()

        clock = session.scalars(select(SimulationClock)).one()
        agents = list(session.scalars(select(Agent.agent_id).order_by(Agent.id)))
        optimisto, vince, sol = agents[0], agents[1], agents[2]

        def _stamp_activations(agent_id: str, count: int) -> None:
            for _ in range(count):
                session.add(
                    Event(
                        event_type=EventType.AGENT_ACTED, agent_id=agent_id,
                        sim_day=clock.current_day, payload={},
                    )
                )
            session.commit()

        # 1a. next_speaker must refuse a participant already at the cap.
        _stamp_activations(optimisto, cap)
        conversation = Conversation(
            trigger_type=ConversationTrigger.RANDOM_SOCIAL,
            participant_ids=[optimisto, vince, sol],
            status=ConversationStatus.ACTIVE,
            started_sim_day=clock.current_day, started_sim_period=clock.current_period,
        )
        session.add(conversation)
        session.commit()

        picks = {convo.next_speaker(session, conversation, clock, settings) for _ in range(5)}
        checks.append(
            (
                "next_speaker never picks a participant already at the cap "
                f"(picked from {picks}, {optimisto!r} was pre-stamped to {cap})",
                optimisto not in picks and picks <= {vince, sol},
            )
        )

        # 1b. Once *every* participant is at the cap, next_speaker returns
        #     None (so the caller can close the conversation) rather than
        #     picking someone anyway or hanging.
        _stamp_activations(vince, cap)
        _stamp_activations(sol, cap)
        checks.append(
            (
                "next_speaker returns None once every participant is at the cap "
                "(so the caller closes the conversation instead of deadlocking)",
                convo.next_speaker(session, conversation, clock, settings) is None,
            )
        )

        # 1c. find_joiner must equally refuse an already-capped outsider,
        #     even one who would otherwise be the strongest candidate.
        session.delete(conversation)
        session.commit()
        capped_agent = agents[4]
        _stamp_activations(capped_agent, cap)
        # A shared-interest conversation subject, so there IS a real reason
        # to join if not for the cap.
        from app.db.models.agents import AgentInterest

        shared_topic = session.scalars(
            select(AgentInterest.interest).where(AgentInterest.agent_id == capped_agent).limit(1)
        ).first()

        spontaneous = Conversation(
            trigger_type=ConversationTrigger.RANDOM_SOCIAL,
            participant_ids=[agents[5], agents[6]],
            status=ConversationStatus.ACTIVE,
            current_subject=shared_topic or "a shared topic",
            started_sim_day=clock.current_day, started_sim_period=clock.current_period,
        )
        session.add(spontaneous)
        session.commit()
        # Give the capped agent the exact same interest so find_joiner would
        # otherwise clearly favor them.
        for row in session.scalars(select(AgentInterest).where(AgentInterest.agent_id == capped_agent)):
            row.interest = spontaneous.current_subject
        session.commit()

        joiner = dialogue.find_joiner(session, spontaneous, clock, settings, seed="cap-fix-joiner")
        checks.append(
            (
                "find_joiner never returns an already-capped outsider, even one with "
                "a strong real reason to join",
                joiner is None or joiner.agent_id != capped_agent,
            )
        )
        session.close()
        engine.dispose()
    finally:
        pass

    # ------------------------------------------------------------------
    # 2. End-to-end: real simulated days, across a couple of seeds.
    # ------------------------------------------------------------------
    from app.db.session import SessionLocal, engine

    for seed in SEEDS:
        engine.dispose()
        _clean_db()
        from alembic import command as _cmd
        from alembic.config import Config as _Cfg

        _cmd.upgrade(_Cfg(str(REPO_ROOT / "alembic.ini")), "head")

        session = SessionLocal()
        try:
            seed_agents.run(session)
            session.commit()
            provider = get_llm_provider(settings)

            clock = session.scalars(select(SimulationClock)).one()
            start_day = clock.current_day
            action_distribution: dict[str, int] = {}
            conversations_closed_normally = 0

            for _ in range(400 * DAYS_TO_DRIVE):
                outcome = run_next_event(
                    session, settings=settings, provider=provider, seed=seed, auto_advance=True,
                )
                session.commit()
                if outcome.clock_advance:
                    session.refresh(clock)
                    if clock.current_day >= start_day + DAYS_TO_DRIVE:
                        break
                    continue
                if outcome.note:
                    break
                if outcome.acted:
                    for a in outcome.executed or ["(no actions)"]:
                        action_distribution[a] = action_distribution.get(a, 0) + 1

            # Invariant: no agent ever exceeds the cap on any single day,
            # through any activation-granting path.
            from app.db.models.agents import Agent as AgentModel

            all_agents = list(session.scalars(select(AgentModel.agent_id)))
            violation = False
            for day in range(start_day, clock.current_day + 1):
                for agent_id in all_agents:
                    count = session.scalar(
                        select(scheduler.func.count())
                        .select_from(Event)
                        .where(
                            Event.agent_id == agent_id, Event.sim_day == day,
                            Event.event_type.in_(scheduler.ACTIVATION_EVENTS),
                        )
                    ) or 0
                    if count > cap:
                        violation = True
                        print(f"  !!! seed {seed!r}: {agent_id} had {count} activations on day {day} (cap={cap})")
            checks.append((f"seed {seed!r}: no agent ever exceeds the cap on any day", not violation))

            all_conversations = list(session.scalars(select(Conversation)))
            for c in all_conversations:
                if c.status == ConversationStatus.ENDED:
                    conversations_closed_normally += 1
            checks.append(
                (
                    f"seed {seed!r}: conversations still open, run, and close normally "
                    f"({conversations_closed_normally} closed of {len(all_conversations)} created)",
                    conversations_closed_normally > 0,
                )
            )
            checks.append(
                (
                    f"seed {seed!r}: passive actions remain part of the distribution",
                    any(a in PASSIVE_ACTIONS or a == "(no actions)" for a in action_distribution),
                )
            )
            checks.append(
                (
                    f"seed {seed!r}: the simulation still terminates deterministically "
                    f"(reached day {start_day + DAYS_TO_DRIVE}, no infinite loop)",
                    clock.current_day >= start_day + DAYS_TO_DRIVE,
                )
            )
            print(f"[seed {seed!r}] drove to day {clock.current_day}; "
                  f"{conversations_closed_normally}/{len(all_conversations)} conversations closed; "
                  f"action distribution: {action_distribution}")
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
        print("\nFAIL: one or more conversation-activation-cap assertions failed.")
        return 1
    print(f"\nPASS: conversation rotation and joining now respect the daily activation cap ({len(checks)} checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
