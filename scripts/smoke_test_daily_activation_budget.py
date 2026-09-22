#!/usr/bin/env python3
"""Deterministic regression test for the Packet 12 live-day diagnostic bug:
``RECENT_ACTIVATION_PENALTY`` mathematically overwhelmed the daily
activation budget (``Settings.max_daily_agent_activations``) long before it
was ever reached, silently emptying most of a simulated day.

The bug: the highest possible positive score in any period is
``PERIOD_WEIGHT``'s max (3.0, MORNING/AFTERNOON) plus ``CURIOSITY_MAX``
(2.0) = 5.0. At the old penalty (2.5), just 2 prior activations
(2.5 x 2 = 5.0) made a positive score mathematically impossible in *every*
period for *every* agent at once — collectively emptying the rest of the
simulated day (RESEARCH/AFTERNOON/EVENING/NIGHT all auto-advance with zero
activity) however many of the configured 6 daily activations per agent
(48 across all 8) remained unused. Traced and reproduced against a fresh
Day 1 fixture seed before the fix: every seed died at exactly 17 real
activations, every one crammed into MORNING, before RUN DAY auto-advanced
four entire periods back to back with nobody ever activated again.

Two checks here, deliberately different in kind:

1. A fast, direct arithmetic invariant on the constants themselves
   (``app/services/scheduler.py``) — this is the actual root cause, encoded
   so nobody can silently reintroduce it by retuning either constant later
   without this test catching the inconsistency immediately, with no
   simulation run required.
2. An end-to-end behavioral check, driving the real event loop under the
   fixture provider for one full simulated day exactly the way RUN DAY
   does, asserting real activation opportunities reach more than one period
   and a reasonable floor of total activations — while also asserting
   passive actions (OBSERVE/REST/DO_NOTHING/etc.) are still a real,
   legitimate part of the distribution: this fix changes how many chances
   agents get, never what they choose to do with them.

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_daily_activation_budget.py
    python scripts/smoke_test_daily_activation_budget.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_daily_activation_budget.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

#: Multiple seeds, not one: curiosity is a genuine random draw
#: (app/services/scheduler.py's score_agents), so which period(s) end up
#: with real activity is inherently probabilistic — before the fix, EVERY
#: seed died at exactly the same 17 activations, all in MORNING, because
#: the penalty made the outcome deterministic rather than probabilistic.
#: Testing across several seeds is what actually distinguishes "the fix
#: restored genuine variability" from "got lucky once."
SEEDS = ("packet12-activation-budget-a", "packet12-activation-budget-b", "packet12-activation-budget-c")

#: Every fixture day so far (before the fix) died at exactly 17 real
#: activations, every single seed, always in MORNING alone. Comfortably
#: clearing 25 proves the fix without demanding a specific number — the
#: fixture provider's own action weighting, not this test, should decide
#: exactly how many.
MIN_TOTAL_ACTIVATIONS = 25

PASSIVE_ACTIONS = {"REST", "OBSERVE", "LISTEN_TO_MUSIC", "DRINK_COFFEE", "DO_NOTHING"}


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.db.models.world import SimulationClock
    from app.providers.llm import get_llm_provider
    from app.services import scheduler
    from app.services.orchestrator import run_next_event
    from sqlalchemy import select

    settings = get_settings()
    checks: list[tuple[str, bool]] = []

    # ------------------------------------------------------------------
    # 1. The arithmetic invariant — the actual root cause, checked directly.
    # ------------------------------------------------------------------
    max_positive_component_sum = max(scheduler.PERIOD_WEIGHT.values()) + scheduler.CURIOSITY_MAX
    last_chance_n = settings.max_daily_agent_activations - 1
    penalty_at_last_chance = scheduler.RECENT_ACTIVATION_PENALTY * last_chance_n
    checks.append(
        (
            f"an agent's {last_chance_n}th prior activation cannot by itself zero out every "
            f"period's eligibility (penalty {penalty_at_last_chance:.2f} < max possible "
            f"period+curiosity {max_positive_component_sum:.2f})",
            penalty_at_last_chance < max_positive_component_sum,
        )
    )
    # The old, buggy relationship, asserted to no longer hold — a direct
    # regression guard on the exact bug, not just its symptom.
    old_penalty = 2.5
    old_relationship_was_broken = (old_penalty * 2) >= max_positive_component_sum
    checks.append(
        (
            "the old penalty (2.5) is confirmed to have broken this invariant at just 2 "
            "prior activations, which is what this fix corrects",
            old_relationship_was_broken,
        )
    )

    # ------------------------------------------------------------------
    # 2. End-to-end: one real simulated day per seed, exactly like RUN DAY.
    # ------------------------------------------------------------------
    from app.db.session import engine

    all_periods_with_activity: set[str] = set()
    for seed in SEEDS:
        # Dispose the pooled connection before unlinking the file — SQLite
        # keeps writing to an already-open (now-unlinked) file descriptor
        # otherwise, silently continuing the *previous* seed's day count
        # instead of starting a genuinely fresh Day 1.
        engine.dispose()
        _clean_db()
        command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")
        session = SessionLocal()
        try:
            seed_agents.run(session)
            session.commit()
            provider = get_llm_provider(settings)

            clock = session.scalars(select(SimulationClock)).one()
            start_day = clock.current_day
            total_activations = 0
            periods_with_activity: set[str] = set()
            action_distribution: dict[str, int] = {}
            per_agent: dict[str, int] = {}

            for _ in range(400):
                outcome = run_next_event(
                    session, settings=settings, provider=provider, seed=seed, auto_advance=True,
                )
                session.commit()
                if outcome.clock_advance:
                    session.refresh(clock)
                    if clock.current_day != start_day:
                        break
                    continue
                if outcome.note:
                    break
                if outcome.acted:
                    total_activations += 1
                    periods_with_activity.add(clock.current_period)
                    per_agent[outcome.activated_agent_id] = per_agent.get(outcome.activated_agent_id, 0) + 1
                    for a in outcome.executed or ["(no actions)"]:
                        action_distribution[a] = action_distribution.get(a, 0) + 1
            else:
                checks.append((f"seed {seed!r}: day terminated within the 400-event safety ceiling", False))

            all_periods_with_activity |= periods_with_activity
            print(f"[seed {seed!r}] terminated at day {clock.current_day} {clock.current_period}.")
            print(f"  total real activations: {total_activations}")
            print(f"  periods with real activity: {sorted(periods_with_activity)}")
            print(f"  per-agent activation counts: {per_agent}")
            print(f"  action distribution: {action_distribution}\n")

            checks.append(
                (
                    f"seed {seed!r}: at least {MIN_TOTAL_ACTIVATIONS} real activations occurred "
                    f"(was exactly 17, every seed, before the fix)",
                    total_activations >= MIN_TOTAL_ACTIVATIONS,
                )
            )
            checks.append((f"seed {seed!r}: every agent got at least one activation", len(per_agent) == 8))
            checks.append(
                (
                    f"seed {seed!r}: passive actions (REST/OBSERVE/DO_NOTHING/etc.) are still present "
                    "— the fix gives more opportunities, it does not force activity",
                    any(a in PASSIVE_ACTIONS or a == "(no actions)" for a in action_distribution),
                )
            )
            checks.append(
                (
                    f"seed {seed!r}: the day still terminates deterministically (reached day "
                    f"{start_day + 1}, no infinite loop)",
                    clock.current_day == start_day + 1,
                )
            )
        finally:
            session.close()

    # Which period(s) end up with real activity is inherently probabilistic
    # (curiosity is a genuine random draw) — before the fix, every seed
    # landed on the exact same outcome (17 activations, MORNING only),
    # which was itself the symptom: the formula had made the "random" walk
    # entirely deterministic. Real variability returning across seeds is
    # the actual proof the fix works, not any one seed's specific spread.
    checks.append(
        (
            f"across {len(SEEDS)} different seeds, real activity reached more than one period "
            f"at least once (was exactly {{'MORNING'}}, every seed, before the fix) — observed: "
            f"{sorted(all_periods_with_activity)}",
            len(all_periods_with_activity) >= 2,
        )
    )

    print("Checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_ok &= ok

    if not args.keep_db:
        _clean_db()
    else:
        print(f"\nDatabase kept at {DB_PATH}")

    if not all_ok:
        print("\nFAIL: one or more activation-budget assertions failed. See above.")
        return 1
    print(f"\nPASS: the daily activation budget reaches real, spread-out opportunities ({len(checks)} checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
