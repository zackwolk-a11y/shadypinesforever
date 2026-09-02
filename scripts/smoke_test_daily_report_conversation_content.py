#!/usr/bin/env python3
"""Deterministic regression test for the Packet 12 daily-synthesis retrieval
bug: the Founder Report's conversation facts were built from conversation
*metadata* alone (participants, trigger type, ``current_subject``, closing
reason) — ``app/services/daily_synthesis.py``'s ``gather_facts`` never
queried ``ConversationMessage`` rows at all, so a conversation with a full,
real, multi-turn transcript on record could only ever be described as
"unspecified" in the report, however much was actually said.

Confirmed live: the Day 2 Founder Report called an extended Optimisto/Lucid
conversation "unspecified in the record" while the Fishbowl's own
conversation detail page showed the complete real transcript for the same
conversation — the report was working from less data than the database
actually held, not summarizing what it saw.

This drives the real event loop under the fixture provider (deterministic
seed, proven in scripts/smoke_test_dialogue.py to produce real spoken
turns) until a conversation with at least one real ``ConversationMessage``
actually closes, then calls ``gather_facts`` directly — the same function
``daily_synthesis.generate_report`` calls at every real day boundary — and
asserts its conversation FactItem actually quotes real, spoken content
rather than falling back to "unspecified". Also asserts the honest
fallback (a conversation where nobody actually spoke) is never confused
with a retrieval failure, and that the excerpt stays bounded rather than
dumping an unbounded transcript.

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_daily_report_conversation_content.py
    python scripts/smoke_test_daily_report_conversation_content.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_daily_report_conversation_content.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet8-smoke"  # proven to produce real spoken conversation turns
DEFAULT_MAX_EVENTS = 4000


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
    from app.db.models.conversations import Conversation, ConversationMessage
    from app.db.models.events import Event
    from app.db.session import SessionLocal
    from app.domain.enums import EventType
    from app.providers.llm import get_llm_provider
    from app.services import daily_synthesis
    from app.services.orchestrator import run_next_event
    from sqlalchemy import select

    settings = get_settings()
    checks: list[tuple[str, bool]] = []

    session = SessionLocal()
    try:
        seed_agents.run(session)
        session.commit()
        provider = get_llm_provider(settings)

        print(f"Driving RUN NEXT EVENT (seed={args.seed!r}, up to {args.max_events} events) "
              f"until a conversation with real spoken turns closes...")

        target_conversation_id: int | None = None
        target_day: int | None = None
        spoken_excerpt: str | None = None

        for i in range(1, args.max_events + 1):
            run_next_event(session, settings=settings, provider=provider, seed=args.seed, auto_advance=True)
            session.commit()

            # Look for a just-closed conversation that actually has real turns.
            for ended_event in session.scalars(
                select(Event).where(Event.event_type == EventType.CONVERSATION_ENDED)
            ):
                cid = int(ended_event.payload.get("conversation_id"))
                if target_conversation_id is not None:
                    continue
                messages = list(
                    session.scalars(
                        select(ConversationMessage).where(ConversationMessage.conversation_id == cid)
                    )
                )
                if not messages:
                    continue
                conversation = session.get(Conversation, cid)
                target_conversation_id = cid
                target_day = ended_event.sim_day
                spoken_excerpt = messages[0].content[:40]
                print(f"  [{i}] conversation #{cid} closed on day {target_day} with "
                      f"{len(messages)} real turn(s); first: {messages[0].agent_id!r} said "
                      f"{spoken_excerpt!r}")
            if target_conversation_id is not None:
                break
        else:
            print(f"\nFAIL: no conversation with real spoken turns closed within "
                  f"{args.max_events} events. Try a different --seed.")
            return 1

        # ------------------------------------------------------------------
        # The actual check: gather_facts (what generate_report calls at every
        # real day boundary) must surface the real transcript, not just
        # metadata.
        # ------------------------------------------------------------------
        facts = daily_synthesis.gather_facts(session, target_day, settings)
        matching = [f for f in facts.conversations if f.ref_id == str(target_conversation_id)]

        checks.append(("the target conversation appears in gather_facts' conversation facts", len(matching) == 1))
        if matching:
            fact_text = matching[0].text
            print(f"\n  gather_facts conversation FactItem text:\n    {fact_text!r}")
            checks.append(
                ("the fact text is not just the bare 'unspecified' fallback", "unspecified" not in fact_text),
            )
            checks.append(
                (
                    "the fact text actually quotes real spoken content from the conversation",
                    any(msg_content[:40] in fact_text for msg_content in (spoken_excerpt,)),
                ),
            )
            checks.append(("the excerpt stays bounded, not an unbounded transcript dump", len(fact_text) <= 500))

        # ------------------------------------------------------------------
        # The honest-fallback case: a conversation where nobody spoke must
        # never be confused with a retrieval failure — it says so plainly,
        # and this fix must not fabricate content for it.
        # ------------------------------------------------------------------
        all_ended_events = list(
            session.scalars(select(Event).where(Event.event_type == EventType.CONVERSATION_ENDED))
        )
        silent = next(
            (
                e for e in all_ended_events
                if not session.scalars(
                    select(ConversationMessage.id).where(
                        ConversationMessage.conversation_id == int(e.payload.get("conversation_id"))
                    )
                ).first()
            ),
            None,
        )
        if silent is not None:
            silent_id = int(silent.payload.get("conversation_id"))
            silent_facts = daily_synthesis.gather_facts(session, silent.sim_day, settings)
            silent_matching = [f for f in silent_facts.conversations if f.ref_id == str(silent_id)]
            if silent_matching:
                checks.append(
                    (
                        "a conversation where nobody actually spoke is honestly labelled, "
                        "not fabricated content",
                        "no one actually spoke" in silent_matching[0].text,
                    ),
                )

        print("\nChecks:")
        all_ok = True
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
            all_ok &= ok

        if not all_ok:
            print("\nFAIL: one or more daily-synthesis conversation-content assertions failed.")
            return 1
        print(f"\nPASS: the Founder Report's conversation facts now carry real transcript content ({len(checks)} checks).")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())
