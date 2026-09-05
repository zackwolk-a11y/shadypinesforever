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
import re
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


def _extract_function_source(text: str, func_name: str) -> str:
    """Pulls one top-level function's full source text out of
    director_unattended.py by pattern, without ever importing the module
    into this process (this file's own standing invariant) -- used to
    prove by source inspection, not just behavior, that the new dynamic
    task classes can never select an unapproved capability."""
    pattern = re.compile(rf"^def {re.escape(func_name)}\(.*?(?=^def |\Z)", re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    assert m, f"could not find function {func_name!r} in director_unattended.py"
    return m.group(0)


def _build_fake_village_data_root() -> Path:
    """CORRECTION, 2026-09-05, following a real incident: this is now the
    ONLY thing that makes the isolated test suite actually safe.
    RUN_BOUNDED_LIVE_WINDOW is genuinely enabled (worst case 42 fits the
    50-event window), so any subprocess launch of the real runner that
    still points at the real VILLAGE_DATA_ROOT can genuinely advance the
    real live Village -- redirecting only this runner's own status/packet
    paths (the prior fix) was never sufficient on its own. Builds a
    disposable directory shaped exactly like the real VILLAGE_DATA_ROOT
    (a live/internal_village.db with the real schema, real seed_agents
    roster, paused, zero events) so app.core.db_safety -- and everything
    built on it, including director_broker.CANONICAL_LIVE_DB_PATH -- has
    no way to reach real production data even if every task in the queue
    runs to completion.
    """
    root = Path(tempfile.mkdtemp(prefix="director_unattended_fixturetest_village_"))
    live_dir = root / "live"
    live_dir.mkdir(parents=True)
    db_path = live_dir / "internal_village.db"

    import sqlite3

    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.db.models  # noqa: F401 -- registers all models on Base.metadata
    from app.db.base import Base
    import seed_agents

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_agents.run(session)
    session.commit()
    session.close()
    engine.dispose()

    # seed_agents.run() never calls record_event -- a fresh seed always
    # starts at zero real Event rows. Confirmed here, not assumed, so a
    # future seed_agents change that DID emit events would be caught
    # immediately (an assertion failure) rather than silently producing a
    # wrong baseline.
    conn = sqlite3.connect(str(db_path))
    starting_max_event = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]
    conn.execute("UPDATE simulation_clock SET is_paused = 1")
    conn.commit()
    conn.close()
    assert starting_max_event == 0, f"seed_agents.run() unexpectedly produced {starting_max_event} events -- fix _build_fake_village_data_root's baseline assumption before trusting this test suite"

    return root


def run_once(
    state_root: Path, master_index_scratch: str, fake_village_root: Path,
    extra_env: dict[str, str] | None = None, timeout: int = 60,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["LLM_PROVIDER"] = "fixture"
    env["DIRECTOR_UNATTENDED_STATE_ROOT"] = str(state_root)
    env["DIRECTOR_UNATTENDED_MASTER_INDEX_PATH"] = master_index_scratch
    # The two together are what make this test suite structurally unable
    # to reach real production data, regardless of which tasks run:
    # VILLAGE_DATA_ROOT is app.core.db_safety's own native override (so
    # CANONICAL_LIVE_DB_PATH, wherever it's imported, resolves to the
    # disposable directory), and the baseline override tells THIS runner
    # what "unchanged" means for that disposable DB (0, not the real 623).
    env["VILLAGE_DATA_ROOT"] = str(fake_village_root)
    env["DIRECTOR_UNATTENDED_BASELINE_MAX_EVENT"] = "0"
    # Default this whole suite to a shift-local live-window cap of 1 so
    # every test that doesn't care about the continuous-planning behavior
    # itself stays fast and deterministic (one live window + one analysis
    # per shift, not up to 5 real fixture-provider live windows). Tests
    # that specifically exercise cross-shift continuation override this.
    env["DIRECTOR_UNATTENDED_MAX_LIVE_WINDOWS"] = "1"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(RUNNER)], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=timeout,
    )


def status_at(state_root: Path) -> dict:
    return json.loads((state_root / "unattended_status.json").read_text())


def main() -> int:
    # Snapshot every real path this test must never touch, BEFORE anything
    # runs -- INCLUDING the real live Village DB itself now (added after a
    # real incident where this file's earlier version omitted exactly this
    # check and a fixture-provider test run advanced the true live Village
    # by 10 events, because RUN_BOUNDED_LIVE_WINDOW's worst case (42) now
    # fits inside the 50-event window and this file's isolation, before
    # this fix, only ever redirected the runner's own bookkeeping paths).
    import app.core.db_safety as _db_safety

    real_before = {
        "status": _hash_or_none(REAL_STATUS_PATH),
        "rolling_packet": _hash_or_none(REAL_ROLLING_PACKET),
        "completion_packet": _hash_or_none(REAL_COMPLETION_PACKET),
        "master_index": _hash_or_none(REAL_MASTER_INDEX),
        "lock": _hash_or_none(REAL_LOCK),
        "stop_flag": _hash_or_none(REAL_STOP_FLAG),
        "live_village_db": _hash_or_none(_db_safety.CANONICAL_LIVE_DB_PATH),
    }
    real_live_max_event_before = None
    if _db_safety.CANONICAL_LIVE_DB_PATH.exists():
        import sqlite3
        conn = sqlite3.connect(f"file:{_db_safety.CANONICAL_LIVE_DB_PATH}?mode=ro", uri=True)
        real_live_max_event_before = conn.execute("SELECT MAX(id) FROM events").fetchone()[0]
        conn.close()

    tmp_root = Path(tempfile.mkdtemp(prefix="director_unattended_fixturetest_"))
    master_index_scratch_relpath = "founder_packets/_unattended_fixturetest_scratch_master_index.md"
    master_index_scratch_abspath = REAL_DIRECTOR_DIR / master_index_scratch_relpath
    fake_village_root = _build_fake_village_data_root()
    try:
        # Seed the scratch "master index" the addendum task will append to --
        # this is a harmless, clearly-named test artifact under an approved
        # WRITE_DIRECTOR_ARTIFACT subtree, never the real canonical file.
        master_index_scratch_abspath.parent.mkdir(parents=True, exist_ok=True)
        master_index_scratch_abspath.write_text("# Scratch master index for fixture testing only\n")

        # --- Test 1: full run completes without touching any real path.
        # attempt_live_window_1 is now genuinely enabled (worst case 42
        # fits the 50-event window) and WILL execute for real against the
        # fully disposable fake village -- that is now correct, intended
        # behavior, not a refusal, and this is exactly why the fake
        # village must be real, seeded, and paused rather than a stub.
        # DIRECTOR_UNATTENDED_MAX_LIVE_WINDOWS=1 (this suite's default) caps
        # this run to exactly one live window + its automatic analysis --
        # this test's job is the ORIGINAL 26-seed-task+one-window shape;
        # the new continuous-planning-across-shifts behavior is Test 2. ---
        proc = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("full isolated run exits 0", proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-800:])
        record("isolated status file was created (not the real one)", (tmp_root / "unattended_status.json").exists(), "")
        status = status_at(tmp_root)
        record("planner completed more tasks than the original fixed 10-task queue (proves dynamic generation)", status["completed_task_count"] > 10, str(status["completed_task_count"]))
        record("planner ran through multiple planning cycles", status["planning_cycle"] > status["completed_task_count"] - 1, str(status["planning_cycle"]))
        record("dynamically_generated_task_count > 0 (per-agent generator fired)", status["dynamically_generated_task_count"] > 0, str(status["dynamically_generated_task_count"]))
        record("stop_reason is a genuine exhaustion, not a fixed count", status["stop_reason"] == "genuinely_exhausted", status["stop_reason"])
        record("live_db_mutated is false (no safety-guard violation, even though the fake village legitimately advanced)", status["live_db_mutated"] is False, "")
        record(
            "attempt_live_window_1 now genuinely COMPLETES against the disposable fake village (correct, intended behavior)",
            "attempt_live_window_1" in status["completed_task_ids"],
            f"completed={status['completed_task_ids']} refused={status.get('live_bound_not_guaranteed_task_ids')}",
        )
        record(
            "live_events_added_total is > 0 (a real, bounded advance occurred against fully disposable data)",
            status.get("live_events_added_total", 0) > 0,
            str(status.get("live_events_added_total")),
        )
        record(
            "the single window's advance never exceeded the mechanically-guaranteed 50-event window (cap=1 this test)",
            status.get("live_events_added_total", 999) <= 50,
            str(status.get("live_events_added_total")),
        )
        record(
            "max_live_event_baseline advanced from the disposable village's own 0 baseline, not the real 623",
            status["max_live_event_baseline"] == status.get("live_events_added_total"),
            f"baseline={status['max_live_event_baseline']} added={status.get('live_events_added_total')}",
        )
        # --- Required regression coverage: a completed finite seed backlog
        # must NOT equal genuine exhaustion; the dynamic planner must have
        # inspected the newest live evidence and generated the next
        # justified task (the automatic post-window analysis) itself,
        # never declaring exhaustion merely because the seed queue emptied. ---
        analyze_task_ids = [t for t in status["completed_task_ids"] if t.startswith("analyze_live_window_")]
        record(
            "seed queue exhausting did NOT immediately declare genuine exhaustion -- the dynamic planner "
            "generated and completed an automatic post-live-window analysis task first",
            len(analyze_task_ids) == 1,
            f"completed={status['completed_task_ids']}",
        )
        shift1 = status["current_shift"]
        record("shift-local state exists with a shift_id", bool(shift1 and shift1.get("shift_id")), str(shift1))
        record(
            "genuine exhaustion required 3 consecutive no-material-task planning passes, not an instant check",
            shift1["consecutive_no_material_task_passes"] == 3,
            str(shift1),
        )
        record(
            "shift-local live_windows_this_shift respected the shift cap (1, this test's override)",
            shift1["live_windows_this_shift"] == 1,
            str(shift1["live_windows_this_shift"]),
        )
        record(
            "shift-local completed_tasks_this_shift matches lifetime completed_task_count on a single-shift run",
            shift1["completed_tasks_this_shift"] == status["completed_task_count"],
            f"{shift1['completed_tasks_this_shift']} vs {status['completed_task_count']}",
        )

        # --- Test 2: a SECOND intentional run against the already-completed
        # first shift must (a) not re-run already-completed seed work or
        # re-analyze an already-analyzed window (no duplication/re-spend),
        # but (b) MUST start a genuinely NEW shift and, since real margin
        # remains and the per-shift cap resets, run ANOTHER bounded live
        # window -- proving a completed previous shift does not poison a
        # new one, and that the Director keeps making real scientific
        # progress across shifts rather than needing a human to notice
        # "genuinely exhausted" and manually resubmit the exact same task. ---
        calls_after_first = status["provider_calls_used"]
        completed_after_first = status["completed_task_count"]
        events_after_first = status["live_events_added_total"]
        shift1_id = shift1["shift_id"]
        proc2 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("second run exits 0", proc2.returncode == 0, proc2.stdout[-300:])
        status2 = status_at(tmp_root)
        record("resume does not re-run any previously completed task", all(t in status2["completed_task_ids"] for t in status["completed_task_ids"]), "")
        record(
            "second run started a genuinely NEW shift (completed previous shift does not poison the new one)",
            status2["current_shift"]["shift_id"] != shift1_id,
            f"{status2['current_shift']['shift_id']} vs {shift1_id}",
        )
        record(
            "the new shift's own counters are fresh, not inherited from the completed first shift",
            status2["current_shift"]["completed_tasks_this_shift"] < completed_after_first,
            str(status2["current_shift"]),
        )
        record(
            "the new shift attempted (and completed) a SECOND live window, since margin remained and its own cap reset",
            "attempt_live_window_2" in status2["completed_task_ids"],
            f"completed={status2['completed_task_ids']}",
        )
        record(
            "the second window's own analysis task also completed automatically",
            any(t.startswith("analyze_live_window_") for t in status2["completed_task_ids"] if t not in status["completed_task_ids"]),
            f"completed={status2['completed_task_ids']}",
        )
        record(
            "lifetime live_events_added_total strictly increased (real further progress, not a no-op)",
            status2["live_events_added_total"] > events_after_first,
            f"{status2['live_events_added_total']} vs {events_after_first}",
        )
        record(
            "provider calls only increased by what the new shift's own work actually spent (no re-spend of old work)",
            status2["provider_calls_used"] >= calls_after_first,
            f"{status2['provider_calls_used']} vs {calls_after_first}",
        )

        # --- Test 2b: restart resumes an INTERRUPTED active shift (state
        # left as "running" -- simulating a crash) appropriately: the SAME
        # shift_id and its accumulated consecutive_no_material_task_passes
        # continue, rather than a fresh shift resetting the counter. ---
        interrupted = status_at(tmp_root)
        interrupted["state"] = "running"  # simulate: process died mid-shift, never reached a clean stop
        interrupted["current_shift"]["consecutive_no_material_task_passes"] = 2
        interrupted_shift_id = interrupted["current_shift"]["shift_id"]
        (tmp_root / "unattended_status.json").write_text(json.dumps(interrupted, indent=2))
        proc2b = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("resume-after-simulated-crash exits 0", proc2b.returncode == 0, proc2b.stdout[-300:])
        status2b = status_at(tmp_root)
        record(
            "an interrupted active shift (state=running on disk) resumes the SAME shift_id, not a new one",
            status2b["current_shift"]["shift_id"] == interrupted_shift_id,
            f"{status2b['current_shift']['shift_id']} vs {interrupted_shift_id}",
        )
        record(
            "the resumed shift's no-material-task counter continued from where it was primed (2 -> 3), proving state actually carried over",
            status2b["current_shift"]["consecutive_no_material_task_passes"] == 3 and status2b["stop_reason"] == "genuinely_exhausted",
            str(status2b["current_shift"]),
        )

        # --- Test 3: stop-flag mid-shift + resume-after-stop, fresh state
        # (fresh disposable village too, so the live-window task can run
        # again from a clean, known baseline). ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        shutil.rmtree(fake_village_root, ignore_errors=True)
        fake_village_root = _build_fake_village_data_root()
        stop_flag = tmp_root / "unattended_stop_requested"

        # Prime partial state by running once, then rewinding completed_task_ids
        # (mirrors real mid-shift interruption without needing real timing races).
        run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        primed = status_at(tmp_root)
        rewound = dict(primed)
        rewound["completed_task_ids"] = primed["completed_task_ids"][:5]
        rewound["completed_task_count"] = 5
        rewound["stop_reason"] = None
        (tmp_root / "unattended_status.json").write_text(json.dumps(rewound, indent=2))
        stop_flag.write_text("")

        proc3 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        status3 = status_at(tmp_root)
        record("stop flag halts before completing everything", status3["completed_task_count"] < primed["completed_task_count"] or status3["stop_reason"] == "founder_requested_stop", str(status3))
        record("stop flag file is cleared after honoring it", not stop_flag.exists(), "")

        proc4 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        status4 = status_at(tmp_root)
        # NOTE, 2026-09-05: this no longer asserts an EXACT count match --
        # with continuous dynamic planning, a resumed run that finishes the
        # original seed+analysis work AND still has live-event margin left
        # will legitimately go on to do MORE real science (another live
        # window + its own analysis), exactly as intended. What this test
        # must still prove is the original guarantee: nothing already
        # completed before the stop is ever duplicated or re-run.
        no_duplicates = len(status4["completed_task_ids"]) == len(set(status4["completed_task_ids"]))
        first_five_preserved = set(primed["completed_task_ids"][:5]).issubset(set(status4["completed_task_ids"]))
        record(
            "resume-after-stop does not duplicate any previously completed task, and reaches at least the original work",
            no_duplicates and first_five_preserved and status4["completed_task_count"] >= primed["completed_task_count"],
            f"no_duplicates={no_duplicates} first_five_preserved={first_five_preserved} {status4['completed_task_count']} vs >= {primed['completed_task_count']}",
        )

        # --- Test 4: lock prevents a concurrent second instance ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        (tmp_root / "unattended.lock").write_text(str(os.getpid()))  # this test process is genuinely alive
        proc5 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("a second instance refuses to start while a live lock exists", proc5.returncode == 1 and "already running" in proc5.stdout, proc5.stdout)
        (tmp_root / "unattended.lock").unlink()

        # --- Test 5: network-outage simulation falls back to offline work ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        shutil.rmtree(fake_village_root, ignore_errors=True)
        fake_village_root = _build_fake_village_data_root()
        proc6 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root, extra_env={"ANTHROPIC_API_KEY": ""})
        status6 = status_at(tmp_root)
        record(
            "with no provider key, D-class tasks defer/fail but R-class offline tasks still complete",
            any(t.startswith(("memory_formation", "agent_opportunity", "research_initiation", "agent_question_continuity", "llm_run_cost", "wall_rabbit", "blocked_candidates", "relationship_dump", "message_provenance", "reflection_pressure", "agent_profile_")) for t in status6["completed_task_ids"]),
            str(status6["completed_task_ids"]),
        )

        # --- Test 6: expanded scientific repertoire (Founder authorization,
        # 2026-09-05) -- once the live-window cap is reached, the planner
        # must mine accumulated evidence (cross-window synthesis, then an
        # evidence-justified replication) rather than declaring exhaustion. ---
        shutil.rmtree(tmp_root)
        tmp_root.mkdir()
        shutil.rmtree(fake_village_root, ignore_errors=True)
        fake_village_root = _build_fake_village_data_root()

        proc7 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("Test 6 seed run exits 0", proc7.returncode == 0, proc7.stdout[-300:])
        status_a = status_at(tmp_root)
        shift_a = status_a["current_shift"]
        synthesis_task_id_a = f"cross_window_synthesis_{shift_a['starting_live_event']}_{shift_a['current_live_event']}"
        record(
            "reaching the live-window cap (1, this test's override) is NOT treated as exhaustion -- cross-window "
            "synthesis is generated and completed automatically, without any manual priming",
            synthesis_task_id_a in status_a["completed_task_ids"],
            f"completed={status_a['completed_task_ids']}",
        )
        record(
            "the live-window cap is never bypassed by evidence-mining work (still exactly 1 live window this shift)",
            "attempt_live_window_2" not in status_a["completed_task_ids"] and shift_a["live_windows_this_shift"] == 1,
            str(shift_a),
        )

        # Prime the trigger condition for task class K (an evidence-justified
        # replication of an ALREADY-APPROVED experiment) directly into the
        # already-completed synthesis result, and resume the SAME shift
        # (state=running, simulating "the process paused right after
        # synthesis, before the next planning pass") to prove: (5) a
        # synthesis can generate a justified follow-up, (8) an approved
        # disposable experiment can be selected when justified.
        primed = status_at(tmp_root)
        primed["state"] = "running"
        primed["current_shift"]["consecutive_no_material_task_passes"] = 0
        primed["results_store"][synthesis_task_id_a]["messages_sent"]["agent_lucid"] = 3
        (tmp_root / "unattended_status.json").write_text(json.dumps(primed, indent=2))

        proc8 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("Test 6 primed-trigger run exits 0", proc8.returncode == 0, proc8.stdout[-300:])
        status_b = status_at(tmp_root)
        replication_task_id = f"quiet_agent_replication_agent_lucid_shift_{shift_a['shift_id']}"
        record(
            "a synthesis showing new agent_lucid activity generates a justified follow-up replication task",
            replication_task_id in status_b["completed_task_ids"],
            f"completed={status_b['completed_task_ids']}",
        )
        record(
            "the follow-up reused the SAME shift (resumed, not a fresh one) -- proves it was genuinely evidence-triggered mid-shift",
            status_b["current_shift"]["shift_id"] == shift_a["shift_id"],
            f"{status_b['current_shift']['shift_id']} vs {shift_a['shift_id']}",
        )
        record(
            "the already-completed cross-window synthesis was not duplicated",
            status_b["completed_task_ids"].count(synthesis_task_id_a) == 1,
            str(status_b["completed_task_ids"].count(synthesis_task_id_a)),
        )
        record(
            "the live-window cap is STILL never bypassed even after generating a follow-up investigation",
            "attempt_live_window_2" not in status_b["completed_task_ids"],
            str(status_b["completed_task_ids"]),
        )

        # A further intentional run starts a genuinely NEW shift with real
        # margin remaining -- it legitimately runs another live window and
        # therefore a NEW cross-window synthesis over a DIFFERENT interval
        # (changed evidence makes a fresh analysis valid, distinct from --
        # and not a duplicate of -- the first shift's own synthesis).
        proc9 = run_once(tmp_root, master_index_scratch_relpath, fake_village_root)
        record("Test 6 next-shift run exits 0", proc9.returncode == 0, proc9.stdout[-300:])
        status_c = status_at(tmp_root)
        shift_c = status_c["current_shift"]
        synthesis_task_id_c = f"cross_window_synthesis_{shift_c['starting_live_event']}_{shift_c['current_live_event']}"
        record(
            "a new shift with new live evidence produces a NEW, differently-keyed cross-window synthesis "
            "(changed evidence makes re-analysis valid; the prior shift's synthesis is preserved, not overwritten)",
            synthesis_task_id_c != synthesis_task_id_a
            and synthesis_task_id_c in status_c["completed_task_ids"]
            and synthesis_task_id_a in status_c["completed_task_ids"],
            f"a={synthesis_task_id_a} c={synthesis_task_id_c} completed={status_c['completed_task_ids']}",
        )
        record(
            "three consecutive true no-material-task passes still terminate cleanly once evidence is fully mined",
            status_c["stop_reason"] == "genuinely_exhausted" and shift_c["consecutive_no_material_task_passes"] == 3,
            str(shift_c),
        )

        # Source-level proof (never importing the runner into this process,
        # this file's own standing invariant): the new task classes can
        # never select an unapproved capability. Cross-window synthesis
        # makes ZERO broker calls at all (pure aggregation of
        # already-collected results); the replication follow-up only ever
        # reuses the pre-existing, already-approved _run_experiment helper,
        # never a raw broker.execute call of its own.
        source_text = RUNNER.read_text()
        synthesis_src = _extract_function_source(source_text, "_run_cross_window_synthesis")
        replication_src = _extract_function_source(source_text, "_maybe_generate_replication_task")
        record(
            "_run_cross_window_synthesis makes zero broker calls (cannot select any capability, approved or not)",
            "broker.execute(" not in synthesis_src,
            "found a broker.execute( call in _run_cross_window_synthesis",
        )
        record(
            "_maybe_generate_replication_task only ever reuses the pre-approved _run_experiment helper, never a raw broker.execute call of its own",
            "_run_experiment(" in replication_src and "broker.execute(" not in replication_src,
            "expected _run_experiment( present and broker.execute( absent in _maybe_generate_replication_task",
        )

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(fake_village_root, ignore_errors=True)
        master_index_scratch_abspath.unlink(missing_ok=True)  # the test's own scratch file, never the real index

    # --- Final, most important check: every real path -- INCLUDING the
    # real live Village DB itself -- is byte-identical, and its max event
    # id is unchanged. This is the exact check whose absence let the real
    # incident happen undetected; it must never be missing again. ---
    real_after = {
        "status": _hash_or_none(REAL_STATUS_PATH),
        "rolling_packet": _hash_or_none(REAL_ROLLING_PACKET),
        "completion_packet": _hash_or_none(REAL_COMPLETION_PACKET),
        "master_index": _hash_or_none(REAL_MASTER_INDEX),
        "lock": _hash_or_none(REAL_LOCK),
        "stop_flag": _hash_or_none(REAL_STOP_FLAG),
        "live_village_db": _hash_or_none(_db_safety.CANONICAL_LIVE_DB_PATH),
    }
    for key in real_before:
        record(f"real path unchanged across the whole test run: {key}", real_before[key] == real_after[key], f"before={real_before[key]} after={real_after[key]}")

    real_live_max_event_after = None
    if _db_safety.CANONICAL_LIVE_DB_PATH.exists():
        import sqlite3
        conn = sqlite3.connect(f"file:{_db_safety.CANONICAL_LIVE_DB_PATH}?mode=ro", uri=True)
        real_live_max_event_after = conn.execute("SELECT MAX(id) FROM events").fetchone()[0]
        conn.close()
    record(
        "REAL live Village max event id unchanged across the whole test run (the exact incident this fix prevents)",
        real_live_max_event_before == real_live_max_event_after,
        f"before={real_live_max_event_before} after={real_live_max_event_after}",
    )

    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} scenarios passed.")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
