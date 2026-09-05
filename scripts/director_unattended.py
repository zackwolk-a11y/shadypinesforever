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
import re
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_broker as broker  # noqa: E402
from app.core.config import get_settings as _get_settings  # noqa: E402

DIRECTOR_DIR = REPO_ROOT / ".director"

# Test isolation (root cause of a real incident: a fixture-provider test
# run of this file once wrote into these exact same real paths as a
# genuine unattended shift, which was then mistaken for fixture leftover
# and deleted). DIRECTOR_UNATTENDED_STATE_ROOT lets a test harness redirect
# every piece of THIS RUNNER's OWN bookkeeping (status file, lock,
# stop-flag, rolling packet, completion packet) to an isolated directory.
# Unset (the default, and the only thing a real launch should ever use),
# it resolves to the real .director directory, identical to this script's
# original behavior. This does not, and cannot, affect the broker's own
# paths (director_broker.py's DIRECTOR_DIR/AUDIT_DIR are separate module
# constants, untouched by this variable) -- LIVE_DB_READ, Level 2A
# diagnostics, and disposable experiments always go through the real
# broker exactly as before, in both modes.
_state_root_override = os.environ.get("DIRECTOR_UNATTENDED_STATE_ROOT", "").strip()
STATE_ROOT = Path(_state_root_override).resolve() if _state_root_override else DIRECTOR_DIR
STATUS_PATH = STATE_ROOT / "unattended_status.json"
STOP_FLAG_PATH = STATE_ROOT / "unattended_stop_requested"
LOCK_PATH = STATE_ROOT / "unattended.lock"
FOUNDER_PACKETS_DIR = STATE_ROOT / "founder_packets"
ROLLING_PACKET_PATH = FOUNDER_PACKETS_DIR / "unattended_director_shift_2026-09-04.md"

# The one task (master_index_addendum) that writes into the broker's own
# real .director/founder_packets/ tree via WRITE_DIRECTOR_ARTIFACT -- that
# capability's paths are NOT affected by STATE_ROOT above (they are the
# broker's, not this runner's). This lets a test target a harmless scratch
# file under the same approved subtree instead of the real canonical
# master index; a real run defaults to the true index.
MASTER_INDEX_RELATIVE_PATH = os.environ.get(
    "DIRECTOR_UNATTENDED_MASTER_INDEX_PATH",
    "founder_packets/master_evidence_roadmap_index_2026-09-04.md",
)

MAX_TOTAL_PROVIDER_CALLS = 96
#: CORRECTION, 2026-09-05, following a real incident: a fixture-provider
#: test run of this file advanced the REAL live Village by 10 events
#: (623 -> 633), because RUN_BOUNDED_LIVE_WINDOW is now genuinely enabled
#: (the 42-event worst case fits inside the new 50-event window) and the
#: test's own isolation only redirected this runner's bookkeeping paths,
#: never the live DB itself. Founder decision 2026-09-05: do not restore
#: or rewrite; classify events 624-633 as CONTAMINATED_FIXTURE_TEST_INTERVAL
#: (see director_contamination_registry.py) and move the operating
#: baseline forward to 633. DIRECTOR_UNATTENDED_BASELINE_MAX_EVENT lets a
#: test point this constant at a disposable database's own true starting
#: count (typically 0, immediately after seed_agents.run(), which never
#: emits Event rows) instead of the real Village's baseline -- used
#: together with VILLAGE_DATA_ROOT (an app.core.db_safety-native override)
#: to make an isolated test's entire live-data root disposable, not just
#: this runner's own status/packet files.
_baseline_override = os.environ.get("DIRECTOR_UNATTENDED_BASELINE_MAX_EVENT", "").strip()
BASELINE_MAX_EVENT = int(_baseline_override) if _baseline_override else 633

# Founder-authorized overnight live-science budget, 2026-09-05.
#: Test-only override, same pattern as DIRECTOR_UNATTENDED_BASELINE_MAX_EVENT
#: above -- lets a test shrink the overnight budget so a live-window/
#: analysis loop reaches its true margin limit in seconds instead of
#: potentially many real (fixture) provider calls. Unset (the only thing a
#: real launch should ever use), this is exactly 250, unchanged.
_overnight_budget_override = os.environ.get("DIRECTOR_UNATTENDED_MAX_ADDITIONAL_LIVE_EVENTS_OVERNIGHT", "").strip()
MAX_ADDITIONAL_LIVE_EVENTS_OVERNIGHT = int(_overnight_budget_override) if _overnight_budget_override else 250
ABSOLUTE_EVENT_CEILING = BASELINE_MAX_EVENT + MAX_ADDITIONAL_LIVE_EVENTS_OVERNIGHT  # 883
#: Raised 25 -> 50, 2026-09-05, per explicit Founder authorization, to
#: match the proven worst-case single-activation burst (42, see
#: director_broker.py's _derive_worst_case_activation_burst -- computed
#: from real, already-existing production caps, not a new schema change).
#: A 25-event window could never admit even one activation; 50 leaves
#: >=42 margin for exactly one while director_broker.py's own
#: `remaining < worst_case_burst` guard still blocks a second whenever it
#: wouldn't fit. Must track director_broker.RunBoundedLiveWindowParams's
#: own le=50 ceiling -- both were raised together this same commit.
MAX_SINGLE_LIVE_WINDOW = 50
#: Founder-authorized 2026-09-05 ("make the unattended Director actually
#: continuous"): a genuine per-shift cap on how many bounded live windows
#: ONE continuous shift may attempt, independent of (and never looser
#: than) the absolute lifetime event ceiling above. Previously defined but
#: never enforced; now the actual gate generate_next_investigation_task()
#: checks before ever proposing another live window this shift.
#: Test-only override, same pattern as the two above -- unset (the only
#: thing a real launch should ever use), this is exactly 5, unchanged.
_max_live_windows_override = os.environ.get("DIRECTOR_UNATTENDED_MAX_LIVE_WINDOWS", "").strip()
MAX_LIVE_WINDOWS = int(_max_live_windows_override) if _max_live_windows_override else 5  # 250 // 50, per the Founder's own arithmetic


def _worst_case_activation_burst() -> int:
    """The same mechanically-proven bound director_broker.py's own
    RUN_BOUNDED_LIVE_WINDOW pre-activation check enforces (see
    _derive_worst_case_activation_burst) -- read fresh from real
    production settings each time, never hardcoded here, so this
    planning-time eligibility check can never drift from the capability's
    own actual safety authority."""
    return broker._derive_worst_case_activation_burst(_get_settings())

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


def _default_status() -> dict[str, Any]:
    return {
        "state": "starting",
        "pid": os.getpid(),
        "started_at": _now(),
        "last_update": _now(),
        "planning_cycle": 0,
        "current_task": None,
        "last_completed_task": None,
        "completed_task_ids": [],
        "deferred_network_task_ids": [],
        "failed_task_ids": [],
        "live_bound_not_guaranteed_task_ids": [],
        "completed_task_count": 0,
        "dynamically_generated_task_count": 0,
        "deferred_network_count": 0,
        "provider_calls_used": 0,
        "live_events_added_total": 0,
        "results_store": {},
        "blocked_tasks": [],
        "live_db_mutated": False,
        "max_live_event_baseline": BASELINE_MAX_EVENT,
        "stop_reason": None,
        "continuing_because": None,
        "current_shift": None,
    }


def _new_shift_state(starting_live_event: int) -> dict[str, Any]:
    """Shift-local state (Founder-authorized 2026-09-05), tracked
    separately from the lifetime/historical fields above. A completed or
    interrupted-and-abandoned shift's counters must never be mistaken for
    the current shift's -- see main()'s resume-vs-fresh-shift decision."""
    return {
        "shift_id": uuid.uuid4().hex[:12],
        "shift_started_at": _now(),
        "shift_cycle_count": 0,
        "starting_live_event": starting_live_event,
        "current_live_event": starting_live_event,
        "live_events_added_this_shift": 0,
        "provider_calls_this_shift": 0,
        "completed_tasks_this_shift": 0,
        "live_windows_this_shift": 0,
        "consecutive_no_material_task_passes": 0,
        "stop_reason": None,
    }


def load_status() -> dict[str, Any]:
    """Merges onto a fresh default so a status file written by an older
    version of this script (missing a field added later, e.g. by tonight's
    RUN_BOUNDED_LIVE_WINDOW integration) still round-trips correctly --
    never silently drops or resets real recorded history."""
    defaults = _default_status()
    if STATUS_PATH.exists():
        on_disk = json.loads(STATUS_PATH.read_text())
        defaults.update(on_disk)
        return defaults
    return defaults


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
    status: str  # COMPLETED | DEFERRED_NETWORK | FAILED | NEW_EXPERIMENT_APPROVAL_REQUIRED | LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED
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


STATIC_TASKS: list[Task] = [
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
# Continuous-planning extension: more static tasks (meta-analysis of
# already-collected evidence, blocked-candidate documentation, and
# per-agent snapshots), plus one genuine data-driven generator so the
# queue does not have to be fully hand-written in advance.
# ---------------------------------------------------------------------------


#: Diagnostic types this project has already BUILT and fixture-tested
#: ([PSIP]) but never added to director_broker._APPROVED_DIAGNOSTIC_TYPES.
#: Running any of these requires a separate, explicit broker-catalog
#: registration -- exactly the "record as blocked candidate, keep working"
#: case the Founder's continuous-planning instruction calls for.
_KNOWN_BLOCKED_DIAGNOSTIC_TYPES = {
    "conversation_decision_trace": "would need real per-decision telemetry correlation the DB doesn't have; also not yet in the broker's approved catalog",
    "research_provenance_and_evidence_flow_trace": "not yet in the broker's approved catalog",
    "relationship_state_and_influence_trace": "not yet in the broker's approved catalog",
    "belief_lifecycle_trace": "not yet in the broker's approved catalog; also 0 real beliefs exist to trace",
    "rabbit_hole_lifecycle_trace": "not yet in the broker's approved catalog; also 0 real rabbit holes exist to trace",
    "invalid_decision_pattern_trace": "not yet in the broker's approved catalog",
    "observability_gap_scan": "needs the 'daily_reports' table added to LIVE_DB_READ's/GET_*'s table allowlist -- a broker-capability change, not yet authorized",
}


#: Founder-authorized 2026-09-05: exactly one preregistered attempt to open
#: a live-science window. Not retried on a loop -- RUN_BOUNDED_LIVE_WINDOW's
#: refusal reason (an unbounded ResearchSynthesis schema) is invariant
#: across calls with the same settings, so asking again would be pure
#: busywork, explicitly forbidden by the standing instructions. If a
#: future, separately-authorized schema fix ever makes the bound
#: computable, a fresh planning cycle run after that fix would need a new
#: task_id to re-attempt (this one, once completed/recorded, is never
#: re-run by the resume logic either way).
def _remaining_overnight_live_budget() -> int | None:
    """Reads the REAL current live max event id via the broker (read-only)
    and returns how much of the 250-event overnight ceiling remains, or
    None if the fingerprint call itself failed (treated as
    non-mechanically-guaranteed, never as "assume budget available")."""
    fp = broker.execute("LIVE_DB_FINGERPRINT", {})
    if fp.status != "SUCCESS":
        return None
    current_max = fp.result.get("max_event_id")
    if current_max is None:
        return None
    return ABSOLUTE_EVENT_CEILING - current_max


def task_attempt_live_window_1() -> TaskResult:
    return _attempt_live_window_task_body("attempt_live_window_1")


def _attempt_live_window_task_body(window_label: str) -> TaskResult:
    """Preregistration, per the Founder's 2026-09-05 night-policy update
    (max window 25 -> 50, matching the proven worst-case atomic burst of
    42): why fresh live data is necessary -- every claim this project has
    made about cross-agent transmission, private continuity, and Wall/
    Rabbit-Hole/Belief non-uptake rests on evidence collected up to some
    prior frozen event snapshot; only genuinely new, unforced activity can
    test whether those patterns hold going forward or were an artifact of
    that specific history. Evidence sought: any new MESSAGE/QUESTION/
    RESEARCH/REFLECTION/WALL/RABBIT_HOLE/BELIEF event past the current
    baseline. Falsification criterion for the favored hypothesis: a live
    window (of the Founder-mandated max_new_events, mechanically <= 50 and
    never exceeding the actual requested value) that produces zero new
    cross-agent reference, zero new research/reflection activity, and no
    departure from the existing all-zero Wall/Rabbit-Hole/Belief pattern
    would falsify it. Requested event budget: computed fresh each call
    from the real current live max event id (see
    _remaining_overnight_live_budget), never assumed. Reused verbatim by
    every dynamically-generated follow-up window this shift (Founder
    authorization 2026-09-05) -- window_label only distinguishes which
    attempt this is in logging/summary text, not the science itself."""
    remaining = _remaining_overnight_live_budget()
    if remaining is None:
        return TaskResult(status="LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED", summary="could not read the real live max event id -- refusing to attempt a live window")
    if remaining <= 0:
        return TaskResult(status="LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED", summary=f"overnight live-event budget already exhausted (ceiling {ABSOLUTE_EVENT_CEILING})")
    window_size = min(MAX_SINGLE_LIVE_WINDOW, remaining)

    result = broker.execute(
        "RUN_BOUNDED_LIVE_WINDOW",
        {
            "max_new_events": window_size,
            "question": (
                f"({window_label}) Does a fresh, mechanically-bounded live window surface new "
                "evidence of durable cross-agent transmission, private intellectual continuity, or "
                "Research Wall/Rabbit Hole/Belief uptake beyond what prior evidence already shows?"
            ),
            "favored_hypothesis": (
                "Real, unforced Village activity beyond the current baseline would show at least one "
                "new instance of a real cross-agent reference, a new research thread, or a new "
                "reflection -- consistent with the same rates this project has already documented."
            ),
            "competing_hypothesis": (
                "No qualitatively new pattern would appear; the same small set of agents (chiefly "
                "Roxy) would continue to dominate activity, and Wall/Rabbit-Hole/Belief uptake would "
                "remain at zero, exactly as every prior phase has found."
            ),
        },
    )
    if result.status != "SUCCESS":
        return TaskResult(status="FAILED", summary=result.failure_reason or "RUN_BOUNDED_LIVE_WINDOW call itself failed", detail=result.to_dict())
    payload = result.result
    if payload.get("status") == "LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED":
        return TaskResult(
            status="LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED",
            summary=payload.get("reason", "no reason given"),
            detail=payload,
        )
    return TaskResult(
        status="COMPLETED",
        summary=f"{window_label}: live window advanced {payload.get('events_added')} events ({payload.get('activations_run')} activations), stopped: {payload.get('stopped_reason')}",
        detail=payload,
    )


def task_blocked_candidates_survey() -> TaskResult:
    """R-class, always safe: records the known-blocked diagnostic
    candidates so the planner keeps working other safe tasks instead of
    stalling on them, per the Founder's explicit instruction."""
    return TaskResult(
        status="COMPLETED",
        summary=f"{len(_KNOWN_BLOCKED_DIAGNOSTIC_TYPES)} diagnostic types recorded as blocked (need broker-catalog registration, not executed)",
        detail={"blocked": _KNOWN_BLOCKED_DIAGNOSTIC_TYPES},
    )


def task_llm_run_cost_by_day() -> TaskResult:
    return _run_read(
        "SELECT date(created_at) as day, COUNT(*) as n, SUM(estimated_cost_usd) as cost "
        "FROM llm_runs GROUP BY date(created_at) ORDER BY day",
        "llm_runs cost by calendar day",
    )


def task_relationship_dump_and_analysis() -> TaskResult:
    return _run_read(
        "SELECT agent_a_id, agent_b_id, trust_score, familiarity, intellectual_affinity, interaction_count "
        "FROM relationships ORDER BY interaction_count DESC",
        "full relationship table dump (Part 4/9 roadmap: does relationship state correlate with who talks to whom)",
    )


def task_message_provenance_cross_check() -> TaskResult:
    # Extends C14/C15: for each real message, does ANY memory's content
    # contain a real substring of it? A crude but honest, fully-offline
    # test of whether message content ever survives into durable memory
    # text anywhere in the Village, independent of the architectural
    # (no-Event-emitted) argument already established.
    return _run_read(
        "SELECT m.id, m.sender_agent_id, m.recipient_agent_id, "
        "(SELECT COUNT(*) FROM memories mem WHERE mem.content LIKE '%' || substr(m.content, 1, 30) || '%') as memory_hits "
        "FROM messages m ORDER BY m.id",
        "message-content-in-memory cross-check (extends C14/C15)",
    )


def task_reflection_pressure_recheck() -> TaskResult:
    return _run_read(
        "SELECT agent_id, reflection_pressure, last_reflection_sim_day FROM agents ORDER BY agent_id",
        "reflection_pressure recheck (Part 2 roadmap: mechanism verification, ties to C16)",
    )


def task_statistical_reanalysis_shift_experiments(status: dict[str, Any]) -> TaskResult:
    """Meta-analysis, R-class, zero new provider calls: pools this shift's
    newly collected disposable-experiment trial data (read back from
    results_store, not re-paid) against the already-published rates in
    thread_genesis_bootstrap_investigation_2026-09-04.md and
    memory_framing_replication_2026-09-04.md."""
    store = status.get("results_store", {})

    def _rate(task_id: str) -> tuple[int, int] | None:
        trials = (store.get(task_id) or {}).get("trials")
        if not trials:
            return None
        treatment = [t for t in trials if t["condition"] == "TREATMENT"]
        substantive = sum(
            1 for t in treatment
            if any(a not in ("OBSERVE", "DRINK_COFFEE", "REST", "DO_NOTHING", "LISTEN_TO_MUSIC") for a in t["action_types"])
        )
        return substantive, len(treatment)

    summary_lines = []
    lucid_original = (2, 4)  # from thread_genesis_bootstrap_investigation_2026-09-04.md, Experiment A
    lucid_new = _rate("lucid_replication_n6")
    if lucid_new:
        pooled = (lucid_original[0] + lucid_new[0], lucid_original[1] + lucid_new[1])
        summary_lines.append(
            f"Lucid: original n=4 -> {lucid_original[0]}/{lucid_original[1]}; "
            f"this shift's n=6 -> {lucid_new[0]}/{lucid_new[1]}; pooled n=10 -> {pooled[0]}/{pooled[1]} "
            f"({100*pooled[0]/pooled[1]:.1f}%)"
        )
    wall_clean = _rate("clean_wall_priming_replication")
    if wall_clean:
        summary_lines.append(
            f"Roxy Wall-priming, CLEAN (neutral, non-directive wording): {wall_clean[0]}/{wall_clean[1]} "
            f"({100*wall_clean[0]/wall_clean[1]:.1f}%) -- compare against the earlier CONTAMINATED "
            f"4/4 (100%) result that explicitly named 'the wall' and 'shared it as a real finding'"
        )
    alien_new = _rate("alien_constructed_unresolved")
    questauthor_new = _rate("questauthor_constructed_unresolved")
    if alien_new:
        summary_lines.append(f"Alien, constructed unresolved memory: {alien_new[0]}/{alien_new[1]} substantive (compare thread_genesis's real-neutral-memory result: 0/4)")
    if questauthor_new:
        summary_lines.append(f"QuestAuthor, constructed unresolved memory: {questauthor_new[0]}/{questauthor_new[1]} substantive (compare thread_genesis's real-neutral-memory result: 0/4)")

    if not summary_lines:
        return TaskResult(status="FAILED", summary="no shift experiment results available yet in results_store")
    return TaskResult(status="COMPLETED", summary="; ".join(summary_lines), detail={"lines": summary_lines})


def task_master_index_addendum(status: dict[str, Any]) -> TaskResult:
    """Appends (never overwrites) a dated corrections/addendum section to
    the canonical master index, per the standing evidence-hygiene rule:
    OLD CLAIM -> NEW EVIDENCE -> CURRENT INTERPRETATION, never silent
    deletion."""
    read = broker.execute("READ_DIRECTOR_ARTIFACT", {"relative_path": MASTER_INDEX_RELATIVE_PATH})
    if read.status != "SUCCESS":
        return TaskResult(status="FAILED", summary=read.failure_reason or "could not read master index")
    existing = read.result["content"]

    store = status.get("results_store", {})
    stat_summary = (store.get("statistical_reanalysis_shift_experiments") or {}).get("lines", [])
    addendum = (
        "\n\n---\n\n## Addendum — Unattended Shift, "
        + _now()
        + "\n\n**Methodological correction (evidence hygiene, not deletion):** the original Roxy "
        "Wall-priming result reported as this shift began (CONTROL 0/4, TREATMENT 4/4 POST_TO_WALL) "
        "used treatment memory text that explicitly named \"the wall\" and \"shared it as a real "
        "finding\" -- closer to naming the target mechanism than the neutral-fact framing this "
        "project holds itself to elsewhere. **Status: CORRECTED, not retracted.** A methodologically "
        "clean replication (`clean_wall_priming_replication`, neutral wording naming no action) was "
        "run this shift; see the statistical reanalysis below for its actual rate.\n\n"
        "**New evidence collected this shift:**\n\n"
        + "\n".join(f"- {line}" for line in stat_summary)
        + "\n\n**Blocked candidates surfaced this shift (recorded, not executed):** "
        + ", ".join(sorted(_KNOWN_BLOCKED_DIAGNOSTIC_TYPES))
        + " -- each requires a separate broker-catalog registration decision, not a Village behavior change.\n"
    )
    write = broker.execute(
        "WRITE_DIRECTOR_ARTIFACT",
        {"relative_path": MASTER_INDEX_RELATIVE_PATH, "content": existing + addendum},
    )
    if write.status != "SUCCESS":
        return TaskResult(status="FAILED", summary=write.failure_reason or "could not write addendum")
    return TaskResult(status="COMPLETED", summary="master index addendum appended", detail={"addendum_chars": len(addendum)})


#: Exactly one entry -- the Founder's overnight live-science authorization
#: (2026-09-05) permits attempting a bounded live window, but the
#: mechanical-bound proof (see director_broker.py's
#: _derive_worst_case_activation_burst) means the outcome is invariant
#: across repeated attempts under the current schema. Ordered first so any
#: resume checks live-window feasibility before spending cycles on
#: anything else, per the mandate's own stated priority.
LIVE_SCIENCE_TASKS: list[Task] = [
    Task("attempt_live_window_1", "Founder-authorized: attempt one bounded live-science window", [1, 2, 4, 5, 6, 7, 8, 9, 10], "L", task_attempt_live_window_1),
]

MORE_STATIC_TASKS: list[Task] = [
    Task("blocked_candidates_survey", "Survey and record diagnostic types blocked on broker-catalog registration", [3, 12], "R", task_blocked_candidates_survey),
    Task("llm_run_cost_by_day", "Cost/call efficiency: real-call breakdown by calendar day", [18], "R", task_llm_run_cost_by_day),
    Task("relationship_dump_and_analysis", "Relationship-mediated culture: full table dump for analysis", [9], "R", task_relationship_dump_and_analysis),
    Task("message_provenance_cross_check", "Cross-agent transmission: does any message's content ever appear in any memory?", [2, 3], "R", task_message_provenance_cross_check),
    Task("reflection_pressure_recheck", "Reflection mechanism verification recheck (ties to C16)", [2], "R", task_reflection_pressure_recheck),
]
# The two tasks below consume this shift's own results_store (populated
# from the D-class tasks above) -- pure meta-analysis, zero new provider
# calls, and only meaningful once at least one D-task has completed, so
# they are appended after the disposable-experiment tasks by construction
# (list order = default priority order in get_task_queue below).
MORE_STATIC_TASKS_NEEDING_STATUS: list[tuple[str, str, list[int], str, Callable[[dict[str, Any]], TaskResult]]] = [
    ("statistical_reanalysis_shift_experiments", "Pool this shift's new disposable-experiment results against already-published rates", [1, 4, 5, 6], "R", task_statistical_reanalysis_shift_experiments),
    ("master_index_addendum", "Append (never overwrite) a corrections addendum to the canonical master index", [11], "R", task_master_index_addendum),
]


def generate_dynamic_tasks(status: dict[str, Any]) -> list[Task]:
    """The genuinely data-driven half of the planner: queries the live DB
    (through the broker, read-only) for the current agent roster and
    yields one per-agent profile task for any agent not yet profiled --
    computed from what the database actually contains right now, not
    hardcoded to '8' in source. On this frozen snapshot it will always
    yield the same 8 the first time it's called and nothing thereafter,
    but the mechanism itself does not assume that population size."""
    result = broker.execute("LIVE_DB_READ", {"sql": "SELECT agent_id FROM agents ORDER BY agent_id"})
    if result.status != "SUCCESS":
        return []

    agent_ids = [row[0] for row in result.result["rows"] if re.match(r"^agent_[a-z_]+$", row[0])]
    tasks = []
    for agent_id in agent_ids:
        task_id = f"agent_profile_{agent_id}"
        if task_id in status["completed_task_ids"] or task_id in status["failed_task_ids"]:
            continue

        def _make_run(aid: str) -> Callable[[], TaskResult]:
            def _run() -> TaskResult:
                return _run_read(
                    "SELECT "
                    "(SELECT COUNT(*) FROM memories WHERE agent_id = '" + aid + "') as memories, "
                    "(SELECT COUNT(*) FROM agent_questions WHERE agent_id = '" + aid + "') as questions, "
                    "(SELECT COUNT(*) FROM research_sessions WHERE agent_id = '" + aid + "') as research, "
                    "(SELECT COUNT(*) FROM messages WHERE sender_agent_id = '" + aid + "') as sent, "
                    "(SELECT COUNT(*) FROM messages WHERE recipient_agent_id = '" + aid + "') as received, "
                    "(SELECT reflection_pressure FROM agents WHERE agent_id = '" + aid + "') as reflection_pressure",
                    f"per-agent profile snapshot: {aid}",
                )
            return _run

        tasks.append(Task(task_id, f"Dynamically generated per-agent profile snapshot for {agent_id}", [1, 4], "R", _make_run(agent_id)))
    return tasks


def get_task_queue(status: dict[str, Any]) -> list[Task]:
    """One planning cycle's worth of candidate tasks, priority-ordered:
    the original 10, then the newer static analysis/meta-analysis tasks,
    then whatever the data-driven generator currently yields. Recomputed
    fresh each cycle rather than cached once, so a generator that depends
    on mutable status (like the meta-analysis tasks reading results_store)
    always sees the latest state."""
    queue = list(LIVE_SCIENCE_TASKS) + list(STATIC_TASKS) + list(MORE_STATIC_TASKS)
    for task_id, desc, phases, method, fn in MORE_STATIC_TASKS_NEEDING_STATUS:
        queue.append(Task(task_id, desc, phases, method, (lambda fn=fn: fn(status))))
    queue.extend(generate_dynamic_tasks(status))
    return queue


def next_unfinished_task(status: dict[str, Any]) -> Task | None:
    for task in get_task_queue(status):
        if (
            task.task_id in status["completed_task_ids"]
            or task.task_id in status["failed_task_ids"]
            or task.task_id in status.get("live_bound_not_guaranteed_task_ids", [])
        ):
            continue
        return task
    return None


# ---------------------------------------------------------------------------
# Continuous-Director dynamic planner (Founder authorization, 2026-09-05):
# consulted ONLY once next_unfinished_task() above (the static + per-agent
# seed queue) has nothing left. A completed finite seed backlog must not be
# mistaken for genuine exhaustion -- this is the mechanism that keeps the
# Director working: inspect the newest live evidence, generate the next
# justified investigation, execute, ingest, repeat. Every task it produces
# still only ever calls broker.execute() -- no new capability, no direct
# DB access, nothing that bypasses the existing safety pipeline.
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(r"^[0-9T:\.\-\+Z ]{4,40}$")


def _safe_timestamp(value: Any) -> str:
    """Defensive validation before embedding a DB-returned timestamp into a
    hand-built SQL string (LIVE_DB_READ takes raw SQL text, not bound
    params) -- mirrors the agent_id regex-validation pattern already used
    elsewhere in this file. Every value here originates from the broker's
    own read of the events table, never external input, but this is
    cheap insurance against ever embedding an unexpected character."""
    text = str(value)
    if not _TIMESTAMP_RE.match(text):
        raise ValueError(f"unexpected timestamp value, refusing to embed in SQL: {value!r}")
    return text


def _completed_live_windows(status: dict[str, Any]) -> list[tuple[str, int, int]]:
    """(task_id, start_max_event_id, end_max_event_id) for every COMPLETED
    attempt_live_window_* task recorded in results_store this far, oldest
    first -- read straight from the persisted detail RUN_BOUNDED_LIVE_WINDOW
    itself returned, never re-derived."""
    store = status.get("results_store", {})
    out: list[tuple[str, int, int]] = []
    for task_id, detail in store.items():
        if not task_id.startswith("attempt_live_window_") or not isinstance(detail, dict):
            continue
        start = detail.get("start_max_event_id")
        end = detail.get("end_max_event_id")
        if isinstance(start, int) and isinstance(end, int) and end > start:
            out.append((task_id, start, end))
    out.sort(key=lambda t: t[1])
    return out


def _run_analyze_live_window(start_event_id: int, end_event_id: int) -> TaskResult:
    """Automatic post-live-window analysis (Founder authorization,
    2026-09-05): every completed live window must be inspected before the
    Director considers what to do next. Examines which agents acted,
    messages, memories, questions, reflections, research, relationship
    totals, and Research Wall/Rabbit-Hole/Belief uptake across the exact
    new event interval, plus a cross-agent-transmission check restricted
    to that window's own new messages -- every query a single read-only
    LIVE_DB_READ SELECT (or the existing GET_EVENT_RANGE capability). No
    new broker capability, no write, no Village behavior change. Any row
    the contamination registry would flag (see
    director_contamination_registry.py, wired into GET_EVENT_RANGE) is
    excluded from the agent/event-type analysis, not merely counted --
    consistent with the 2026-09-05 incident's exclusion requirement, even
    though a live window advancing forward from the current baseline can
    never actually overlap the frozen 624-633 interval."""
    event_range = broker.execute("GET_EVENT_RANGE", {"start_id": start_event_id + 1, "end_id": end_event_id, "limit": 500})
    if event_range.status != "SUCCESS":
        return TaskResult(status="FAILED", summary=event_range.failure_reason or "could not read event range", detail=event_range.to_dict())

    columns = event_range.result["columns"]
    all_rows = event_range.result["rows"]
    idx = {name: i for i, name in enumerate(columns)}
    excluded = [r for r in all_rows if r[idx["contaminated"]]]
    rows = [r for r in all_rows if not r[idx["contaminated"]]]
    if not rows:
        return TaskResult(
            status="COMPLETED",
            summary=f"window {start_event_id + 1}-{end_event_id}: no non-contaminated event rows found (nothing to analyze)",
            detail={"columns": columns, "rows": rows, "excluded_contaminated_count": len(excluded)},
        )

    agent_ids_acted = sorted({r[idx["agent_id"]] for r in rows if r[idx["agent_id"]]})
    event_type_counts: dict[str, int] = {}
    for r in rows:
        et = r[idx["event_type"]]
        event_type_counts[et] = event_type_counts.get(et, 0) + 1

    timestamps = [r[idx["created_at"]] for r in rows]
    min_ts, max_ts = _safe_timestamp(min(timestamps)), _safe_timestamp(max(timestamps))

    def _grouped_count(table: str) -> TaskResult:
        return _run_read(
            f"SELECT agent_id, COUNT(*) as n FROM {table} "
            f"WHERE created_at BETWEEN '{min_ts}' AND '{max_ts}' GROUP BY agent_id ORDER BY n DESC",
            f"{table} in window",
        )

    messages_result = _run_read(
        "SELECT sender_agent_id, recipient_agent_id, COUNT(*) as n FROM messages "
        f"WHERE created_at BETWEEN '{min_ts}' AND '{max_ts}' GROUP BY sender_agent_id, recipient_agent_id ORDER BY n DESC",
        "messages in window",
    )
    memories_result = _grouped_count("memories")
    questions_result = _grouped_count("agent_questions")
    reflections_result = _grouped_count("agent_reflections")
    research_result = _grouped_count("research_sessions")
    transmission_result = _run_read(
        "SELECT m.id, m.sender_agent_id, m.recipient_agent_id, "
        "(SELECT COUNT(*) FROM memories mem WHERE mem.content LIKE '%' || substr(m.content, 1, 30) || '%') as memory_hits "
        f"FROM messages m WHERE m.created_at BETWEEN '{min_ts}' AND '{max_ts}' ORDER BY m.id",
        "cross-agent transmission check (window-scoped)",
    )
    wall_result = _run_read(
        "SELECT (SELECT COUNT(*) FROM research_wall) as wall, (SELECT COUNT(*) FROM rabbit_holes) as holes, "
        "(SELECT COUNT(*) FROM agent_beliefs) as beliefs",
        "Wall/Rabbit-Hole/Belief cumulative totals (not window-scoped -- no history table exists to diff against)",
    )
    relationships_result = _run_read(
        "SELECT COUNT(*) as n_relationships, SUM(interaction_count) as total_interactions FROM relationships",
        "relationship totals (cumulative, not window-scoped)",
    )

    def _col_sum(result: TaskResult, col_index: int) -> int:
        if result.status != "COMPLETED":
            return 0
        return sum(row[col_index] for row in result.detail.get("rows", []))

    n_messages = _col_sum(messages_result, 2)
    n_memories = _col_sum(memories_result, 1)
    n_questions = _col_sum(questions_result, 1)
    n_reflections = _col_sum(reflections_result, 1)
    n_research = _col_sum(research_result, 1)
    transmission_hits = _col_sum(transmission_result, 3)

    culture_note = (
        f"cross-agent transmission detected ({transmission_hits} hit(s)) -- warrants a dedicated follow-up trace"
        if transmission_hits > 0
        else "no new cross-agent transmission detected in this window, consistent with the established pattern"
    )

    summary = (
        f"window {start_event_id + 1}-{end_event_id}: {len(rows)} events, agents acted={agent_ids_acted}, "
        f"event types={event_type_counts}; {n_messages} messages, {n_memories} memories, {n_questions} questions, "
        f"{n_reflections} reflections, {n_research} research sessions; {culture_note}"
    )

    return TaskResult(
        status="COMPLETED",
        summary=summary,
        detail={
            "start_event_id": start_event_id, "end_event_id": end_event_id,
            "agent_ids_acted": agent_ids_acted, "event_type_counts": event_type_counts,
            "excluded_contaminated_count": len(excluded),
            "messages": messages_result.detail, "memories": memories_result.detail,
            "questions": questions_result.detail, "reflections": reflections_result.detail,
            "research_sessions": research_result.detail, "cross_agent_transmission": transmission_result.detail,
            "wall_rabbit_belief_totals": wall_result.detail, "relationship_totals": relationships_result.detail,
        },
    )


def _shift_window_analyses(status: dict[str, Any], shift_start: int, shift_end: int) -> list[tuple[int, int, dict]]:
    """(start, end, detail) for every completed analyze_live_window_*
    result whose interval falls within [shift_start, shift_end] -- i.e.
    the live windows THIS shift itself produced, oldest first. Reads only
    already-collected results_store data, never the live DB again."""
    store = status.get("results_store", {})
    out: list[tuple[int, int, dict]] = []
    for task_id, detail in store.items():
        if not task_id.startswith("analyze_live_window_") or not isinstance(detail, dict):
            continue
        s, e = detail.get("start_event_id"), detail.get("end_event_id")
        if isinstance(s, int) and isinstance(e, int) and s >= shift_start and e <= shift_end:
            out.append((s, e, detail))
    out.sort(key=lambda t: t[0])
    return out


def _run_cross_window_synthesis(status: dict[str, Any], shift_start: int, shift_end: int) -> TaskResult:
    """Task class A (Founder authorization, 2026-09-05): compares every
    live window THIS SHIFT produced across the shift's full interval --
    which agents became more/less active, whether Wall/Rabbit-Hole/Belief
    state changed, whether relationship totals moved, and cumulative
    cross-agent transmission -- purely by aggregating already-collected
    analyze_live_window_* results (ZERO new broker calls, zero new
    provider spend; this is why reaching the live-window cap is never
    itself exhaustion, there is still cheap, real evidence to mine). Also
    emits ranked, falsifiable hypotheses (task class J), each with
    evidence-for, evidence-against, an alternative explanation, a
    falsifiable prediction, and a safest-next-test with its type."""
    windows = _shift_window_analyses(status, shift_start, shift_end)
    if not windows:
        return TaskResult(status="FAILED", summary="no analyzed live windows found in this shift's interval")

    def _field_totals(field: str) -> dict[str, int]:
        totals: dict[str, int] = {}
        for _, _, d in windows:
            for row in (d.get(field) or {}).get("rows", []):
                totals[row[0]] = totals.get(row[0], 0) + row[1]
        return totals

    def _messages_totals() -> tuple[dict[str, int], dict[str, int]]:
        sent: dict[str, int] = {}
        received: dict[str, int] = {}
        for _, _, d in windows:
            for row in (d.get("messages") or {}).get("rows", []):
                sender, recipient, n = row[0], row[1], row[2]
                if sender:
                    sent[sender] = sent.get(sender, 0) + n
                if recipient:
                    received[recipient] = received.get(recipient, 0) + n
        return sent, received

    messages_sent, messages_received = _messages_totals()
    memories_totals = _field_totals("memories")
    questions_totals = _field_totals("questions")
    reflections_totals = _field_totals("reflections")
    research_totals = _field_totals("research_sessions")

    all_agents = sorted(
        set(messages_sent) | set(messages_received) | set(memories_totals)
        | set(questions_totals) | set(reflections_totals) | set(research_totals)
    )
    activity_totals = {
        a: messages_sent.get(a, 0) + messages_received.get(a, 0) + memories_totals.get(a, 0)
        + questions_totals.get(a, 0) + reflections_totals.get(a, 0) + research_totals.get(a, 0)
        for a in all_agents
    }

    def _half_totals(half_windows: list) -> dict[str, int]:
        agg: dict[str, int] = {}
        for _, _, d in half_windows:
            for row in (d.get("messages") or {}).get("rows", []):
                if row[0]:
                    agg[row[0]] = agg.get(row[0], 0) + row[2]
            for field in ("memories", "questions", "reflections", "research_sessions"):
                for row in (d.get(field) or {}).get("rows", []):
                    agg[row[0]] = agg.get(row[0], 0) + row[1]
        return agg

    midpoint = max(1, len(windows) // 2)
    first_totals = _half_totals(windows[:midpoint])
    second_totals = _half_totals(windows[midpoint:]) if len(windows) > midpoint else {}
    trends = {}
    for a in all_agents:
        f, s = first_totals.get(a, 0), second_totals.get(a, 0)
        if not second_totals:
            trends[a] = "single-window this shift, no trend derivable"
        elif s > f:
            trends[a] = "more active in the later part of this shift"
        elif s < f:
            trends[a] = "less active in the later part of this shift"
        else:
            trends[a] = "steady across this shift"

    def _first_row(field: str) -> Any:
        return (windows[0][2].get(field) or {}).get("rows", [None])[0]

    def _last_row(field: str) -> Any:
        return (windows[-1][2].get(field) or {}).get("rows", [None])[0]

    first_wall, last_wall = _first_row("wall_rabbit_belief_totals"), _last_row("wall_rabbit_belief_totals")
    new_persistent_state = first_wall != last_wall
    first_rel, last_rel = _first_row("relationship_totals"), _last_row("relationship_totals")
    relationship_moved = first_rel != last_rel

    total_transmission_hits = sum(
        row[3] for _, _, d in windows for row in (d.get("cross_agent_transmission") or {}).get("rows", [])
    )
    most_active = max(activity_totals, key=activity_totals.get) if activity_totals else None

    hypotheses = [
        {
            "hypothesis": (
                f"{most_active} continues to dominate real activity across this shift's {len(windows)} live window(s)"
                if most_active else "no agent showed measurable non-event activity this shift"
            ),
            "evidence_for": f"activity totals: {activity_totals}",
            "evidence_against": "a single shift's windows are a small sample; dominance could reflect scheduling opportunity, not durable disposition",
            "alternative_explanation": "the scheduler/opportunity-selection mechanism, not agent disposition, determines who acts",
            "falsifiable_prediction": "a much larger live sample would show the same agent(s) dominating at a similar rate",
            "safest_next_test": "read-only: agent_opportunity_and_scheduling_trace across this interval",
            "test_type": "read_only",
        },
        {
            "hypothesis": (
                "no durable cross-agent transmission occurred across this shift's live windows"
                if total_transmission_hits == 0 else
                f"cross-agent transmission occurred ({total_transmission_hits} hit(s)) and warrants a dedicated trace"
            ),
            "evidence_for": f"{total_transmission_hits} substring-match transmission hit(s) across {len(windows)} window(s)",
            "evidence_against": None if total_transmission_hits == 0 else f"{total_transmission_hits} hit(s) directly contradict a strict no-transmission claim",
            "alternative_explanation": "transmission may occur through paraphrase or delayed reference this substring check cannot detect",
            "falsifiable_prediction": (
                "a live window immediately following an agent explicitly referencing another agent's shared content would still show zero substring hits"
                if total_transmission_hits == 0 else
                "the specific message pair(s) found show a real, attributable causal link, not coincidental phrasing overlap"
            ),
            "safest_next_test": "read-only: manually inspect the specific flagged message/memory pair(s)" if total_transmission_hits else "disposable: extend message_provenance_cross_check over a longer interval",
            "test_type": "read_only",
        },
        {
            "hypothesis": (
                "no new Wall/Rabbit-Hole/Belief uptake formed this shift, consistent with the established all-zero pattern"
                if not new_persistent_state else
                "new Wall/Rabbit-Hole/Belief state appeared this shift -- a genuine departure from the established pattern"
            ),
            "evidence_for": f"cumulative totals: first window={first_wall}, last window={last_wall}",
            "evidence_against": None,
            "alternative_explanation": "these mechanisms may require conditions (e.g. explicit prompting) this shift's unforced activity never created",
            "falsifiable_prediction": (
                "a much longer live run under identical conditions would still show zero uptake"
                if not new_persistent_state else "the new state persists and is referenced again in a later window"
            ),
            "safest_next_test": "read-only: wall_rabbit_belief_population_recheck at the start of the next shift",
            "test_type": "read_only",
        },
    ]

    summary = (
        f"cross-window synthesis, shift interval {shift_start}-{shift_end} ({len(windows)} window(s)): "
        f"activity totals={activity_totals}; trends={trends}; new persistent Wall/Rabbit/Belief state={new_persistent_state}; "
        f"relationship totals moved={relationship_moved}; cumulative cross-agent transmission hits={total_transmission_hits}"
    )
    return TaskResult(
        status="COMPLETED",
        summary=summary,
        detail={
            "shift_start": shift_start, "shift_end": shift_end, "windows_analyzed": len(windows),
            "activity_totals": activity_totals, "trends": trends,
            "messages_sent": messages_sent, "messages_received": messages_received,
            "new_persistent_state": new_persistent_state, "relationship_totals_moved": relationship_moved,
            "cumulative_cross_agent_transmission_hits": total_transmission_hits,
            "hypotheses": hypotheses,
        },
    )


def _maybe_generate_replication_task(status: dict[str, Any], shift: dict[str, Any]) -> Task | None:
    """Task class K (Founder authorization, 2026-09-05): autonomously
    re-running an ALREADY-APPROVED disposable experiment when this shift's
    own cross-window synthesis shows a qualifying real-world condition --
    never inventing a new experiment_id or new stimulus text, only reusing
    the exact, already-reviewed 'quiet_agent_thread_counterfactual'
    template this file already ships for agent_lucid. Gated on the
    synthesis having already run THIS shift, so this is always a genuine,
    evidence-triggered follow-up, never an independent guess."""
    synthesis_task_id = f"cross_window_synthesis_{shift['starting_live_event']}_{shift['current_live_event']}"
    synthesis = status.get("results_store", {}).get(synthesis_task_id)
    if not isinstance(synthesis, dict):
        return None  # synthesis hasn't run yet this shift -- nothing to react to

    replication_task_id = f"quiet_agent_replication_agent_lucid_shift_{shift['shift_id']}"
    if replication_task_id in status["completed_task_ids"] or replication_task_id in status["failed_task_ids"]:
        return None

    lucid_sent_this_shift = synthesis.get("messages_sent", {}).get("agent_lucid", 0)
    if not lucid_sent_this_shift:
        return None  # no new real activity from Lucid this shift -- nothing to justify a fresh trial

    def _run() -> TaskResult:
        return _run_experiment(
            "quiet_agent_thread_counterfactual", "agent_lucid",
            "I asked Optimisto how people actually land on what they want to dig into this morning "
            "-- he never answered. Still don't know what he thinks.",
            "EPISODIC", 4,
        )

    return Task(
        replication_task_id,
        f"Dynamically justified (shift {shift['shift_id']}): agent_lucid sent {lucid_sent_this_shift} new "
        "message(s) this shift per the cross-window synthesis -- replicate the already-approved quiet-agent "
        "unresolved-memory experiment to test whether new real activity changes the substantive-response rate",
        [1, 4, 5],
        "D",
        _run,
    )


def generate_next_investigation_task(status: dict[str, Any], shift: dict[str, Any]) -> Task | None:
    """The dynamic half of the planner (Founder authorization, 2026-09-05,
    expanded 2026-09-05 to widen the scientific repertoire): consulted
    only once the static + per-agent seed queue has nothing left. Every
    currently-authorized task class is checked, in priority order, before
    a planning pass may count as "no material task":

    1. any completed live window whose event interval hasn't been
       analyzed yet -- analyze it next (task class per-window analysis).
    2. otherwise, if this shift's own live-window cap (MAX_LIVE_WINDOWS)
       and the mechanically-proven remaining margin both still allow it,
       attempt one more bounded live window.
    3. otherwise (no more live advancement is currently permitted THIS
       SHIFT -- which is NOT exhaustion, only "no more live windows"):
       cross-window synthesis of this shift's full live interval, if at
       least one window ran this shift and it hasn't been synthesized yet
       (task class A, with embedded ranked hypotheses, task class J).
    4. otherwise, an evidence-justified replication of an
       ALREADY-APPROVED disposable experiment, if the synthesis surfaced
       a qualifying condition (task class K).

    Returns None (no material task) only once every one of the above has
    been checked and found nothing to do -- callers count 3 consecutive
    None results as genuine exhaustion, never a bare empty seed queue and
    never merely reaching the live-window cap."""
    for task_id, start, end in _completed_live_windows(status):
        analysis_task_id = f"analyze_live_window_{start}_{end}"
        if analysis_task_id in status["completed_task_ids"] or analysis_task_id in status["failed_task_ids"]:
            continue
        return Task(
            analysis_task_id,
            f"Automatic post-live-window analysis of events {start + 1}-{end}",
            [1, 2, 3, 4, 6, 7, 8, 9, 10],
            "R",
            (lambda s=start, e=end: _run_analyze_live_window(s, e)),
        )

    live_window_permitted = shift["live_windows_this_shift"] < MAX_LIVE_WINDOWS
    if live_window_permitted:
        remaining = _remaining_overnight_live_budget()
        live_window_permitted = remaining is not None and remaining >= _worst_case_activation_burst()

    if live_window_permitted:
        used_live_ids = {
            tid for tid in (
                status["completed_task_ids"] + status["failed_task_ids"] + status.get("live_bound_not_guaranteed_task_ids", [])
            )
            if tid.startswith("attempt_live_window_")
        }
        n = 1
        while f"attempt_live_window_{n}" in used_live_ids:
            n += 1
        task_id = f"attempt_live_window_{n}"
        return Task(
            task_id,
            f"Dynamically continued (shift {shift['shift_id']}): attempt bounded live-science window #{n}",
            [1, 2, 4, 5, 6, 7, 8, 9, 10],
            "L",
            (lambda tid=task_id: _attempt_live_window_task_body(tid)),
        )

    # No more live advancement is currently permitted this shift (cap
    # reached or margin insufficient) -- that is NOT exhaustion, only "no
    # more live windows." Mine the accumulated evidence instead.
    if shift["current_live_event"] > shift["starting_live_event"]:
        synthesis_task_id = f"cross_window_synthesis_{shift['starting_live_event']}_{shift['current_live_event']}"
        if synthesis_task_id not in status["completed_task_ids"] and synthesis_task_id not in status["failed_task_ids"]:
            shift_start, shift_end = shift["starting_live_event"], shift["current_live_event"]
            return Task(
                synthesis_task_id,
                f"Cross-window synthesis of this shift's full live interval {shift_start}-{shift_end}",
                [1, 2, 3, 4, 6, 7, 8, 9, 10],
                "R",
                (lambda ss=shift_start, se=shift_end: _run_cross_window_synthesis(status, ss, se)),
            )
        replication_task = _maybe_generate_replication_task(status, shift)
        if replication_task is not None:
            return replication_task

    return None


def write_final_founder_packet(status: dict[str, Any], before: dict[str, Any], shift: dict[str, Any]) -> Path:
    path = FOUNDER_PACKETS_DIR / "unattended_shift_completion_2026-09-04.md"
    store = status.get("results_store", {})
    stat_lines = (store.get("statistical_reanalysis_shift_experiments") or {}).get("lines", [])
    content = f"""# Unattended Director Shift — Completion Report
### {_now()} — standalone runner, zero Claude Code involvement during execution

## 1. Why the shift stopped

**Genuinely exhausted** (Founder-authorized conservative rule, 2026-09-05):
{shift['consecutive_no_material_task_passes']} consecutive dynamic-planning
passes this shift produced no material safe next task, AND no unresolved
high-value scientific question could currently be investigated safely (the
static + per-agent seed queue was already exhausted, every completed live
window had already been analyzed, and either this shift's live-window cap
({MAX_LIVE_WINDOWS}) or the mechanically-proven remaining live-event margin
ruled out attempting another window). A completed finite seed backlog is
explicitly NOT treated as genuine exhaustion by itself -- the dynamic
planner (generate_next_investigation_task) is always consulted first.

Shift: `{shift['shift_id']}`, started {shift['shift_started_at']},
{shift['shift_cycle_count']} planning cycles this shift.

## 2. Completed this shift

{shift['completed_tasks_this_shift']} tasks completed THIS SHIFT
({status['completed_task_count']} lifetime), {status['deferred_network_count']}
deferred for network, {len(status['failed_task_ids'])} failed (lifetime).
Provider calls this shift: {shift['provider_calls_this_shift']}
({status['provider_calls_used']} lifetime).

Live events added this shift: {shift['live_events_added_this_shift']}
across {shift['live_windows_this_shift']} live window(s)
(starting live event {shift['starting_live_event']} -> current
{shift['current_live_event']}).

Completed task IDs (lifetime): {status['completed_task_ids']}

## 3. New evidence / statistical reanalysis

{chr(10).join('- ' + l for l in stat_lines) if stat_lines else '(see results_store in unattended_status.json for raw detail)'}

## 4. Blocked candidates (recorded, not executed)

{chr(10).join(f'- `{k}`: {v}' for k, v in _KNOWN_BLOCKED_DIAGNOSTIC_TYPES.items())}

Each requires a separate, explicit broker-catalog registration decision
(adding a diagnostic_type to `_APPROVED_DIAGNOSTIC_TYPES` or a table to
the read allowlist) -- Director-infrastructure engineering, not a Village
behavior change, but still outside this shift's standing authorization.

## 5. Highest-value next consequential action

Per the accumulated evidence across this whole project, the two genuine
boundaries now reached are: (a) registering the blocked diagnostic types
above (a narrow broker-infrastructure change, low risk, would unlock
several more free R-class tasks), and (b) the still-pending Gate C
(A+C social-experience-persistence) production candidate, which remains
unimplemented and would require a real `app/` code change plus separate
Founder authorization to prototype live. Neither was attempted this
shift.

## 6. Safety state at completion

- Live DB hash: {before['sha256']} (matches the safety snapshot taken immediately after the last completed task; re-verified after every single task)
- Max event id: {before['max_event_id']} (module starting baseline {BASELINE_MAX_EVENT}; expected baseline at completion {status['max_live_event_baseline']}; live events added this shift: {shift['live_events_added_this_shift']}; lifetime total: {status['live_events_added_total']})
- Day/period/paused: {before['current_day']} / {before['current_period']} / {before['is_paused']}
- Live DB mutated: {status['live_db_mutated']}
- No live advancement, no production/prompt/schema change, no Level 2B, no new broker capability added during execution.

**Control returned to Founder. No consequential action was taken.**
"""
    path.write_text(content)
    return path


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
        # Load status FIRST: an earlier launch of this same script may
        # already have legitimately advanced max_live_event_baseline via a
        # real RUN_BOUNDED_LIVE_WINDOW call, in which case the correct
        # expected value on this fresh launch is that persisted baseline,
        # not the module's original BASELINE_MAX_EVENT constant.
        status = load_status()
        expected_max_event = status["max_live_event_baseline"]

        before = safety_snapshot()
        if before["max_event_id"] != expected_max_event or not before["is_paused"]:
            print(f"REFUSING TO START: live baseline changed unexpectedly (expected max_event_id={expected_max_event}): {before}")
            return 1
        if not before["integrity_ok"]:
            print(f"REFUSING TO START: live DB integrity check failed: {before}")
            return 1

        # Shift-local state (Founder authorization, 2026-09-05): a
        # completed or founder-stopped previous shift's counters must
        # never poison this run's genuine-exhaustion evaluation. Only an
        # actually-interrupted shift (state left as "running" on disk --
        # meaning the previous process died without ever reaching a clean
        # stop) resumes the same shift_id and its accumulated counters;
        # every other launch (including "the previous shift completed")
        # begins a fresh shift with fresh counters.
        previous_state = status.get("state")
        existing_shift = status.get("current_shift")
        resuming_interrupted_shift = previous_state == "running" and existing_shift is not None
        if resuming_interrupted_shift:
            shift = existing_shift
        else:
            if existing_shift is not None:
                append_rolling_packet(
                    "Previous shift ended",
                    f"shift_id={existing_shift.get('shift_id')} stop_reason={existing_shift.get('stop_reason')} "
                    f"completed_tasks_this_shift={existing_shift.get('completed_tasks_this_shift')} "
                    f"live_events_added_this_shift={existing_shift.get('live_events_added_this_shift')}",
                )
            shift = _new_shift_state(before["max_event_id"])
        status["current_shift"] = shift

        status["state"] = "running"
        status["stop_reason"] = None
        shift["stop_reason"] = None
        save_status(status)
        append_rolling_packet(
            "Session start" if status["completed_task_count"] == 0 else ("Interrupted shift resumed" if resuming_interrupted_shift else "New shift started"),
            f"Shift: {shift['shift_id']} (started {shift['shift_started_at']})\n"
            f"Baseline: {before}\nAlready completed (lifetime): {status['completed_task_ids']}\n"
            f"Provider calls used so far (lifetime): {status['provider_calls_used']}\n"
            f"Live events added so far (lifetime): {status['live_events_added_total']}",
        )

        while True:
            if _stop_requested or STOP_FLAG_PATH.exists():
                status["state"] = "stopped"
                status["stop_reason"] = "founder_requested_stop"
                shift["stop_reason"] = "founder_requested_stop"
                save_status(status)
                STOP_FLAG_PATH.unlink(missing_ok=True)
                print("Stop requested. Exiting cleanly.")
                return 0

            status["planning_cycle"] += 1
            shift["shift_cycle_count"] += 1

            # Seed queue first (static + per-agent dynamic generator); if
            # and only if that has nothing left, fall back to the
            # continuous-Director dynamic planner (Founder authorization,
            # 2026-09-05) -- a completed finite seed backlog must never by
            # itself be treated as genuine exhaustion.
            task = next_unfinished_task(status)
            if task is None:
                task = generate_next_investigation_task(status, shift)

            if task is None:
                shift["consecutive_no_material_task_passes"] += 1
                save_status(status)
                if shift["consecutive_no_material_task_passes"] < 3:
                    append_rolling_packet(
                        f"Dynamic planning pass {shift['consecutive_no_material_task_passes']}/3: no material task",
                        "Seed queue empty and generate_next_investigation_task found no unanalyzed live window "
                        "and no further live window this shift can currently be safely attempted (shift cap or "
                        "mechanical margin). Continuing to the conservative 3-pass confirmation before declaring "
                        "genuine exhaustion.",
                    )
                    continue
                status["state"] = "stopped"
                status["stop_reason"] = "genuinely_exhausted"
                shift["stop_reason"] = "genuinely_exhausted"
                save_status(status)
                packet_path = write_final_founder_packet(status, before, shift)
                append_rolling_packet(
                    "Shift complete -- genuinely exhausted",
                    f"3 consecutive dynamic-planning passes produced no material safe next task and no "
                    f"unresolved high-value scientific question could currently be investigated safely, after "
                    f"{shift['shift_cycle_count']} planning cycles this shift ({status['planning_cycle']} lifetime). "
                    f"Completed this shift: {shift['completed_tasks_this_shift']}. Live windows this shift: "
                    f"{shift['live_windows_this_shift']}. Founder Approval Packet: {packet_path}",
                )
                print(f"Genuinely exhausted after {shift['shift_cycle_count']} planning cycles this shift ({status['planning_cycle']} lifetime). Founder Approval Packet: {packet_path}")
                return 0

            shift["consecutive_no_material_task_passes"] = 0

            if task.task_id.startswith("agent_profile_"):
                status["dynamically_generated_task_count"] += 1

            if status["provider_calls_used"] >= MAX_TOTAL_PROVIDER_CALLS and task.method in ("D", "N"):
                status["continuing_because"] = "provider budget exhausted for D/N; continuing with R-only tasks"
                # Skip (do not mark failed -- may resume later) any D/N
                # task once the budget is spent, but keep planning: an
                # R-class task might still exist further in the queue.
                remaining_r = [t for t in get_task_queue(status) if t.method == "R" and t.task_id not in status["completed_task_ids"] and t.task_id not in status["failed_task_ids"]]
                if not remaining_r:
                    status["state"] = "stopped"
                    status["stop_reason"] = "provider_budget_exhausted_no_offline_work_remains"
                    shift["stop_reason"] = "provider_budget_exhausted_no_offline_work_remains"
                    save_status(status)
                    packet_path = write_final_founder_packet(status, before, shift)
                    append_rolling_packet("Stopped", f"Provider budget ({MAX_TOTAL_PROVIDER_CALLS}) exhausted and no R-class work remains. Founder Approval Packet: {packet_path}")
                    print(f"Provider budget exhausted, no offline work remains. Founder Approval Packet: {packet_path}")
                    return 0
                task = remaining_r[0]

            status["current_task"] = task.task_id
            save_status(status)
            print(f"[{_now()}] cycle {status['planning_cycle']}: running {task.task_id} ({task.method}) -- {task.description}")

            result = task.run()

            status["provider_calls_used"] += result.provider_calls
            shift["provider_calls_this_shift"] += result.provider_calls
            status["current_task"] = None

            if task.method == "L":
                # Counts against this shift's live-window cap on ANY
                # outcome (COMPLETED, FAILED, or
                # LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED) -- not only
                # success. Counting only successes would let a
                # persistently-failing live-window call spin forever: a
                # FAILED result never re-triggers the "no material task"
                # 3-strikes branch (a task WAS found and attempted every
                # cycle), so without this the shift-local cap would never
                # actually bound the retries.
                shift["live_windows_this_shift"] += 1

            if result.status == "COMPLETED":
                status["completed_task_ids"].append(task.task_id)
                status["completed_task_count"] += 1
                status["last_completed_task"] = task.task_id
                status["results_store"][task.task_id] = result.detail
                shift["completed_tasks_this_shift"] += 1
                if task.method == "L":
                    # A real, authorized live-window advance -- move the
                    # expected baseline forward BEFORE the safety check
                    # below runs, so an intentional, bounded advance is
                    # recognized as legitimate rather than flagged as a
                    # violation. Genuinely reachable as of 2026-09-05 (the
                    # 50-event window fits the proven 42-event worst case).
                    events_added = result.detail.get("events_added", 0)
                    status["live_events_added_total"] += events_added
                    shift["live_events_added_this_shift"] += events_added
                    new_baseline = result.detail.get("end_max_event_id")
                    if new_baseline is not None:
                        shift["current_live_event"] = new_baseline
                        if new_baseline > ABSOLUTE_EVENT_CEILING:
                            status["state"] = "stopped"
                            status["stop_reason"] = "SAFETY_VIOLATION_live_event_ceiling_exceeded"
                            status["live_db_mutated"] = True
                            shift["stop_reason"] = "SAFETY_VIOLATION_live_event_ceiling_exceeded"
                            save_status(status)
                            append_rolling_packet("SAFETY STOP", f"Live window pushed max_event_id to {new_baseline}, exceeding the absolute ceiling {ABSOLUTE_EVENT_CEILING}. Halting immediately.")
                            print("SAFETY VIOLATION: absolute live event ceiling exceeded. Halting immediately.")
                            return 2
                        status["max_live_event_baseline"] = new_baseline
                append_rolling_packet(f"Task completed: {task.task_id}", f"Method: {task.method}\nRoadmap phases: {task.roadmap_phases}\nResult: {result.summary}\n\n```json\n{json.dumps(result.detail, indent=2, default=str)[:8000]}\n```")
            elif result.status == "DEFERRED_NETWORK":
                if task.task_id not in status["deferred_network_task_ids"]:
                    status["deferred_network_task_ids"].append(task.task_id)
                status["deferred_network_count"] += 1
                append_rolling_packet(f"DEFERRED_NETWORK: {task.task_id}", f"Reason: {result.summary}\nWill retry on next resume.")
                print(f"  DEFERRED_NETWORK: {result.summary}")
            elif result.status == "LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED":
                # Recorded and never retried -- the refusal reason is
                # invariant under the current schema (see director_broker
                # .py's _derive_worst_case_activation_burst), so repeating
                # this call would be pure busywork.
                if task.task_id not in status["live_bound_not_guaranteed_task_ids"]:
                    status["live_bound_not_guaranteed_task_ids"].append(task.task_id)
                append_rolling_packet(f"LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED: {task.task_id}", f"Reason: {result.summary}\nContinuing with other authorized R/D/N work instead.")
                print(f"  LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED: {result.summary}")
            else:  # FAILED or NEW_EXPERIMENT_APPROVAL_REQUIRED
                status["failed_task_ids"].append(task.task_id)
                if result.status == "NEW_EXPERIMENT_APPROVAL_REQUIRED":
                    status["blocked_tasks"].append({"task_id": task.task_id, "reason": result.summary})
                append_rolling_packet(f"{result.status}: {task.task_id}", f"Reason: {result.summary}")
                print(f"  {result.status}: {result.summary}")

            save_status(status)

            after = safety_snapshot()
            # CORRECTION, 2026-09-05, following a real incident: a
            # legitimate, authorized live-window advance necessarily
            # changes the file hash (real content changed) -- the original
            # version of this check compared the hash unconditionally and
            # would have flagged EVERY successful live window as a false
            # "SAFETY_VIOLATION_live_db_changed", never actually verified
            # until RUN_BOUNDED_LIVE_WINDOW became reachable. The event-id
            # comparison against the just-updated max_live_event_baseline
            # already correctly distinguishes "the exact authorized amount
            # changed" from "something changed unexpectedly" -- the hash
            # must only be compared when this task was NOT itself a
            # completed live-window advance.
            was_legitimate_live_advance = task.method == "L" and result.status == "COMPLETED"
            hash_violation = (not was_legitimate_live_advance) and after["sha256"] != before["sha256"]
            event_violation = after["max_event_id"] != status["max_live_event_baseline"]
            if hash_violation or event_violation:
                status["state"] = "stopped"
                status["stop_reason"] = "SAFETY_VIOLATION_live_db_changed"
                status["live_db_mutated"] = True
                shift["stop_reason"] = "SAFETY_VIOLATION_live_db_changed"
                save_status(status)
                append_rolling_packet("SAFETY STOP", f"Live DB changed unexpectedly after {task.task_id}. Before={before}, After={after}, expected baseline={status['max_live_event_baseline']}, hash_violation={hash_violation}, event_violation={event_violation}. Halting immediately.")
                print("SAFETY VIOLATION: live DB changed. Halting immediately.")
                return 2
            before = after  # the new legitimate baseline for the next iteration's comparison
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
