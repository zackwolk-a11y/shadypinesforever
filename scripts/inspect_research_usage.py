#!/usr/bin/env python3
"""Print search-provider usage telemetry (Packet 10, Part G).

Answers exactly the questions the Founder needs after any amount of research
— fixture or live: how many searches happened, which provider, which agent
triggered them, how many sources got stored, and which sessions failed and
why. One row per research session (``app.db.models.research_usage.
ResearchProviderUsage``) — never an API key, a request/response body, or an
invented cost figure.

Usage::

    python scripts/inspect_research_usage.py
    python scripts/inspect_research_usage.py --agent agent_dex
    python scripts/inspect_research_usage.py --provider tavily
    python scripts/inspect_research_usage.py --failed-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.research_usage import ResearchProviderUsage  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's research sessions")
    parser.add_argument("--provider", default=None, help="only this provider (fixture/brave/tavily)")
    parser.add_argument("--failed-only", action="store_true", help="only sessions that failed")
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(ResearchProviderUsage).order_by(ResearchProviderUsage.id)
        if args.agent:
            query = query.filter(ResearchProviderUsage.agent_id == args.agent)
        if args.provider:
            query = query.filter(ResearchProviderUsage.provider == args.provider)
        if args.failed_only:
            query = query.filter(ResearchProviderUsage.failed.is_(True))
        rows = query.all()

        if not rows:
            print("\n(no research usage rows match)")
            return 0

        totals = {
            "sessions": 0, "live_sessions": 0, "failed": 0,
            "queries": 0, "results": 0, "fetched": 0, "fetch_failures": 0, "retries": 0,
        }
        for u in rows:
            fixture_tag = " [FIXTURE]" if u.is_fixture else " [LIVE]"
            status = "FAILED" if u.failed else "ok"
            print(
                f"\n#{u.id} session={u.research_session_id} agent={u.agent_id} "
                f"provider={u.provider}{fixture_tag} [{status}]"
            )
            print(
                f"    queries={u.queries_executed} results={u.results_returned} "
                f"fetched={u.sources_fetched} fetch_failures={u.fetch_failures} "
                f"retries={u.retry_count} duration_ms={u.duration_ms}"
            )
            if u.failed and u.failure_reason:
                print(f"    reason: {u.failure_reason}")
            if u.provider_reported_cost is not None:
                print(f"    provider_reported_cost: {u.provider_reported_cost}")

            totals["sessions"] += 1
            totals["live_sessions"] += 0 if u.is_fixture else 1
            totals["failed"] += 1 if u.failed else 0
            totals["queries"] += u.queries_executed
            totals["results"] += u.results_returned
            totals["fetched"] += u.sources_fetched
            totals["fetch_failures"] += u.fetch_failures
            totals["retries"] += u.retry_count

        print(
            f"\n{totals['sessions']} session(s) ({totals['live_sessions']} live, "
            f"{totals['failed']} failed) — {totals['queries']} quer(y/ies), "
            f"{totals['results']} result(s), {totals['fetched']} source(s) fetched, "
            f"{totals['fetch_failures']} fetch failure(s), {totals['retries']} retr(y/ies)."
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
