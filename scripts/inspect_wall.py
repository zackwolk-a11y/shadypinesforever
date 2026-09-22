#!/usr/bin/env python3
"""Print the Research Wall, every Rabbit Hole, and every belief, for eyeballing.

Complements ``inspect_research.py`` (the provenance chain within one research
session) with the social layer Packet 6 adds on top of it: what got posted,
what connected to what, which investigations are shared, and how beliefs have
moved.

Usage::

    python scripts/inspect_wall.py
    python scripts/inspect_wall.py --agent agent_dex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.agents import AgentBelief  # noqa: E402
from app.db.models.belief import BeliefBasis  # noqa: E402
from app.db.models.rabbit_holes import RabbitHole, RabbitHoleMember, RabbitHoleResearch  # noqa: E402
from app.db.models.wall import ResearchWallPost  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's posts/holes/beliefs")
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        print("\n" + "=" * 70)
        print("RESEARCH WALL")
        print("=" * 70)
        query = session.query(ResearchWallPost).order_by(ResearchWallPost.id)
        if args.agent:
            query = query.filter(ResearchWallPost.agent_id == args.agent)
        posts = query.all()
        if not posts:
            print("  (nothing posted yet)")
        for p in posts:
            refs = []
            if p.related_research_id:
                refs.append(f"research={p.related_research_id}")
            if p.related_wall_post_id:
                refs.append(f"-> post #{p.related_wall_post_id}")
            if p.related_rabbit_hole_id:
                refs.append(f"hole #{p.related_rabbit_hole_id}")
            print(f"  #{p.id} [{p.post_type.value}] {p.agent_id}: {p.content}")
            if refs:
                print(f"      {' '.join(refs)}")

        print("\n" + "=" * 70)
        print("RABBIT HOLES")
        print("=" * 70)
        holes = session.query(RabbitHole).order_by(RabbitHole.id).all()
        if not holes:
            print("  (none yet)")
        for h in holes:
            members = (
                session.query(RabbitHoleMember)
                .filter_by(rabbit_hole_id=h.id)
                .order_by(RabbitHoleMember.id)
                .all()
            )
            research_links = (
                session.query(RabbitHoleResearch).filter_by(rabbit_hole_id=h.id).all()
            )
            print(
                f"\n  #{h.id} \"{h.title}\"  status={h.status.value}  "
                f"heat={h.activity_level:.0f}  evidence={h.evidence_strength.value}"
            )
            print(f"      originated by {h.originating_agent_id}: {h.description}")
            print(
                "      members: "
                + ", ".join(
                    f"{m.agent_id}{' (left)' if m.left_at else ''}" for m in members
                )
            )
            if research_links:
                print(
                    "      research linked: "
                    + ", ".join(link.research_session_id for link in research_links)
                )

        print("\n" + "=" * 70)
        print("BELIEFS")
        print("=" * 70)
        query = session.query(AgentBelief).order_by(AgentBelief.id)
        if args.agent:
            query = query.filter(AgentBelief.agent_id == args.agent)
        beliefs = query.all()
        if not beliefs:
            print("  (none yet)")
        for b in beliefs:
            basis_rows = (
                session.query(BeliefBasis).filter_by(belief_id=b.id).order_by(BeliefBasis.id).all()
            )
            print(
                f"\n  #{b.id} {b.agent_id}  status={b.status.value}  confidence={b.confidence:.0f}"
            )
            print(f"      {b.statement}")
            for basis in basis_rows:
                print(f"      <- {basis.relation.value} by {basis.basis_type}:{basis.basis_id}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
