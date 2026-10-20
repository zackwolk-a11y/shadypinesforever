#!/usr/bin/env python3
"""Resume a paused Village — only after the provider proves it can answer.

    python scripts/resume_village.py                 # probe once, resume if OK
    python scripts/resume_village.py --wait 6        # retry a dropped connection up to 6x (backoff)
    python scripts/resume_village.py --probe-only    # just report provider health; change nothing
    python scripts/resume_village.py --manual-pause  # also lift a Founder's manual pause

Exit codes: 0 resumed (or already running), 75 provider not ready (try later),
2 refused (manual pause without --manual-pause, or live DB without --founder).

What it fixes: a trial used to need a person to (a) notice the run had
stopped, (b) check usage by hand, (c) flip the pause. A Mac sleeping or
dropping Wi-Fi made (b) fail and blocked the whole session. This does the
check itself, retries transient connection failures with backoff, and only
lifts automated pauses (PAUSED_RATE_LIMIT / PAUSED_PROVIDER_ERROR) unless told
otherwise. Safe to run from launchd/cron before each trial session.

On APP_ENV=live it requires --founder: resuming the canonical Village is a
Founder act (Director constitution §2).
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
from app.domain.enums import EventType, PauseReason  # noqa: E402
from app.providers.llm import get_llm_provider  # noqa: E402
from app.services.events import record_event  # noqa: E402
from app.services.provider_health import probe_with_backoff  # noqa: E402

AUTOMATED_PAUSES = {PauseReason.RATE_LIMIT.value, PauseReason.PROVIDER_ERROR.value}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wait", type=int, default=1, help="probe attempts for transient errors")
    parser.add_argument("--wait-seconds", type=float, default=60.0, help="first backoff delay")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--manual-pause", action="store_true", help="also lift a manual (Founder) pause")
    parser.add_argument("--founder", action="store_true", help="required to resume APP_ENV=live")
    args = parser.parse_args()

    settings = get_settings()
    provider = get_llm_provider(settings)
    result = probe_with_backoff(provider, settings, attempts=max(1, args.wait), wait_seconds=args.wait_seconds)
    print(f"Provider {provider.name}: {result.status} after {result.attempts} attempt(s) — {result.detail}")
    if args.probe_only:
        return 0 if result.ok else 75
    if not result.ok:
        print("Not resuming: the provider isn't ready. Nothing changed.")
        return 75

    if settings.app_env == "live" and not args.founder:
        print("Refusing to resume the live Village without --founder.")
        return 2

    session = SessionLocal()
    try:
        clock = session.scalars(select(SimulationClock).limit(1)).first()
        if clock is None:
            print("No simulation clock.")
            return 2
        if not clock.is_paused:
            print(f"Already running (day {clock.current_day} {clock.current_period}).")
            return 0
        reason = clock.pause_reason
        if reason not in AUTOMATED_PAUSES and not args.manual_pause:
            print("Paused manually by the Founder; pass --manual-pause to lift that too. Nothing changed.")
            return 2
        clock.is_paused = False
        clock.pause_reason = None
        record_event(
            session, event_type=EventType.SIMULATION_RESUMED,
            payload={"previous_pause_reason": reason, "probe": result.detail, "probe_attempts": result.attempts},
            clock=clock,
        )
        session.commit()
        print(f"Resumed at day {clock.current_day} {clock.current_period} (was {reason or 'manual'}).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
