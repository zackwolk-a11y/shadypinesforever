#!/usr/bin/env python3
"""PROVE ONE CYCLE — run a bounded trial on a disposable copy until the
database shows one complete chain, then write the evidence.

    voluntary meeting -> meaningful conversation -> remembered experience -> executed action

Never touches the canonical live Village: it refuses APP_ENV=live and any path
under the live data directory, and works only on a fresh database or a copy.

Usage::

    # Offline wiring check (fixture provider, no spend):
    python scripts/prove_cycle.py --fresh

    # Real-model trial on a fresh Village, capped at 80 model calls:
    LLM_PROVIDER=claude_cli python scripts/prove_cycle.py --fresh --max-llm-calls 80

    # Real-model trial on a copy of an existing Village (e.g. a backup):
    LLM_PROVIDER=claude_cli python scripts/prove_cycle.py --clone-from /path/to/backup.db

    # Continue a trial that paused (provider/quota) — same workdir:
    python scripts/resume_village.py --wait 6   # with DATABASE_URL pointed at the trial db
    LLM_PROVIDER=claude_cli python scripts/prove_cycle.py --continue .cycle_trials/<run>

Writes ``<workdir>/cycle_proof.md`` (human-readable, with real quotes and row
ids) and ``<workdir>/cycle_proof.json``. Exit: 0 a complete cycle was found
(GENUINE only if every decision in it was live), 1 none yet, 75 the provider
paused the run (resume and --continue).

The trial profile (override any of these in the environment):
    MORNING_GATHERING=off              only meetings agents start themselves
    CONVERSATION_INTERLEAVE_EVERY=3    the rest of the Village keeps living during a conversation
    MAX_PERIOD_AGENT_ACTIVATIONS=3     the day's budget isn't all spent by MORNING
    INTENTION_WINDOW_PERIODS=10        intentions stay open two simulated days
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIAL_PROFILE = {
    "MORNING_GATHERING": "off",
    "CONVERSATION_INTERLEAVE_EVERY": "3",
    "MAX_PERIOD_AGENT_ACTIVATIONS": "3",
    "INTENTION_WINDOW_PERIODS": "10",
}


def _refuse_live(path: Path) -> None:
    if os.environ.get("APP_ENV", "development") == "live":
        sys.exit("Refusing: APP_ENV=live. This harness only runs on disposable copies.")
    data_root = Path(os.environ.get("VILLAGE_DATA_ROOT", REPO_ROOT / "data")).resolve()
    live_dir = data_root / "live"
    resolved = path.resolve()
    if resolved == live_dir or live_dir in resolved.parents:
        sys.exit(f"Refusing: {resolved} is inside the live data directory {live_dir}.")


def _run(cmd: list[str], env: dict) -> None:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed:\n{proc.stdout}\n{proc.stderr}")


def _prepare(args) -> Path:
    if args.continue_dir:
        workdir = Path(args.continue_dir)
        db = workdir / "village.db"
        if not db.exists():
            sys.exit(f"No trial database at {db}")
        _refuse_live(db)
        return workdir
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    workdir = Path(args.workdir or REPO_ROOT / ".cycle_trials" / stamp)
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "village.db"
    _refuse_live(db)
    if db.exists():
        sys.exit(f"{db} already exists; use --continue {workdir} or a new --workdir")
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db}"}
    python = sys.executable
    if args.clone_from:
        source = Path(args.clone_from)
        if not source.exists():
            sys.exit(f"No database at {source}")
        # SQLite's own online backup: consistent even with a live WAL, and
        # read-only on the source.
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        dst = sqlite3.connect(db)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        _run([python, "-m", "alembic", "upgrade", "head"], env)
        # A cloned Village may be paused (e.g. halted after a provider
        # failure); the copy is ours to run, the original is untouched.
        conn = sqlite3.connect(db)
        with conn:
            conn.execute("UPDATE simulation_clock SET is_paused = 0, pause_reason = NULL")
        conn.close()
    else:
        _run([python, "-m", "alembic", "upgrade", "head"], env)
        _run([python, "scripts/seed_agents.py"], env)
    return workdir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fresh", action="store_true", help="seed a brand-new Village (default)")
    source.add_argument("--clone-from", help="copy this Village database and run the copy")
    source.add_argument("--continue", dest="continue_dir", help="continue a previous trial workdir")
    parser.add_argument("--workdir", help="where the trial database and evidence go")
    parser.add_argument("--max-events", type=int, default=600)
    parser.add_argument("--max-llm-calls", type=int, default=150,
                        help="hard ceiling on model calls this run (all purposes)")
    parser.add_argument("--seed", default="cycle-proof")
    parser.add_argument("--keep-going", action="store_true", help="don't stop at the first complete cycle")
    parser.add_argument("--engine-defaults", action="store_true",
                        help="skip the trial profile (reproduce old engine behaviour)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    workdir = _prepare(args)
    db = workdir / "village.db"
    os.environ["APP_ENV"] = "development"
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    if not args.engine_defaults:
        for key, value in TRIAL_PROFILE.items():
            os.environ.setdefault(key, value)

    sys.path.insert(0, str(REPO_ROOT))
    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.db.models.telemetry import LLMRun
    from app.db.session import SessionLocal
    from app.providers.llm import get_llm_provider
    from app.services import cycle_proof
    from app.services.orchestrator import run_next_event

    settings = get_settings()
    provider = get_llm_provider(settings)
    session = SessionLocal()
    log_path = workdir / "trial_log.jsonl"
    started_runs = session.scalar(select(func.count()).select_from(LLMRun)) or 0
    status = "BUDGET_SPENT"
    print(f"Trial database: {db}")
    print(f"Provider: {provider.name}{'  [FIXTURE — wiring only, not real behaviour]' if provider.is_fixture else ''}")
    print("Profile: " + ", ".join(
        f"{k}={os.environ.get(k)}" for k in TRIAL_PROFILE
    ) + (" (engine defaults)" if args.engine_defaults else ""))

    found = None
    try:
        with log_path.open("a") as log:
            for i in range(args.max_events):
                outcome = run_next_event(session, settings=settings, provider=provider,
                                         seed=args.seed, auto_advance=True)
                session.commit()
                log.write(json.dumps({
                    "i": i, "agent": outcome.activated_agent_id, "conversation": outcome.conversation_id,
                    "executed": outcome.executed, "rejected": outcome.rejected_reason,
                    "summary": outcome.decision.summary if outcome.decision else None,
                    "advance": outcome.clock_advance, "note": outcome.note,
                }) + "\n")
                if not args.quiet and outcome.decision is not None:
                    extra = []
                    if outcome.decision.new_intention is not None:
                        extra.append(f"+intention: {outcome.decision.new_intention.what}")
                    if outcome.decision.fulfills_intention_id:
                        extra.append(f"fulfils I{outcome.decision.fulfills_intention_id}")
                    where = f" [conv {outcome.conversation_id}]" if outcome.conversation_id else ""
                    print(f"  {outcome.activated_agent_id}{where}: {outcome.decision.summary[:110]}"
                          + (f"  ({'; '.join(extra)})" if extra else ""))
                elif not args.quiet and outcome.clock_advance:
                    print(f"  -- {outcome.clock_advance}")
                if outcome.provider_unavailable:
                    status = "PROVIDER_PAUSED"
                    print(f"Provider stopped the run: {outcome.rejected_reason}")
                    break
                if outcome.note and "paused" in outcome.note.lower():
                    status = "PAUSED"
                    break
                runs = (session.scalar(select(func.count()).select_from(LLMRun)) or 0) - started_runs
                if runs >= args.max_llm_calls:
                    print(f"Model-call budget reached ({runs}).")
                    break
                if outcome.decision is not None and (
                    outcome.decision.fulfills_intention_id or "intentions" in str(outcome.executed) or i % 10 == 0
                ):
                    complete = [c for c in cycle_proof.evaluate(session) if c.complete]
                    if complete and not args.keep_going:
                        found = complete[0]
                        status = "CYCLE_FOUND"
                        break
            else:
                status = "EVENT_CEILING"
    finally:
        cycles = cycle_proof.evaluate(session)
        best = found or (cycles[0] if cycles else None)
        metrics = cycle_proof.village_metrics(session)
        header = {
            "Run": dt.datetime.now().isoformat(timespec="seconds"),
            "Database": str(db),
            "Provider": f"{provider.name} (model {settings.agent_model})",
            "Stopped because": status,
            "Model calls this run": (session.scalar(select(func.count()).select_from(LLMRun)) or 0) - started_runs,
            "Candidate chains found": len(cycles),
            "Complete chains": sum(1 for c in cycles if c.complete),
        }
        (workdir / "cycle_proof.md").write_text(cycle_proof.render_markdown(best, metrics, header))
        (workdir / "cycle_proof.json").write_text(json.dumps({
            "header": header, "best": best.as_dict() if best else None,
            "all": [c.as_dict() for c in cycles], "metrics": metrics,
        }, indent=2, default=str))
        session.close()

    print()
    print(f"Verdict: {best.verdict if best else 'NO CYCLE YET'}")
    if best:
        for link in best.links:
            print(f"  {link.status:8} {link.name}: {link.why}")
    print(f"Evidence: {workdir / 'cycle_proof.md'}")
    if status == "PROVIDER_PAUSED":
        return 75
    return 0 if best is not None and best.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
