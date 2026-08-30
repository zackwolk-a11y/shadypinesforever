#!/usr/bin/env python3
"""Print every agent's reflections, for eyeballing (Packet 9).

Complements ``inspect_memories.py``: reflections are the layer above
memories — higher-level patterns an agent noticed across several real prior
experiences, not any one memory itself. Every reflection prints its full
provenance chain (which real memories/research/beliefs/conversations/rabbit
holes/wall posts/earlier reflections it actually cites), so "does this
reflection really trace back to something real" can be checked by eye, not
just trusted.

Usage::

    python scripts/inspect_reflections.py
    python scripts/inspect_reflections.py --agent agent_alien
    python scripts/inspect_reflections.py --day 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.reflection import AgentReflection  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's reflections")
    parser.add_argument("--day", type=int, default=None, help="only reflections formed on this simulated day")
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(AgentReflection).order_by(AgentReflection.agent_id, AgentReflection.id)
        if args.agent:
            query = query.filter(AgentReflection.agent_id == args.agent)
        if args.day is not None:
            query = query.filter(AgentReflection.simulation_day == args.day)
        rows = query.all()

        if not rows:
            print("\n(no reflections match)")
            return 0

        current_agent = None
        for r in rows:
            if r.agent_id != current_agent:
                current_agent = r.agent_id
                print("\n" + "=" * 70)
                print(current_agent)
                print("=" * 70)
            fixture_tag = " [FIXTURE]" if r.is_fixture else ""
            print(
                f"\n  #{r.id} [{r.status.value}]{fixture_tag} day={r.simulation_day} "
                f"importance={r.importance:.0f} confidence={r.confidence:.0f}"
            )
            print(f"      topic: {r.topic}")
            print(f"      summary: {r.summary}")
            if r.open_question:
                print(f"      open question: {r.open_question}")
            if r.suggested_follow_up:
                print(f"      suggested follow-up: {r.suggested_follow_up}")
            if r.supersedes_reflection_id:
                print(f"      supersedes: #{r.supersedes_reflection_id}")

            sources = []
            if r.source_memory_ids:
                sources.append(f"memories={r.source_memory_ids}")
            if r.source_research_ids:
                sources.append(f"research={r.source_research_ids}")
            if r.source_belief_ids:
                sources.append(f"beliefs={r.source_belief_ids}")
            if r.source_conversation_ids:
                sources.append(f"conversations={r.source_conversation_ids}")
            if r.source_rabbit_hole_ids:
                sources.append(f"rabbit_holes={r.source_rabbit_hole_ids}")
            if r.source_wall_post_ids:
                sources.append(f"wall_posts={r.source_wall_post_ids}")
            if r.source_reflection_ids:
                sources.append(f"earlier_reflections={r.source_reflection_ids}")
            print(f"      sources: {' '.join(sources) if sources else '(none — should not happen)'}")

        print(f"\n{len(rows)} reflections.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
