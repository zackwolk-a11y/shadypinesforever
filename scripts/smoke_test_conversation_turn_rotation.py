#!/usr/bin/env python3
"""Deterministic regression test for the conversation turn-rotation fix
(Finding 1, Baseline Run 2 diagnosis): ``app.services.conversations.
next_speaker`` picking the same participant over and over when nobody has
spoken yet.

The tie-break is "whoever has spoken least, breaking ties by participant
order." At the start of every conversation everybody is tied at zero spoken
turns, so the exclusion of "don't repeat the immediately-previous pick" has
to actually engage in that exact state to do anything. Before the fix it was
keyed on who last *spoke* (via ``ConversationMessage``) — which stays
``None`` until somebody actually speaks — so a participant who is picked,
chooses not to speak, and is asked again a moment later was *still* tied for
"fewest spoken" with everyone else and won the same participant-order
tie-break again. Reproduced live: an 8-participant MORNING_GATHERING gave
all three of its turns to the same first-listed agent and closed from their
own silence, without a second participant ever being offered the floor.

The fix keys the exclusion on who was last *offered* the floor (the most
recent AGENT_WOKE event recorded for this conversation) instead of who last
spoke. This test constructs that exact edge case directly — no simulation
randomness, no LLM call — and proves the turn now rotates.

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_conversation_turn_rotation.py
    python scripts/smoke_test_conversation_turn_rotation.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_conversation_turn_rotation.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


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
    from app.db.session import SessionLocal, engine
    from app.domain.enums import ConversationStatus, ConversationTrigger, EventType
    from app.services import conversations as convo
    from sqlalchemy import select

    settings = get_settings()
    checks: list[tuple[str, bool]] = []

    session = SessionLocal()
    try:
        seed_agents.run(session)
        session.commit()

        clock = session.scalars(select(SimulationClock)).one()
        participants = list(session.scalars(select(Agent.agent_id).order_by(Agent.id)))[:4]

        def _offer_turn(agent_id: str) -> None:
            """Record exactly what a real activation records for this
            conversation (an AGENT_WOKE event carrying conversation_id in
            its payload) without recording a spoken ConversationMessage —
            i.e. the agent was given the floor and chose not to speak."""
            session.add(
                Event(
                    event_type=EventType.AGENT_WOKE,
                    agent_id=agent_id,
                    sim_day=clock.current_day,
                    payload={"conversation_id": conversation.id},
                )
            )
            session.commit()

        conversation = Conversation(
            trigger_type=ConversationTrigger.MORNING_GATHERING,
            participant_ids=list(participants),
            status=ConversationStatus.ACTIVE,
            started_sim_day=clock.current_day, started_sim_period=clock.current_period,
        )
        session.add(conversation)
        session.commit()

        # Nobody has spoken yet -> everyone tied at spoken=0 -> the
        # participant-order tie-break picks the first participant.
        first_pick = convo.next_speaker(session, conversation, clock, settings)
        checks.append((
            "next_speaker picks the first-listed participant when nobody has "
            f"spoken yet (picked {first_pick!r}, expected {participants[0]!r})",
            first_pick == participants[0],
        ))

        # They were offered the floor and chose not to speak — exactly the
        # state that broke before the fix (no ConversationMessage recorded).
        _offer_turn(first_pick)

        second_pick = convo.next_speaker(session, conversation, clock, settings)
        checks.append((
            "THE FIX: next_speaker does not repeat the same participant who "
            f"was just offered the floor and stayed silent (first={first_pick!r}, "
            f"second={second_pick!r})",
            second_pick is not None and second_pick != first_pick,
        ))
        checks.append((
            "the second pick is still a real, eligible participant in this "
            f"conversation ({second_pick!r} in {participants})",
            second_pick in participants,
        ))

        # The fix's actual guarantee is "never repeat the immediately-
        # previous pick," not full round-robin fairness across every
        # participant — with everyone still tied at spoken=0, the
        # participant-order tie-break can and does bring an earlier picker
        # back once someone *else* has been the most recent pick (e.g.
        # optimisto, vince, optimisto, vince, ... is an expected, in-scope
        # sequence). What must never happen, proven over a longer run of
        # consecutive silent turns, is any *back-to-back* repeat.
        picks = [first_pick, second_pick]
        for _ in range(4):
            _offer_turn(picks[-1])
            picks.append(convo.next_speaker(session, conversation, clock, settings))
        consecutive_repeat = next(
            ((a, b) for a, b in zip(picks, picks[1:]) if a == b), None
        )
        checks.append((
            f"no back-to-back repeat across a longer run of silent turns (picks: {picks})",
            consecutive_repeat is None,
        ))

        # Sole-survivor escape hatch still works: once every OTHER
        # participant is at today's activation cap, the last eligible
        # participant may be picked again even though they were just
        # offered the floor (otherwise next_speaker would incorrectly
        # return None with a real eligible speaker still in the room).
        last_pick = picks[-1]
        cap = settings.max_daily_agent_activations
        for other in participants:
            if other == last_pick:
                continue
            for _ in range(cap):
                session.add(Event(
                    event_type=EventType.AGENT_ACTED, agent_id=other,
                    sim_day=clock.current_day, payload={},
                ))
            session.commit()
        _offer_turn(last_pick)
        sole_survivor_pick = convo.next_speaker(session, conversation, clock, settings)
        checks.append((
            "sole-survivor escape hatch: the one remaining eligible "
            f"participant ({last_pick!r}) can still be picked again once "
            "everyone else is at the daily activation cap",
            sole_survivor_pick == last_pick,
        ))

        session.close()
        engine.dispose()
    finally:
        pass

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
        print("\nFAIL: conversation turn-rotation regression check failed.")
        return 1
    print(f"\nPASS: next_speaker rotates away from a silent participant instead of repeating them ({len(checks)} checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
