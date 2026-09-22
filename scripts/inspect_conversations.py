#!/usr/bin/env python3
"""Print every conversation, for eyeballing whether they're actually
interesting (Packet 8).

Complements ``inspect_wall.py``/``inspect_memories.py``: this is the social
layer itself — who talked to whom, why, what was actually said, and what it
produced (memories, relationship movement, and any connection back to
research/the wall/a rabbit hole).

Usage::

    python scripts/inspect_conversations.py
    python scripts/inspect_conversations.py --agent agent_dex
    python scripts/inspect_conversations.py --id 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.conversations import Conversation, ConversationMessage  # noqa: E402
from app.db.models.memory import Memory  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only conversations this agent was in")
    parser.add_argument("--id", type=int, default=None, help="only this conversation")
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(Conversation).order_by(Conversation.id)
        if args.id is not None:
            query = query.filter(Conversation.id == args.id)
        conversations = query.all()
        if args.agent:
            conversations = [
                c for c in conversations
                if args.agent in (c.participant_ids or []) or args.agent in (c.departed_agent_ids or [])
            ]

        if not conversations:
            print("\n(no conversations match)")
            return 0

        for c in conversations:
            everyone = list(dict.fromkeys([*(c.participant_ids or []), *(c.departed_agent_ids or [])]))
            print("\n" + "=" * 70)
            print(
                f"#{c.id} [{c.trigger_type.value}] {c.status.value}  "
                f"day {c.started_sim_day} {c.started_sim_period or ''}  location={c.location or '?'}"
            )
            print("=" * 70)
            print(f"  participants: {', '.join(everyone)}")
            if c.initiating_reason:
                print(f"  why it started: {c.initiating_reason}")
            if c.current_subject:
                print(f"  subject: {c.current_subject}")
            if c.ending_reason:
                print(f"  why it ended: {c.ending_reason}")
            refs = []
            if c.related_research_ids:
                refs.append(f"research={c.related_research_ids}")
            if c.related_wall_post_ids:
                refs.append(f"wall_posts={c.related_wall_post_ids}")
            if c.related_rabbit_hole_ids:
                refs.append(f"rabbit_holes={c.related_rabbit_hole_ids}")
            if c.related_memory_ids:
                refs.append(f"memories_that_prompted_it={c.related_memory_ids}")
            if refs:
                print(f"  connects to: {' '.join(refs)}")

            messages = (
                session.query(ConversationMessage)
                .filter_by(conversation_id=c.id)
                .order_by(ConversationMessage.turn_number)
                .all()
            )
            if messages:
                print("  transcript:")
                for m in messages:
                    print(f"    {m.turn_number}. {m.agent_id}: {m.content}")
            else:
                print("  (nothing was said)")

            produced = (
                session.query(Memory)
                .filter(Memory.related_conversation_ids.isnot(None))
                .all()
            )
            produced = [m for m in produced if c.id in (m.related_conversation_ids or [])]
            if produced:
                print("  memories this produced:")
                for m in produced:
                    print(f"    - [{m.agent_id}] [{m.memory_type.value}] {m.content}")

        print(f"\n{len(conversations)} conversation(s).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
