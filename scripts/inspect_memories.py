#!/usr/bin/env python3
"""Print every agent's memories, for eyeballing (Packet 7).

Complements ``inspect_wall.py``/``inspect_research.py``: this is the private
layer underneath the public Village — what each agent actually remembers,
how important it judged each thing, and whether that memory has ever been
recalled again since. Memories are agent-private by construction (never
cross-agent), so ``--agent`` is the natural way to read this one agent at a
time.

Usage::

    python scripts/inspect_memories.py
    python scripts/inspect_memories.py --agent agent_alien
    python scripts/inspect_memories.py --agent agent_alien --type SEMANTIC
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.memory import Memory  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.domain.enums import MemoryType  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's memories")
    parser.add_argument(
        "--type", default=None, choices=[t.value for t in MemoryType],
        help="only this memory type",
    )
    parser.add_argument(
        "--min-importance", type=float, default=0.0, help="hide memories below this importance"
    )
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(Memory).order_by(Memory.agent_id, Memory.id)
        if args.agent:
            query = query.filter(Memory.agent_id == args.agent)
        if args.type:
            query = query.filter(Memory.memory_type == MemoryType(args.type))
        if args.min_importance:
            query = query.filter(Memory.importance >= args.min_importance)
        rows = query.all()

        if not rows:
            print("\n(no memories match)")
            return 0

        current_agent = None
        for m in rows:
            if m.agent_id != current_agent:
                current_agent = m.agent_id
                print("\n" + "=" * 70)
                print(current_agent)
                print("=" * 70)
            recalled = (
                f"last recalled day {m.last_accessed_sim_day}"
                if m.last_accessed_sim_day is not None else "never recalled again"
            )
            print(
                f"\n  #{m.id} [{m.memory_type.value}] importance={m.importance:.0f} "
                f"confidence={m.confidence:.0f} reinforced={m.reinforcement_count}x "
                f"decay={m.decay_score:.2f}"
            )
            print(f"      created day {m.created_sim_day}, {recalled}")
            print(f"      {m.content}")
            refs = []
            if m.related_agent_ids:
                refs.append(f"agents={m.related_agent_ids}")
            if m.related_research_ids:
                refs.append(f"research={m.related_research_ids}")
            if m.related_rabbit_hole_ids:
                refs.append(f"holes={m.related_rabbit_hole_ids}")
            if m.related_belief_ids:
                refs.append(f"beliefs={m.related_belief_ids}")
            if refs:
                print(f"      {' '.join(refs)}")

        print(f"\n{len(rows)} memories.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
