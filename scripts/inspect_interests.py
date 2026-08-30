#!/usr/bin/env python3
"""Print every agent's interests — founding and emerging — for eyeballing
(Packet 7).

Shows the same table ``INTERESTS:`` in an agent's own context is drawn from,
plus the bookkeeping that never gets rendered into a prompt: origin, when it
last engaged the agent, and whether it has gone dormant.

Usage::

    python scripts/inspect_interests.py
    python scripts/inspect_interests.py --agent agent_alien
    python scripts/inspect_interests.py --emerging-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.agents import AgentInterest  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.domain.enums import InterestOrigin  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's interests")
    parser.add_argument(
        "--emerging-only", action="store_true",
        help="hide founding-roster interests; show only what an agent developed since",
    )
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(AgentInterest).order_by(
            AgentInterest.agent_id, AgentInterest.strength.desc()
        )
        if args.agent:
            query = query.filter(AgentInterest.agent_id == args.agent)
        if args.emerging_only:
            query = query.filter(AgentInterest.origin != InterestOrigin.FOUNDING.value)
        rows = query.all()

        if not rows:
            print("\n(no interests match)")
            return 0

        current_agent = None
        for i in rows:
            if i.agent_id != current_agent:
                current_agent = i.agent_id
                print("\n" + "=" * 70)
                print(current_agent)
                print("=" * 70)
            founding = i.origin == InterestOrigin.FOUNDING.value
            tag = "founding" if founding else "emerging"
            dormant = " DORMANT" if i.dormant else ""
            print(f"\n  [{tag}{dormant}] {i.interest}")
            print(f"      strength={i.strength:.3f}  origin={i.origin}")
            last_engaged = f"day {i.last_engaged_sim_day}" if i.last_engaged_sim_day is not None else "never"
            print(f"      last engaged: {last_engaged}")
            if i.supporting_research_ids:
                print(f"      research: {i.supporting_research_ids}")

        emerging_count = sum(1 for i in rows if i.origin != InterestOrigin.FOUNDING.value)
        print(f"\n{len(rows)} interests ({emerging_count} emerging).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
