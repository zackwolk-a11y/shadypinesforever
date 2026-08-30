#!/usr/bin/env python3
"""Deterministic Packet 8 smoke test: drives the real loop until an organic
dialogue/social-intelligence chain has happened, then asserts it end to end.

    Agent A notices Agent B (a conversation begins for a real, computed reason)
      -> Agent A says something
      -> Agent B responds specifically to what Agent A said (a tagged,
         direct-response conversational move, not an independent monologue
         that merely shares a topic)
      -> the conversation runs several turns
      -> a meaningful moment occurs (a challenge, a connection, an anecdote,
         or a proposal to research something)
      -> the conversation ends and produces at least one persistent
         consequence (a memory)
      -> that consequence is recalled again later, in a genuinely later turn

Every step happens through the real agent-decision loop — scheduler picks an
agent, FixtureLLMProvider.complete() makes that agent's own (character-
biased, weighted-random) decision, orchestrator validation and execution run
exactly as they would for a live model, and app/services/dialogue.py and
app/services/memory.py are the same modules a live model's decisions would
run through. Nothing here scripts what an agent says, hand-writes a
conversation, or sets a memory directly — a fixed seed only makes which
choices happen to occur reproducible, the same discipline as
scripts/smoke_test_cross_pollination.py and
scripts/smoke_test_character_development.py.

Usage::

    python scripts/smoke_test_dialogue.py
    python scripts/smoke_test_dialogue.py --seed other --max-events 4000
    python scripts/smoke_test_dialogue.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_dialogue.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet8-smoke"
#: Observed to complete between ~250 and ~600 events run to run (the exact
#: count varies slightly even at a fixed seed — plausibly a filesystem/WAL
#: timing effect on this throwaway db's exact page layout rather than a
#: divergence in the decisions themselves, since independent deep diffs of
#: full per-event action sequences have shown byte-for-byte identical
#: decisions across separate processes); this ceiling leaves generous
#: margin over that range.
DEFAULT_MAX_EVENTS = 2000

#: A multi-turn conversation, for this test's purposes — the spec's own
#: "conversation lasts multiple turns" — three or more, so at least one
#: exchange happened beyond the opener and a single reply.
MIN_TURNS = 3
#: Mirrors app.services.memory._RECALL_LOG_GAP_DAYS: a genuine gap, not
#: routine re-display, is what "recalled again later" requires.
MIN_RECALL_GAP_DAYS = 2

_RESPONSIVE_MOVES = {"ANSWER", "QUESTION", "CHALLENGE", "CLARIFY", "EXTEND", "CONNECT"}
_SALIENT_MOVES = {"CHALLENGE", "CONNECT", "ANECDOTE", "PROPOSE_RESEARCH"}


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

            if i % 400 == 0:
                print(f"  ... {i} events so far")

            if i % 25 == 0 or i == args.max_events:
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

        print("\nPASS: an organic dialogue chain occurred:")
        print(f"  conversation #{chain['conversation_id']} [{chain['trigger']}]: {chain['reason']}")
        print(f"  subject: {chain['subject']!r}")
        print(f"  turns: {chain['n_turns']}")
        print(f"  direct response: turn {chain['response_turn']} ({chain['response_move']}) "
              f"by {chain['responder']} replying to {chain['original_speaker']}")
        print(f"  salient moment: {chain['salient_move']}")
        print(f"  persistent consequence: memory #{chain['memory_id']} for {chain['memory_agent']} "
              f"(created day {chain['memory_created_day']})")
        print(f"  recalled again: day {chain['recalled_day']} "
              f"(gap {chain['recalled_day'] - chain['memory_created_day']} days)")
        print("\nInspect it directly:")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_conversations.py")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


def _check_chain(session) -> dict:
    """Look for the whole chain in whatever state the database is in now.

    Tries every ended, multi-turn conversation, not just the first —
    same reasoning as the Packet 6/7 smoke tests: the earliest thread is not
    necessarily the one that produced a lasting memory and a later recall.
    Returns the first complete attempt, or the best (most-progressed)
    partial one so a failure report still shows how far things got.
    """
    from app.db.models.conversations import Conversation
    from app.domain.enums import ConversationStatus

    checks: list[tuple[str, bool]] = []
    result: dict = {"complete": False, "checks": checks}

    candidates = (
        session.query(Conversation)
        .filter(Conversation.status == ConversationStatus.ENDED)
        .order_by(Conversation.id)
        .all()
    )
    if not candidates:
        checks.append(("a conversation began for a real reason", False))
        return result

    best = None
    for conversation in candidates:
        attempt = _try_chain_from(session, conversation)
        if attempt["complete"]:
            return attempt
        if best is None or len(attempt["checks"]) > len(best["checks"]):
            best = attempt
    return best


def _try_chain_from(session, conversation) -> dict:
    from app.db.models.conversations import ConversationMessage
    from app.db.models.events import Event
    from app.db.models.memory import Memory
    from app.domain.enums import EventType

    checks: list[tuple[str, bool]] = [("a conversation began for a real reason", True)]
    result = {"complete": False, "checks": checks}

    messages = (
        session.query(ConversationMessage)
        .filter_by(conversation_id=conversation.id)
        .order_by(ConversationMessage.turn_number)
        .all()
    )
    stage_multiturn = len(messages) >= MIN_TURNS
    checks.append((f"the conversation ran {MIN_TURNS}+ turns", stage_multiturn))
    if not stage_multiturn:
        return result

    move_by_message_id = {
        e.entity_id: e.payload.get("move")
        for e in session.query(Event).filter(
            Event.event_type == EventType.CONVERSATION_MESSAGE,
            Event.correlation_id == conversation.correlation_id,
        )
    }

    response_turn = None
    for prev, cur in zip(messages, messages[1:]):
        if cur.agent_id == prev.agent_id:
            continue
        move = move_by_message_id.get(str(cur.id))
        if move in _RESPONSIVE_MOVES:
            response_turn = (cur, prev, move)
            break
    stage_response = response_turn is not None
    checks.append(("a later turn directly responded to a different agent's turn", stage_response))
    if not stage_response:
        return result

    salient_move = next((m for m in move_by_message_id.values() if m in _SALIENT_MOVES), None)
    stage_salient = salient_move is not None
    checks.append(("a meaningful moment occurred (challenge/connection/anecdote/proposal)", stage_salient))
    if not stage_salient:
        return result

    memory = (
        session.query(Memory)
        .filter(Memory.related_conversation_ids.isnot(None))
        .order_by(Memory.id)
        .all()
    )
    memory = next((m for m in memory if conversation.id in (m.related_conversation_ids or [])), None)
    stage_memory = memory is not None
    checks.append(("the conversation produced a persistent memory", stage_memory))
    if not stage_memory:
        return result

    recalled_day = None
    for e in session.query(Event).filter(Event.event_type == EventType.MEMORY_RECALLED):
        if memory.id in e.payload.get("memory_ids", []):
            if memory.created_sim_day is not None and e.sim_day is not None and (
                e.sim_day - memory.created_sim_day
            ) >= MIN_RECALL_GAP_DAYS:
                recalled_day = e.sim_day
                break
    stage_recalled = recalled_day is not None
    checks.append(("that memory was recalled again after a genuine gap", stage_recalled))
    if not stage_recalled:
        return result

    cur, prev, move = response_turn
    result.update(
        complete=True,
        conversation_id=conversation.id,
        trigger=conversation.trigger_type.value,
        reason=conversation.initiating_reason,
        subject=conversation.current_subject,
        n_turns=len(messages),
        response_turn=cur.turn_number,
        response_move=move,
        responder=cur.agent_id,
        original_speaker=prev.agent_id,
        salient_move=salient_move,
        memory_id=memory.id,
        memory_agent=memory.agent_id,
        memory_created_day=memory.created_sim_day,
        recalled_day=recalled_day,
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
