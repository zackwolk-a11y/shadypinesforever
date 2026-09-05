#!/usr/bin/env python3
"""Standalone unattended Director runner.

Runs from a normal Terminal, with no Claude Code involvement, no shell
wrapper, and no `source .env`:

    caffeinate -i .venv/bin/python scripts/director_unattended.py

Every real operation this script performs goes through
``director_broker.execute()`` -- this file contains no direct database
access, no ``subprocess``, no ``eval``/``exec``, and no dynamic capability
or experiment registration of its own. It can only ever do what a
``Capability`` the broker already exposes allows, exactly as if a human
were typing the same broker CLI calls one at a time.

Resume semantics: on every startup this script reads
``.director/unattended_status.json`` (if present) and skips any
``task_id`` already recorded as completed there -- it never re-runs a
finished task or re-spends already-paid provider calls. A clean interrupt
(Ctrl+C, or `touch .director/unattended_stop_requested` from another
terminal) finishes the in-flight task, writes final status, and exits;
re-running the same command afterward resumes from the next task.

Hard boundaries, enforced structurally (nothing below can ever cross
these, because there is no code path that touches anything but the
broker): no live Village advancement, no live DB mutation, no production/
prompt/schema change, no Level 2B, no new broker capability, no new
experiment_id or diagnostic_type invented at runtime.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_broker as broker  # noqa: E402

DIRECTOR_DIR = REPO_ROOT / ".director"
STATUS_PATH = DIRECTOR_DIR / "unattended_status.json"
STOP_FLAG_PATH = DIRECTOR_DIR / "unattended_stop_requested"
LOCK_PATH = DIRECTOR_DIR / "unattended.lock"
ROLLING_PACKET_PATH = DIRECTOR_DIR / "founder_packets" / "unattended_director_shift_2026-09-04.md"

MAX_TOTAL_PROVIDER_CALLS = 96
BASELINE_MAX_EVENT = 623

_NETWORK_ERROR_HINTS = (
    "connection", "timeout", "timed out", "network", "dns", "refused",
    "unreachable", "temporarily unavailable", "apiconnectionerror",
    "connecterror", "ssl", "getaddrinfo",
)

_stop_requested = False


def _handle_signal(signum, frame) -> None:  # noqa: ANN001
    global _stop_requested
    _stop_requested = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Status persistence
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_status() -> dict[str, Any]:
    if STATUS_PATH.exists():
        return json.loads(STATUS_PATH.read_text())
    return {
        "state": "starting",
        "pid": os.getpid(),
        "started_at": _now(),
        "last_update": _now(),
        "current_task": None,
        "last_completed_task": None,
        "completed_task_ids": [],
        "deferred_network_task_ids": [],
        "failed_task_ids": [],
        "completed_task_count": 0,
        "deferred_network_count": 0,
        "provider_calls_used": 0,
        "live_db_mutated": False,
        "max_live_event_baseline": BASELINE_MAX_EVENT,
        "stop_reason": None,
    }


def save_status(status: dict[str, Any]) -> None:
    status["last_update"] = _now()
    status["pid"] = os.getpid()
    DIRECTOR_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2))
    tmp.replace(STATUS_PATH)  # atomic on the same filesystem


def append_rolling_packet(section_title: str, body: str) -> None:
    ROLLING_PACKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ROLLING_PACKET_PATH.exists():
        ROLLING_PACKET_PATH.write_text(
            "# Unattended Director Shift\n"
            f"### Started {_now()} — standalone runner, zero Claude Code involvement\n\n"
        )
    with ROLLING_PACKET_PATH.open("a") as f:
        f.write(f"\n## {section_title}\n### {_now()}\n\n{body}\n")


# ---------------------------------------------------------------------------
# Task definitions -- every run() body calls broker.execute() only.
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    status: str  # COMPLETED | DEFERRED_NETWORK | FAILED | NEW_EXPERIMENT_APPROVAL_REQUIRED
    provider_calls: int = 0
    summary: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    task_id: str
    description: str
    roadmap_phases: list[int]
    method: str  # R | D | N
    run: Callable[[], TaskResult]


def _is_network_error(broker_result: broker.BrokerResult) -> bool:
    reason = (broker_result.failure_reason or "").lower()
    return any(hint in reason for hint in _NETWORK_ERROR_HINTS)


def _run_experiment(experiment_id: str, agent_id: str, memory_content: str, memory_type: str, n_pairs: int) -> TaskResult:
    result = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {
            "experiment_id": experiment_id, "agent_id": agent_id,
            "memory_content": memory_content, "memory_type": memory_type, "n_pairs": n_pairs,
        },
    )
    if result.status == "SUCCESS":
        trials = result.result.get("trials", [])
        substantive = sum(
            1 for t in trials
            if any(a not in ("OBSERVE", "DRINK_COFFEE", "REST", "DO_NOTHING", "LISTEN_TO_MUSIC") for a in t["action_types"])
            and t["condition"] == "TREATMENT"
        )
        n_treatment = sum(1 for t in trials if t["condition"] == "TREATMENT")
        return TaskResult(
            status="COMPLETED", provider_calls=result.provider_calls,
            summary=f"{experiment_id}/{agent_id}: {substantive}/{n_treatment} TREATMENT trials substantive",
            detail={"trials": trials},
        )
    if _is_network_error(result):
        return TaskResult(status="DEFERRED_NETWORK", summary=result.failure_reason or "network error")
    return TaskResult(status="FAILED", summary=result.failure_reason or "unknown failure", detail=result.to_dict())


def _run_diagnostic(diagnostic_type: str, scope: dict[str, Any]) -> TaskResult:
    result = broker.execute("RUN_APPROVED_LEVEL_2A_DIAGNOSTIC", {"diagnostic_type": diagnostic_type, "scope": scope})
    if result.status == "SUCCESS":
        return TaskResult(
            status="COMPLETED", provider_calls=0,
            summary=f"{diagnostic_type}: {result.result.get('diagnostic_id')} {result.result.get('run_status')}",
            detail=result.result,
        )
    return TaskResult(status="FAILED", summary=result.failure_reason or "diagnostic failed", detail=result.to_dict())


def _run_read(sql: str, label: str) -> TaskResult:
    result = broker.execute("LIVE_DB_READ", {"sql": sql, "max_rows": 500})
    if result.status == "SUCCESS":
        return TaskResult(status="COMPLETED", summary=f"{label}: {result.result['row_count']} rows", detail=result.result)
    return TaskResult(status="FAILED", summary=result.failure_reason or "read failed", detail=result.to_dict())


def task_clean_wall_priming_replication() -> TaskResult:
    # Methodologically clean version of the earlier contaminated 4/4 result:
    # names no action, no mechanism, no "wall" -- states only the same real
    # underlying fact (completed research, not yet acted on) in neutral,
    # non-directive language, per the Founder's own suggested wording.
    return _run_experiment(
        "research_sharing_priming_counterfactual", "agent_roxy",
        "I finished real research on Portland's DIY scene, but the findings are still sitting "
        "with me unresolved. I haven't decided what they mean or what I should do with them.",
        "EPISODIC", 4,
    )


def task_lucid_replication_n6() -> TaskResult:
    return _run_experiment(
        "quiet_agent_thread_counterfactual", "agent_lucid",
        "I asked Optimisto how people actually land on what they want to dig into this morning "
        "-- he never answered. Still don't know what he thinks.",
        "EPISODIC", 6,
    )


def task_alien_constructed_unresolved() -> TaskResult:
    # Derived directly from Alien's own real memory #3 ("...there's a rhythm
    # to their exchange I want to map later"), reframed in explicit
    # unresolved language -- not an invented topic.
    return _run_experiment(
        "quiet_agent_thread_counterfactual", "agent_alien",
        "I still haven't gone back to map that rhythm between Optimisto and Vince at the "
        "counter -- I said I wanted to, but I never actually did.",
        "EPISODIC", 3,
    )


def task_questauthor_constructed_unresolved() -> TaskResult:
    # Derived directly from QuestAuthor's own real memory #1 ("Whether Gut
    # Check Digest is still running or archived").
    return _run_experiment(
        "quiet_agent_thread_counterfactual", "agent_questauthor",
        "I still don't know whether Gut Check Digest is still running or if it's been "
        "archived -- I never actually followed up to find out.",
        "PROJECT", 3,
    )


def task_memory_formation_trace() -> TaskResult:
    return _run_diagnostic("memory_formation_and_recall_trace", {"memory_ids": [1, 2, 3, 4, 5, 6, 7, 8]})


def task_agent_opportunity_trace() -> TaskResult:
    return _run_diagnostic("agent_opportunity_and_scheduling_trace", {"sim_day_range": [1, 6]})


def task_research_initiation_trace() -> TaskResult:
    return _run_diagnostic("research_initiation_and_completion_trace", {"agent_ids": ["agent_roxy"]})


def task_agent_question_continuity_trace() -> TaskResult:
    return _run_diagnostic("agent_question_continuity_trace", {"question_ids": [1, 2, 3, 4, 5, 6, 7]})


def task_llm_run_cost_breakdown() -> TaskResult:
    return _run_read(
        "SELECT purpose, COUNT(*) as n, SUM(input_tokens) as in_tok, SUM(output_tokens) as out_tok, "
        "SUM(estimated_cost_usd) as cost FROM llm_runs GROUP BY purpose ORDER BY n DESC",
        "llm_runs cost/purpose breakdown",
    )


def task_wall_rabbit_belief_population_recheck() -> TaskResult:
    return _run_read(
        "SELECT (SELECT COUNT(*) FROM research_wall) as wall, (SELECT COUNT(*) FROM rabbit_holes) as holes, "
        "(SELECT COUNT(*) FROM agent_beliefs) as beliefs",
        "Wall/Rabbit-Hole/Belief population recheck",
    )


TASKS: list[Task] = [
    Task("clean_wall_priming_replication", "Methodologically clean replication of the Roxy Wall-priming test", [6, 10], "D", task_clean_wall_priming_replication),
    Task("lucid_replication_n6", "Backlog #5: Lucid unresolved-memory replication at n=6 pairs", [1, 4, 5], "D", task_lucid_replication_n6),
    Task("alien_constructed_unresolved", "Backlog #6: Alien, constructed unresolved memory from her own real content", [1, 4], "D", task_alien_constructed_unresolved),
    Task("questauthor_constructed_unresolved", "Backlog #6: QuestAuthor, constructed unresolved memory from her own real content", [1, 4], "D", task_questauthor_constructed_unresolved),
    Task("memory_formation_trace_all8", "Backlog #8: memory_formation_and_recall_trace across all 8 real memories", [3], "R", task_memory_formation_trace),
    Task("agent_opportunity_trace_full", "Backlog #11: agent_opportunity_and_scheduling_trace, days 1-6", [1, 9], "R", task_agent_opportunity_trace),
    Task("research_initiation_trace_roxy", "Backlog #7-class: research_initiation_and_completion_trace for agent_roxy", [3], "R", task_research_initiation_trace),
    Task("agent_question_continuity_trace_all7", "agent_question_continuity_trace across all 7 real questions", [2, 4], "R", task_agent_question_continuity_trace),
    Task("llm_run_cost_breakdown", "Backlog #12/#24: consolidated real-call cost/purpose breakdown", [18], "R", task_llm_run_cost_breakdown),
    Task("wall_rabbit_belief_recheck", "Backlog #21: Wall/Rabbit-Hole/Belief population recheck", [6, 7, 8], "R", task_wall_rabbit_belief_population_recheck),
]


# ---------------------------------------------------------------------------
# Safety pre/post checks -- every one goes through the broker too.
# ---------------------------------------------------------------------------


def safety_snapshot() -> dict[str, Any]:
    fp = broker.execute("LIVE_DB_FINGERPRINT", {})
    integ = broker.execute("CHECK_LIVE_DB_INTEGRITY", {})
    return {
        "sha256": fp.result.get("sha256"), "max_event_id": fp.result.get("max_event_id"),
        "current_day": fp.result.get("current_day"), "current_period": fp.result.get("current_period"),
        "is_paused": fp.result.get("is_paused"), "integrity_ok": integ.result.get("healthy"),
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def acquire_lock() -> bool:
    if LOCK_PATH.exists():
        try:
            existing_pid = int(LOCK_PATH.read_text().strip())
            os.kill(existing_pid, 0)  # raises if not alive; does not actually signal-kill
            return False  # a live instance is already running
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # stale or unreadable lock -- safe to take over
    DIRECTOR_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        if LOCK_PATH.exists() and LOCK_PATH.read_text().strip() == str(os.getpid()):
            LOCK_PATH.unlink()
    except OSError:
        pass


def main() -> int:
    if "--status" in sys.argv:
        if STATUS_PATH.exists():
            print(STATUS_PATH.read_text())
        else:
            print(json.dumps({"state": "never_started"}))
        return 0

    if not acquire_lock():
        print("Another unattended Director instance is already running (lock held). Exiting.")
        return 1

    try:
        before = safety_snapshot()
        if before["max_event_id"] != BASELINE_MAX_EVENT or not before["is_paused"]:
            print(f"REFUSING TO START: live baseline changed unexpectedly: {before}")
            return 1
        if not before["integrity_ok"]:
            print(f"REFUSING TO START: live DB integrity check failed: {before}")
            return 1

        status = load_status()
        status["state"] = "running"
        status["stop_reason"] = None
        save_status(status)
        append_rolling_packet(
            "Session start" if status["completed_task_count"] == 0 else "Session resumed",
            f"Baseline: {before}\nAlready completed: {status['completed_task_ids']}\n"
            f"Provider calls used so far this shift: {status['provider_calls_used']}",
        )

        for task in TASKS:
            if _stop_requested or STOP_FLAG_PATH.exists():
                status["state"] = "stopped"
                status["stop_reason"] = "founder_requested_stop"
                save_status(status)
                STOP_FLAG_PATH.unlink(missing_ok=True)
                print("Stop requested. Exiting cleanly.")
                return 0

            if task.task_id in status["completed_task_ids"] or task.task_id in status["failed_task_ids"]:
                continue

            if status["provider_calls_used"] >= MAX_TOTAL_PROVIDER_CALLS and task.method in ("D", "N"):
                status["state"] = "stopped"
                status["stop_reason"] = "provider_budget_exhausted"
                save_status(status)
                append_rolling_packet("Stopped", f"Provider budget ({MAX_TOTAL_PROVIDER_CALLS}) exhausted before task {task.task_id}.")
                print(f"Provider budget exhausted ({status['provider_calls_used']}/{MAX_TOTAL_PROVIDER_CALLS}). Stopping cleanly.")
                return 0

            status["current_task"] = task.task_id
            save_status(status)
            print(f"[{_now()}] running {task.task_id} ({task.method}) -- {task.description}")

            result = task.run()

            status["provider_calls_used"] += result.provider_calls
            status["current_task"] = None

            if result.status == "COMPLETED":
                status["completed_task_ids"].append(task.task_id)
                status["completed_task_count"] += 1
                status["last_completed_task"] = task.task_id
                append_rolling_packet(f"Task completed: {task.task_id}", f"Method: {task.method}\nRoadmap phases: {task.roadmap_phases}\nResult: {result.summary}\n\n```json\n{json.dumps(result.detail, indent=2, default=str)[:8000]}\n```")
            elif result.status == "DEFERRED_NETWORK":
                if task.task_id not in status["deferred_network_task_ids"]:
                    status["deferred_network_task_ids"].append(task.task_id)
                status["deferred_network_count"] += 1
                append_rolling_packet(f"DEFERRED_NETWORK: {task.task_id}", f"Reason: {result.summary}\nWill retry on next resume.")
                print(f"  DEFERRED_NETWORK: {result.summary}")
            else:  # FAILED or NEW_EXPERIMENT_APPROVAL_REQUIRED
                status["failed_task_ids"].append(task.task_id)
                append_rolling_packet(f"{result.status}: {task.task_id}", f"Reason: {result.summary}")
                print(f"  {result.status}: {result.summary}")

            save_status(status)

            after = safety_snapshot()
            if after["sha256"] != before["sha256"] or after["max_event_id"] != BASELINE_MAX_EVENT:
                status["state"] = "stopped"
                status["stop_reason"] = "SAFETY_VIOLATION_live_db_changed"
                status["live_db_mutated"] = True
                save_status(status)
                append_rolling_packet("SAFETY STOP", f"Live DB changed unexpectedly after {task.task_id}. Before={before}, After={after}. Halting immediately.")
                print("SAFETY VIOLATION: live DB changed. Halting immediately.")
                return 2

        status["state"] = "stopped"
        status["stop_reason"] = "backlog_exhausted"
        save_status(status)
        append_rolling_packet("Backlog exhausted", f"All {len(TASKS)} coded tasks finished or failed. Completed: {status['completed_task_count']}. Deferred (network): {status['deferred_network_count']}. Failed: {len(status['failed_task_ids'])}.")
        print("All coded tasks finished. See the rolling packet and status file.")
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
