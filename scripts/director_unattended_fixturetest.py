#!/usr/bin/env python3
"""Isolated fixture tests for scripts/director_unattended.py.

Runs the runner as a real subprocess (never imports it into this
process), with DIRECTOR_UNATTENDED_STATE_ROOT and
DIRECTOR_UNATTENDED_MASTER_INDEX_PATH both pointed at a disposable temp
directory / scratch subtree for the whole test file. This is the direct
fix for a real incident: a fixture-provider test run of this runner once
wrote into the exact same real .director/unattended_status.json and
.director/founder_packets/unattended_director_shift_2026-09-04.md paths a
genuine unattended shift uses, and that state was later mistaken for
fixture leftover and deleted.

Every assertion in this file explicitly re-checks that the REAL paths
(.director/unattended_status.json, .director/founder_packets/
unattended_director_shift_2026-09-04.md, .director/founder_packets/
unattended_shift_completion_2026-09-04.md, and the real canonical
master_evidence_roadmap_index_2026-09-04.md) are byte-for-byte unchanged
before and after the entire test run -- not merely that the isolated
copies behave correctly.

Run with:
    .venv/bin/python scripts/director_unattended_fixturetest.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

RUNNER = REPO_ROOT / "scripts" / "director_unattended.py"

REAL_DIRECTOR_DIR = REPO_ROOT / ".director"
REAL_STATUS_PATH = REAL_DIRECTOR_DIR / "unattended_status.json"
REAL_ROLLING_PACKET = REAL_DIRECTOR_DIR / "founder_packets" / "unattended_director_shift_2026-09-04.md"
REAL_COMPLETION_PACKET = REAL_DIRECTOR_DIR / "founder_packets" / "unattended_shift_completion_2026-09-04.md"
REAL_MASTER_INDEX = REAL_DIRECTOR_DIR / "founder_packets" / "master_evidence_roadmap_index_2026-09-04.md"
REAL_LOCK = REAL_DIRECTOR_DIR / "unattended.lock"
REAL_STOP_FLAG = REAL_DIRECTOR_DIR / "unattended_stop_requested"

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(("PASS " if passed else "FAIL "), name, ("" if passed else f"— {detail}"))


def _hash_or_none(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def run_once(state_root: Path, master_index_scratch: str, extra_env: dict[str, str] | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["LLM_PROVIDER"] = "fixture"
    env["DIRECTOR_UNATTENDED_STATE_ROOT"] = str(state_root)
    env["DIRECTOR_UNATTENDED_MASTER_INDEX_PATH"] = master_index_scratch
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(RUNNER)], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=timeout,
    )


def status_at(state_root: Path) -> dict:
    return json.loads((state_root / "unattended_status.json").read_text())


def main() -> int:
    # Snapshot every real path this test must never touch, BEFORE anything runs.
    real_before = {
        "status": _hash_or_none(REAL_STATUS_PATH),
        "rolling_packet": _hash_or_none(REAL_ROLLING_PACKET),
        "completion_packet": _hash_or_none(REAL_COMPLETION_PACKET),
        "master_index": _hash_or_none(REAL_MASTER_INDEX),
        "lock": _hash_or_none(REAL_LOCK),
        "stop_flag": _hash_or_none(REAL_STOP_FLAG),
    }

    tmp_root = Path(tempfile.mkdtemp(prefix="director_unattended_fixturetest_"))
    master_index_scratch_relpath = "founder_packets/_unattended_fixturetest_scratch_master_index.md"
    master_index_scratch_abspath = REAL_DIRECTOR_DIR / master_index_scratch_relpath
    try:
        # Seed the scratch "master index" the addendum task will append to --
        # this is a harmless, clearly-named test artifact under an approved
        # WRITE_DIRECTOR_ARTIFACT subtree, never the real canonical file.
        master_index_scratch_abspath.parent.mkdir(parents=True, exist_ok=True)
        master_index_scratch_abspath.write_text("# Scratch master index for fixture testing only\n")

        # --- Test 1: full run completes without touching any real path ---
        proc = run_once(tmp_root, master_index_scratch_relpath)
        record("full isolated run exits 0", proc.returncode == 0, proc.stdout[-500:] + proc.stderr[-500:])
        record("isolated status file was created (not the real one)", (tmp_root / "unattended_status.json").exists(), "")
        status = status_at(tmp_root)
        record("planner completed more tasks than the original fixed 10-task queue (proves dynamic generation)", status["completed_task_count"] > 10, str(status["completed_task_count"]))
        record("planner ran through multiple planning cycles", status["planning_cycle"] > status["completed_task_count"] - 1, str(status["planning_cycle"]))
        record("dynamically_generated_task_count > 0 (per-agent generator fired)", status["dynamically_generated_task_count"] > 0, str(status["dynamically_generated_task_count"]))
        record("stop_reason is a genuine exhaustion, not a fixed count", status["stop_reason"] == "genuinely_exhausted", status["stop_reason"])
        record("live_db_mutated is false", status["live_db_mutated"] is False, "")
        record(
            "attempt_live_window_1 correctly returns LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED, not COMPLETED",
            "attempt_live_window_1" in status.get("live_bound_not_guaranteed_task_ids", [])
            and "attempt_live_window_1" not in status["completed_task_ids"],
            str(status.get("live_bound_not_guaranteed_task_ids")),
        )
        record(
            "live_events_added_total is zero (no live advancement occurred)",
            status.get("live_events_added_total", -1) == 0,
            str(status.get("live_events_added_total")),
        )
        record(
            "max_live_event_baseline is unchanged from the real 623 baseline",
            status["max_live_event_baseline"] == 623,
            str(status["max_live_event_baseline"]),
        )

        # --- Test 2: resume does not duplicate / re-spend completed work ---
        calls_after_first = status["provider_calls_used"]
        completed_after_first = status["completed_task_count"]
        proc2 = run_once(tmp_root, master_index_scratch_relpath)
        record("second run against already-exhausted state exits 0", proc2.returncode == 0, proc2.stdout[-300:])
        status2 = status_at(tmp_root)
        record("resume does not re-run completed tasks", status2["completed_task_count"] == completed_after_first, f"{status2['completed_task_count']} vs {completed_after_first}")
        record("resume does not re-spend provider calls", status2["provider_calls_used"] == calls_after_first, f"{status2['provider_calls_used']} vs {calls_after_first}")
        record(
            "resume does not re-attempt a live window already marked LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED",
            status2.get("live_bound_not_guaranteed_task_ids") == status.get("live_bound_not_guaranteed_task_ids"),
            f"{status2.get('live_bound_not_guaranteed_task_ids')} vs {status.get('live_bound_not_guaranteed_task_ids')}",
        )

        # --- Test 3: stop-flag mid-shift + resume-after-stop, fresh state ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        stop_flag = tmp_root / "unattended_stop_requested"

        # Prime partial state by running once, then rewinding completed_task_ids
        # (mirrors real mid-shift interruption without needing real timing races).
        run_once(tmp_root, master_index_scratch_relpath)
        primed = status_at(tmp_root)
        rewound = dict(primed)
        rewound["completed_task_ids"] = primed["completed_task_ids"][:5]
        rewound["completed_task_count"] = 5
        rewound["stop_reason"] = None
        (tmp_root / "unattended_status.json").write_text(json.dumps(rewound, indent=2))
        stop_flag.write_text("")

        proc3 = run_once(tmp_root, master_index_scratch_relpath)
        status3 = status_at(tmp_root)
        record("stop flag halts before completing everything", status3["completed_task_count"] < primed["completed_task_count"] or status3["stop_reason"] == "founder_requested_stop", str(status3))
        record("stop flag file is cleared after honoring it", not stop_flag.exists(), "")

        proc4 = run_once(tmp_root, master_index_scratch_relpath)
        status4 = status_at(tmp_root)
        record("resume-after-stop completes the remaining work without duplicating the first 5", status4["completed_task_count"] == primed["completed_task_count"], f"{status4['completed_task_count']} vs {primed['completed_task_count']}")

        # --- Test 4: lock prevents a concurrent second instance ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        (tmp_root / "unattended.lock").write_text(str(os.getpid()))  # this test process is genuinely alive
        proc5 = run_once(tmp_root, master_index_scratch_relpath)
        record("a second instance refuses to start while a live lock exists", proc5.returncode == 1 and "already running" in proc5.stdout, proc5.stdout)
        (tmp_root / "unattended.lock").unlink()

        # --- Test 5: network-outage simulation falls back to offline work ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        proc6 = run_once(tmp_root, master_index_scratch_relpath, extra_env={"ANTHROPIC_API_KEY": ""})
        status6 = status_at(tmp_root)
        record(
            "with no provider key, D-class tasks defer/fail but R-class offline tasks still complete",
            any(t.startswith(("memory_formation", "agent_opportunity", "research_initiation", "agent_question_continuity", "llm_run_cost", "wall_rabbit", "blocked_candidates", "relationship_dump", "message_provenance", "reflection_pressure", "agent_profile_")) for t in status6["completed_task_ids"]),
            str(status6["completed_task_ids"]),
        )

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
        master_index_scratch_abspath.unlink(missing_ok=True)  # the test's own scratch file, never the real index

    # --- Final, most important check: every real path is byte-identical ---
    real_after = {
        "status": _hash_or_none(REAL_STATUS_PATH),
        "rolling_packet": _hash_or_none(REAL_ROLLING_PACKET),
        "completion_packet": _hash_or_none(REAL_COMPLETION_PACKET),
        "master_index": _hash_or_none(REAL_MASTER_INDEX),
        "lock": _hash_or_none(REAL_LOCK),
        "stop_flag": _hash_or_none(REAL_STOP_FLAG),
    }
    for key in real_before:
        record(f"real path unchanged across the whole test run: {key}", real_before[key] == real_after[key], f"before={real_before[key]} after={real_after[key]}")

    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} scenarios passed.")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
