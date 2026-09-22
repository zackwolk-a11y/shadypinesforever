#!/usr/bin/env python3
"""Print the Founder Daily Field Report(s) (Packet 9).

By default prints the rendered report exactly as the Founder would read it.
``--structured`` also prints the machine-queryable backing data behind it —
the ranked, provenanced facts (real database ids and §2 classifications)
``app.services.daily_synthesis.gather_facts`` gathered before any prose was
written, which is what makes "does this report's prose actually map to real
activity" checkable directly rather than only by re-reading logs.

Usage::

    python scripts/inspect_daily_report.py
    python scripts/inspect_daily_report.py --day 3
    python scripts/inspect_daily_report.py --day 3 --structured
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.reports import DailyReport  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=int, default=None, help="only this simulated day's report")
    parser.add_argument(
        "--structured", action="store_true",
        help="also print the machine-queryable facts + synthesis backing the prose",
    )
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(DailyReport).order_by(DailyReport.day_number)
        if args.day is not None:
            query = query.filter(DailyReport.day_number == args.day)
        rows = query.all()

        if not rows:
            print("\n(no daily reports match)")
            return 0

        for report in rows:
            fixture_tag = " [FIXTURE]" if report.is_fixture else ""
            activity_tag = "" if report.had_meaningful_activity else " (quiet day)"
            print("\n" + "#" * 70)
            print(f"Report #{report.id} — day {report.day_number}{fixture_tag}{activity_tag}")
            print("#" * 70)
            print(report.summary_text)

            if args.structured:
                print("\n--- structured backing data ---")
                print(json.dumps(report.structured, indent=2, default=str))

        print(f"\n{len(rows)} report(s).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
