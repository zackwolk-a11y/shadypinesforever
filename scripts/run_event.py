#!/usr/bin/env python3
"""RUN NEXT EVENT — activate one agent and print what happened.

Runs against the fixture provider by default, so it needs no API key and costs
nothing. Set LLM_PROVIDER=anthropic (with credentials) for a live run.

Usage::

    python scripts/run_event.py            # one event
    python scripts/run_event.py -n 10      # ten events
    python scripts/run_event.py --scores   # show the activation scoreboard too
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
from app.services import scheduler  # noqa: E402
from app.services.orchestrator import run_next_event  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--count", type=int, default=1, help="events to run")
    parser.add_argument("--scores", action="store_true", help="print activation scores")
    parser.add_argument("--seed", default="", help="seed for the activation jitter")
    parser.add_argument(
        "--advance",
        action="store_true",
        help="advance the clock when a period runs out of eligible agents",
    )
    args = parser.parse_args()

    settings = get_settings()
    provider = get_llm_provider(settings)
    print(f"Database: {settings.database_url}")
    print(f"Provider: {provider.name}" + ("  [FIXTURE — not a live model]" if provider.is_fixture else ""))
    print(f"Model:    {settings.agent_model}\n")

    session = SessionLocal()
    try:
        for i in range(args.count):
            if args.scores:
                clock = session.scalars(select(SimulationClock).limit(1)).first()
                if clock is not None:
                    print("  activation scores:")
                    for c in scheduler.score_agents(session, clock, settings, seed=args.seed):
                        print(f"    {c.agent_id:<20} {c.score:6.2f}  (acted {c.activations_today}x today)")

            outcome = run_next_event(
                session, settings=settings, provider=provider,
                seed=args.seed, auto_advance=args.advance,
            )
            session.commit()

            label = f"[{i + 1}/{args.count}]"
            if outcome.clock_advance:
                print(f"{label} -- {outcome.clock_advance}")
                continue
            if outcome.note:
                print(f"{label} {outcome.note}")
                break
            if outcome.rejected_reason:
                print(f"{label} {outcome.activated_agent_id}: REJECTED — {outcome.rejected_reason}")
                continue

            decision = outcome.decision
            where = f" [conversation {outcome.conversation_id}]" if outcome.conversation_id else ""
            print(f"{label} {outcome.activated_agent_id}{where}: {decision.summary}")
            print(f"      activity={decision.activity!r} actions={outcome.executed or ['(none)']}")
            if decision.public_dialogue:
                print(f'      says: "{decision.public_dialogue}"')
            print(f"      events={outcome.event_ids} correlation={outcome.correlation_id}")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
