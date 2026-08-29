#!/usr/bin/env python3
"""Print every research session's full provenance chain, for eyeballing.

For each session: the question, its status, every source, every passage (with
its sha256), every finding, every atomic claim, and which passages each claim
cites — the whole spine from "what was searched" to "what was concluded".

Usage::

    python scripts/inspect_research.py                 # every session
    python scripts/inspect_research.py --agent agent_dex
    python scripts/inspect_research.py --failed-only    # RESEARCH_UNAVAILABLE only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.research import ResearchFinding, ResearchQuery, ResearchSession, ResearchSource  # noqa: E402
from app.db.models.research_provenance import Claim, ClaimEvidence, ResearchSourcePassage  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's sessions")
    parser.add_argument(
        "--failed-only", action="store_true", help="only RESEARCH_UNAVAILABLE sessions"
    )
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(ResearchSession).order_by(ResearchSession.id)
        if args.agent:
            query = query.filter(ResearchSession.agent_id == args.agent)
        sessions = query.all()
        if args.failed_only:
            sessions = [s for s in sessions if s.status.value == "FAILED"]

        if not sessions:
            print("No research sessions match.")
            return 0

        for rs in sessions:
            tag = "FIXTURE" if rs.is_fixture else "LIVE"
            print(f"\n{'=' * 70}")
            print(f"{rs.research_id}  [{tag}]  agent={rs.agent_id}  status={rs.status.value}")
            print(f"  question: {rs.question}")
            if rs.status.value == "FAILED":
                print(f"  {rs.interpretation}")
                continue

            print(
                f"  evidence_strength={rs.evidence_strength.value}  confidence={rs.confidence}"
            )
            print(f"  interpretation: {rs.interpretation}")

            queries = (
                session.query(ResearchQuery)
                .filter_by(research_session_id=rs.research_id)
                .all()
            )
            for q in queries:
                print(f"\n  QUERY #{q.id}: {q.query_text!r}")

            sources = (
                session.query(ResearchSource)
                .filter_by(research_session_id=rs.research_id)
                .all()
            )
            passages_by_source = {}
            for p in session.query(ResearchSourcePassage).all():
                passages_by_source.setdefault(p.source_id, []).append(p)

            print(f"\n  SOURCES ({len(sources)}):")
            for src in sources:
                fetched = passages_by_source.get(src.id, [])
                print(
                    f"    [{src.id}] {src.title!r} — {src.url} "
                    f"(provider={src.provider}, {'fetched' if fetched else 'metadata only'})"
                )
                for p in fetched:
                    print(f"        passage #{p.id}  sha256={p.excerpt_sha256[:16]}...")
                    print(f"        text: {p.excerpt_text[:120]!r}")

            findings = (
                session.query(ResearchFinding)
                .filter_by(research_session_id=rs.research_id)
                .all()
            )
            print(f"\n  FINDINGS ({len(findings)}):")
            for f in findings:
                print(f"    [{f.classification.value}] {f.finding_text}")
                claims = session.query(Claim).filter_by(finding_id=f.id).all()
                for c in claims:
                    links = session.query(ClaimEvidence).filter_by(claim_id=c.id).all()
                    cites = ", ".join(f"passage #{l.passage_id} ({l.relation.value})" for l in links)
                    print(f"      claim [{c.classification.value}] conf={c.confidence}: {c.claim_text}")
                    print(f"        evidence: {cites or '(none cited)'}")

            print(f"\n  open_questions: {rs.open_questions}")
            print(f"  follow_ups: {rs.follow_ups}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
