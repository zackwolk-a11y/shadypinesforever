#!/usr/bin/env python3
"""RUN ONE DAY — advance the event queue until the day rolls over.

Periods advance when the agents in them run out of reasons to act, rather than
on a fixed schedule of model calls. A day is therefore as long as it needs to
be, bounded by --max-events so a runaway can never spend without limit.

Usage::

    python scripts/run_day.py              # one simulated day
    python scripts/run_day.py --days 3     # three
    python scripts/run_day.py --quiet      # totals only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models.world import SimulationClock  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.providers.llm import get_llm_provider  # noqa: E402
from app.services.orchestrator import run_next_event  # noqa: E402

DEFAULT_MAX_EVENTS_PER_DAY = 400


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1, help="simulated days to run")
    parser.add_argument("--seed", default="", help="seed for the activation jitter")
    parser.add_argument(
        "--max-events",
        type=int,
        default=DEFAULT_MAX_EVENTS_PER_DAY,
        help="safety ceiling on events per day",
    )
    parser.add_argument("--quiet", action="store_true", help="totals only")
    args = parser.parse_args()

    settings = get_settings()
    provider = get_llm_provider(settings)
    print(f"Database: {settings.database_url}")
    print(
        f"Provider: {provider.name}"
        + ("  [FIXTURE — not a live model]" if provider.is_fixture else "")
    )

    session = SessionLocal()
    try:
        for _ in range(args.days):
            clock = session.scalars(select(SimulationClock).limit(1)).first()
            if clock is None:
                print("No simulation clock. Run scripts/seed_agents.py first.")
                return 1

            start_day = clock.current_day
            print(f"\n=== DAY {start_day} ===")
            acted = spoken = advances = 0

            for _ in range(args.max_events):
                outcome = run_next_event(
                    session, settings=settings, provider=provider,
                    seed=args.seed, auto_advance=True,
                )
                session.commit()

                if outcome.clock_advance:
                    advances += 1
                    if not args.quiet:
                        print(f"  -- {outcome.clock_advance}")
                    session.refresh(clock)
                    if clock.current_day != start_day:
                        break
                    continue

                if outcome.note:
                    print(f"  {outcome.note}")
                    break

                if outcome.rejected_reason:
                    if not args.quiet:
                        print(f"  {outcome.activated_agent_id}: rejected — {outcome.rejected_reason}")
                    continue

                acted += 1
                spoken += 1 if outcome.spoke else 0
                if not args.quiet:
                    where = f" [conversation {outcome.conversation_id}]" if outcome.conversation_id else ""
                    print(f"  {outcome.activated_agent_id}{where}: {outcome.decision.summary}")
            else:
                print(f"  Hit the {args.max_events}-event ceiling; stopping this day.")

            print(f"  day {start_day}: {acted} actions, {spoken} utterances, {advances} period changes")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
