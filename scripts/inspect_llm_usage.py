#!/usr/bin/env python3
"""Print LLM usage telemetry (Packet 11, Part M).

One row per model call (``app.db.models.telemetry.LLMRun``, written by every
purpose — agent decisions, search query generation, research synthesis,
reflection, daily report — through the one shared
``app.services.telemetry.record_llm_run``). Answers: how many real model
calls happened, which model, which agent, total input/output tokens, and a
breakdown by purpose (decision vs. query generation vs. interpretation vs.
reflection vs. synthesis).

Usage::

    python scripts/inspect_llm_usage.py
    python scripts/inspect_llm_usage.py --agent agent_dex
    python scripts/inspect_llm_usage.py --purpose research_synthesis
    python scripts/inspect_llm_usage.py --live-only
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_database_url  # noqa: E402
from app.db.models.telemetry import LLMRun  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="only this agent's calls")
    parser.add_argument("--purpose", default=None, help="only this purpose (agent_decision/search_query_generation/research_synthesis/reflection/daily_report)")
    parser.add_argument("--live-only", action="store_true", help="hide fixture calls")
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    session = SessionLocal()
    try:
        query = session.query(LLMRun).order_by(LLMRun.id)
        if args.agent:
            query = query.filter(LLMRun.agent_id == args.agent)
        if args.purpose:
            query = query.filter(LLMRun.purpose == args.purpose)
        if args.live_only:
            query = query.filter(LLMRun.is_fixture.is_(False))
        rows = query.all()

        if not rows:
            print("\n(no LLM runs match)")
            return 0

        for r in rows:
            fixture_tag = " [FIXTURE]" if r.is_fixture else " [LIVE]"
            print(
                f"\n#{r.id} [{r.purpose}]{fixture_tag} agent={r.agent_id or '-'} "
                f"provider={r.provider} model={r.model}"
            )
            print(
                f"    input={r.input_tokens} output={r.output_tokens} "
                f"cache_write={r.cache_creation_input_tokens} cache_read={r.cache_read_input_tokens} "
                f"retries={r.retry_count} latency_ms={r.latency_ms} stop={r.stop_reason}"
            )
            if r.estimated_cost_usd:
                print(f"    estimated_cost_usd={r.estimated_cost_usd:.6f}")

        by_purpose: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "input": 0, "output": 0, "cost": 0.0, "retries": 0})
        totals = {"calls": 0, "live_calls": 0, "input": 0, "output": 0, "cost": 0.0, "retries": 0}
        for r in rows:
            b = by_purpose[r.purpose]
            b["calls"] += 1
            b["input"] += r.input_tokens
            b["output"] += r.output_tokens
            b["cost"] += r.estimated_cost_usd
            b["retries"] += r.retry_count
            totals["calls"] += 1
            totals["live_calls"] += 0 if r.is_fixture else 1
            totals["input"] += r.input_tokens
            totals["output"] += r.output_tokens
            totals["cost"] += r.estimated_cost_usd
            totals["retries"] += r.retry_count

        print("\n--- by purpose ---")
        for purpose, b in sorted(by_purpose.items()):
            print(
                f"  {purpose:26s} calls={int(b['calls']):4d} "
                f"input={int(b['input']):7d} output={int(b['output']):7d} "
                f"retries={int(b['retries']):3d} cost=${b['cost']:.6f}"
            )

        print(
            f"\n{totals['calls']} call(s) ({totals['live_calls']} live) — "
            f"{totals['input']} input token(s), {totals['output']} output token(s), "
            f"{totals['retries']} retr(y/ies), ${totals['cost']:.6f} estimated."
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
