#!/usr/bin/env python3
"""Director Level 1: one review round.

    snapshot (director_snapshot.build_snapshot), persisted + versioned
        -> exactly one PRIMARY reviewer (scripts/director_reviewers)
        -> zero or more CRITIQUE reviewers (e.g. Hermes, once configured),
           each independently given the SAME snapshot plus the PRIMARY
           reviewer's own full output
        -> every reviewer's full output appended to .director/observations.jsonl
           as its own record, tagged with a shared round_id — never
           averaged, merged, or reconciled into one "consensus" result
        -> cursor advanced in .director/cursor.json once the PRIMARY
           reviewer succeeds (a CRITIQUE reviewer's failure is recorded and
           reported, but never blocks the round or rolls back the PRIMARY's
           already-recorded observation)
        -> a concise, per-reviewer Founder report printed

Which reviewers run is entirely config (.director/reviewers.json, falling
back to director_reviewers.DEFAULT_REVIEWERS) — this script has no branch
that names a specific reviewer. Enabling Hermes, or adding a second
CRITIQUE reviewer, is a config edit, never a code change here.

Safety boundary — Level 1 is OBSERVATION ONLY:

- Every reviewer only ever reads the snapshot dict already built by
  director_snapshot.build_snapshot() (itself strictly read-only against
  the live DB) — no reviewer, PRIMARY or CRITIQUE, is ever given DB, shell,
  or filesystem access. It calls a model and gets JSON back; nothing else.
- Never modifies Village code, the live database, or runs Village periods.
- Never executes a Director or Hermes recommendation.
- Never invokes Claude Code or any other agent to implement anything.
- Never approves its own recommendation: RecommendationStatus.APPROVED_TO_TEST
  is rejected by director_reviewers.run_reviewer() even if a model returns
  it — no reviewer output can ever mark itself approved.
- Director output only ever goes to Director-owned state: .director/cursor.json,
  .director/observations.jsonl, .director/snapshots/*.json.

Usage::

    .venv/bin/python scripts/director_loop.py
    .venv/bin/python scripts/director_loop.py --db-path /tmp/fixture.db --cursor-path /tmp/cursor.json
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.core.db_safety import LiveDatabaseError  # noqa: E402
from director_providers import ModelProviderError  # noqa: E402
from director_reviewers import (  # noqa: E402
    ReviewerRole,
    ReviewerSpec,
    load_reviewer_specs,
    run_reviewer,
)
from director_snapshot import DirectorSnapshotError, build_snapshot  # noqa: E402
from director_bridge import get_relevant_history, rebuild_rounds_history  # noqa: E402
from director_diagnostics import (  # noqa: E402
    DiagnosticState,
    DiagnosticSafetyError,
    load_evidence as load_diagnostic_evidence,
    load_spec as load_diagnostic_spec,
    DEFAULT_DIAGNOSTICS_DIR,
)
from director_experiments import (  # noqa: E402
    ExperimentState,
    load_evidence as load_experiment_evidence,
    load_spec as load_experiment_spec,
    DEFAULT_EXPERIMENTS_DIR,
)
from director_synthesis import build_generic_reconciliation_packet  # noqa: E402

DIRECTOR_DIR = REPO_ROOT / ".director"
DEFAULT_CURSOR_PATH = DIRECTOR_DIR / "cursor.json"
DEFAULT_OBSERVATIONS_PATH = DIRECTOR_DIR / "observations.jsonl"
DEFAULT_SNAPSHOTS_DIR = DIRECTOR_DIR / "snapshots"
DEFAULT_PACKETS_DIR = DIRECTOR_DIR / "packets"


class DirectorLoopError(RuntimeError):
    """One Director round could not complete. The cursor is left unchanged."""


def load_cursor(cursor_path: Path) -> dict[str, Any]:
    if not cursor_path.exists():
        return {"last_event_id": 0}
    return json.loads(cursor_path.read_text())


def save_cursor(cursor_path: Path, cursor: dict[str, Any]) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(json.dumps(cursor, indent=2) + "\n")


def persist_snapshot(snapshots_dir: Path, snapshot_id: str, snapshot: dict[str, Any]) -> Path:
    """Write the exact snapshot used for this round to disk, immutably —
    this is the evidence a second reviewer (Hermes, or a human) can later
    be given, byte-for-byte identical to what the PRIMARY reviewer saw."""
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    path = snapshots_dir / f"{snapshot_id}.json"
    path.write_text(json.dumps(snapshot, indent=2, default=str) + "\n")
    return path


def append_record(observations_path: Path, record: dict[str, Any]) -> None:
    observations_path.parent.mkdir(parents=True, exist_ok=True)
    with observations_path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _base_record(round_id: str, snapshot_id: str, snapshot_version: int, spec: ReviewerSpec) -> dict[str, Any]:
    return {
        "round_id": round_id,
        "observation_id": f"obs_{uuid.uuid4().hex[:16]}",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_id": spec.reviewer_id,
        "reviewer_role": spec.role.value,
        "provider": spec.provider,
        "model": spec.model,
        "snapshot_id": snapshot_id,
        "snapshot_version": snapshot_version,
    }


def build_success_record(
    round_id: str,
    snapshot_id: str,
    snapshot_version: int,
    spec: ReviewerSpec,
    observation: Any,
    *,
    resolved_model: str | None = None,
) -> dict[str, Any]:
    record = _base_record(round_id, snapshot_id, snapshot_version, spec)
    if resolved_model:
        # What the provider actually reports having used (e.g. Hermes'
        # session-store lookup) takes priority over the config-declared
        # spec.model already in the base record — for providers where the
        # model is explicit in the request (Anthropic/OpenRouter) the two
        # always agree; for Hermes only this one is meaningful.
        record["model"] = resolved_model
    output = observation.model_dump(mode="json")
    record["output"] = output
    record["disagreements_with_other_reviewers"] = (
        output.get("disagreements_with_primary", []) if spec.role is ReviewerRole.CRITIQUE else []
    )
    return record


def build_failure_record(
    round_id: str, snapshot_id: str, snapshot_version: int, spec: ReviewerSpec, exc: Exception
) -> dict[str, Any]:
    record = _base_record(round_id, snapshot_id, snapshot_version, spec)
    record["error"] = str(exc)
    return record


def append_failed_attempt_records(
    observations_path: Path, round_id: str, snapshot_id: str, snapshot_version: int,
    spec: ReviewerSpec, attempts: list[dict[str, Any]], *, final_exception: Exception | None = None,
) -> None:
    """Writes one failure record per failed attempt in ``attempts`` (as
    produced by director_reviewers.run_reviewer's ``attempts_sink`` — see
    its bounded-transient-retry logic): 0 records for the common
    no-retry-needed path, 1 if a transient failure was retried into a
    success, 2 if the retry also failed. Call this exactly once per
    run_reviewer call, right after it returns OR right after it raises
    (passing the caught exception as ``final_exception`` in the latter
    case) — the eventual success record is still appended by the existing
    caller code around this; this only adds the audit trail.

    ``final_exception`` covers two cases the attempts_sink alone can't:
    a non-transient failure that happened before any attempt was even
    recorded (get_model_provider() itself failing, or a non-transient
    ModelProviderError from the provider call — attempts_sink stays empty
    in both), and a successful provider call whose result then failed
    schema validation or the APPROVED_TO_TEST status check (attempts_sink
    shows the call itself as succeeded, so nothing there reflects that
    later failure). In both cases exactly one additional failure record is
    written for it; when the sink's last entry is already a failed
    attempt, `final_exception` is redundant with it and skipped."""
    for attempt in attempts:
        if attempt["succeeded"]:
            continue
        record = build_failure_record(round_id, snapshot_id, snapshot_version, spec, RuntimeError(attempt["error"]))
        record["attempt_number"] = attempt["attempt"]
        append_record(observations_path, record)
    if final_exception is not None:
        sink_already_covers_it = bool(attempts) and not attempts[-1]["succeeded"]
        if not sink_already_covers_it:
            append_record(
                observations_path,
                build_failure_record(round_id, snapshot_id, snapshot_version, spec, final_exception),
            )


def render_founder_report(round_result: dict[str, Any]) -> str:
    lines = [
        "=" * 72,
        "DIRECTOR REVIEW ROUND (Level 1 — observation only, no action taken)",
        "=" * 72,
        f"Round:     {round_result['round_id']}",
        f"Snapshot:  {round_result['snapshot_id']}",
        f"           stored at {round_result['snapshot_path']}",
        "",
    ]
    any_candidate = False
    for rec in round_result["records"]:
        lines.append("-" * 72)
        lines.append(f"Reviewer:  {rec['reviewer_id']}  [{rec['reviewer_role']}]")
        model_suffix = f" ({rec['model']})" if rec.get("model") else ""
        lines.append(f"Provider:  {rec['provider']}{model_suffix}")
        if "error" in rec:
            lines.append(f"FAILED:    {rec['error']}")
            continue
        out = rec["output"]
        lines.append(f"Confidence: {out.get('confidence', 0):.2f}")
        lines.append(f"Status:    {out.get('status')}")
        if out.get("status") == "CANDIDATE_FOR_TESTING":
            any_candidate = True
        if rec["reviewer_role"] == ReviewerRole.PRIMARY.value:
            lines.append("Findings:")
            lines += [f"  - {f}" for f in out.get("findings", [])] or ["  (none)"]
            lines.append(f"Interpretation: {out.get('interpretation')}")
            lines.append(f"Recommendation ({out.get('recommendation_type')}): {out.get('recommendation')}")
            lines.append("Evidence:")
            lines += [f"  - {e}" for e in out.get("evidence", [])] or ["  (none)"]
        elif rec["reviewer_role"] == ReviewerRole.SYNTHESIS.value:
            lines.append("Hypothesis assessment:")
            lines += [
                f"  - [{h.get('likelihood', 0):.2f}] {h.get('hypothesis')}: {h.get('reasoning')}"
                for h in out.get("hypothesis_assessment", [])
            ] or ["  (none)"]
            lines.append("Disagreement handling:")
            lines += [
                f"  - [{d.get('resolution')}] {d.get('disagreement')} — {d.get('reasoning')}"
                for d in out.get("disagreement_handling", [])
            ] or ["  (none)"]
            lines.append("Unresolved uncertainty:")
            lines += [f"  - {u}" for u in out.get("unresolved_uncertainty", [])] or ["  (none)"]
            lines.append(f"Strategic recommendation: {out.get('strategic_recommendation')}")
            lines.append(
                f"Recommended next step ({out.get('recommendation_type')}): "
                f"{out.get('recommended_next_step')}"
            )
        else:
            lines.append(f"Findings supported by evidence?: {out.get('findings_supported_by_evidence')}")
            lines.append("Alternative explanations:")
            lines += [f"  - {a}" for a in out.get("alternative_explanations", [])] or ["  (none)"]
            lines.append("Unintended consequences:")
            lines += [f"  - {u}" for u in out.get("unintended_consequences", [])] or ["  (none)"]
            lines.append(f"Preserves agent autonomy?: {out.get('preserves_agent_autonomy')}")
            lines.append(
                f"Apparent improvement real or manufactured?: {out.get('apparent_improvement_assessment')}"
            )
            lines.append(f"Smaller/safer intervention: {out.get('smaller_safer_intervention')}")
            lines.append("Disagreements with primary reviewer:")
            lines += [f"  - {d}" for d in out.get("disagreements_with_primary", [])] or ["  (none)"]
    lines.append("-" * 72)
    lines.append(
        f"Founder approval required: {any_candidate} "
        "(True only if some reviewer marked CANDIDATE_FOR_TESTING — nothing here was approved "
        "or executed; APPROVED_TO_TEST can only ever be set by a human)"
    )
    lines.append("=" * 72)
    return "\n".join(lines)


def run_cycle(
    *,
    db_path: Path | None = None,
    cursor_path: Path = DEFAULT_CURSOR_PATH,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    reviewers_path: Path | None = None,
    max_events: int = 500,
    max_rows: int = 50,
) -> dict[str, Any]:
    cursor = load_cursor(cursor_path)
    since_event_id = int(cursor.get("last_event_id", 0))

    try:
        snapshot = build_snapshot(
            db_path=db_path,
            since_event_id=since_event_id,
            max_events=max_events,
            max_rows=max_rows,
        )
    except (DirectorSnapshotError, LiveDatabaseError) as exc:
        raise DirectorLoopError(f"snapshot failed, cursor unchanged: {exc}") from exc

    snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
    snapshot["snapshot_id"] = snapshot_id
    snapshot_version = snapshot["director_snapshot_version"]
    snapshot_path = persist_snapshot(snapshots_dir, snapshot_id, snapshot)

    specs = [s for s in load_reviewer_specs(reviewers_path) if s.enabled]
    primary_specs = [s for s in specs if s.role is ReviewerRole.PRIMARY]
    if len(primary_specs) != 1:
        raise DirectorLoopError(
            f"expected exactly one enabled PRIMARY reviewer, found {len(primary_specs)}. "
            "cursor unchanged (snapshot was still persisted at "
            f"{snapshot_path})."
        )
    primary_spec = primary_specs[0]
    critique_specs = [s for s in specs if s.role is ReviewerRole.CRITIQUE]

    round_id = f"round_{uuid.uuid4().hex[:16]}"
    records: list[dict[str, Any]] = []

    try:
        primary_observation, primary_model = run_reviewer(primary_spec, snapshot=snapshot)
    except ModelProviderError as exc:
        raise DirectorLoopError(
            f"primary reviewer {primary_spec.reviewer_id!r} failed, cursor unchanged: {exc}"
        ) from exc

    primary_record = build_success_record(
        round_id, snapshot_id, snapshot_version, primary_spec, primary_observation,
        resolved_model=primary_model,
    )
    append_record(observations_path, primary_record)
    records.append(primary_record)

    for spec in critique_specs:
        try:
            critique_observation, critique_model = run_reviewer(
                spec, snapshot=snapshot, primary_observation=primary_observation.model_dump(mode="json")
            )
        except ModelProviderError as exc:
            failure_record = build_failure_record(round_id, snapshot_id, snapshot_version, spec, exc)
            append_record(observations_path, failure_record)
            records.append(failure_record)
            continue
        critique_record = build_success_record(
            round_id, snapshot_id, snapshot_version, spec, critique_observation,
            resolved_model=critique_model,
        )
        append_record(observations_path, critique_record)
        records.append(critique_record)

    cursor["last_event_id"] = snapshot["window"]["through_event_id"]
    cursor["last_run_at"] = datetime.now(timezone.utc).isoformat()
    cursor["last_round_id"] = round_id
    save_cursor(cursor_path, cursor)

    # Bridge auto-update: the persistent round-history index is derived
    # entirely from observations_path + packets_dir, so refreshing it here
    # is what "automatically update as future Director rounds occur" means
    # in practice — no separate manual step, no drift between what
    # happened and what the bridge remembers happened.
    rebuild_rounds_history(observations_path=observations_path)

    return {
        "round_id": round_id,
        "snapshot_id": snapshot_id,
        "snapshot_path": str(snapshot_path),
        "records": records,
    }


def load_persisted_snapshot(snapshots_dir: Path, snapshot_id: str) -> dict[str, Any]:
    path = snapshots_dir / f"{snapshot_id}.json"
    if not path.exists():
        raise DirectorLoopError(f"no persisted snapshot at {path} — cannot attach a critique to it.")
    return json.loads(path.read_text())


def load_existing_primary_record(observations_path: Path, snapshot_id: str) -> dict[str, Any]:
    if not observations_path.exists():
        raise DirectorLoopError(
            f"no observations file at {observations_path}; cannot find a PRIMARY record for "
            f"snapshot_id={snapshot_id!r}."
        )
    matches = []
    with observations_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if (
                rec.get("snapshot_id") == snapshot_id
                and rec.get("reviewer_role") == ReviewerRole.PRIMARY.value
                and "output" in rec
            ):
                matches.append(rec)
    if not matches:
        raise DirectorLoopError(
            f"no successful PRIMARY record found for snapshot_id={snapshot_id!r} in {observations_path}."
        )
    return matches[-1]


def run_critique_for_existing_round(
    *,
    snapshot_id: str,
    reviewer_id: str,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    reviewers_path: Path | None = None,
) -> dict[str, Any]:
    """Attach exactly one additional CRITIQUE reviewer to an *existing*
    round: the snapshot at .director/snapshots/{snapshot_id}.json and the
    already-recorded PRIMARY observation for it, both loaded read-only and
    never regenerated. Never touches the cursor — no new event window was
    consumed, since no new snapshot was built. Never reruns the PRIMARY
    reviewer.

    Looks the reviewer up by reviewer_id directly, deliberately ignoring
    its `enabled` flag in reviewers.json: naming a reviewer explicitly here
    *is* the deliberate act of running it once, distinct from `enabled`,
    which governs whether run_cycle() includes it automatically in every
    future fresh round."""
    snapshot = load_persisted_snapshot(snapshots_dir, snapshot_id)
    primary_record = load_existing_primary_record(observations_path, snapshot_id)
    round_id = primary_record["round_id"]
    snapshot_version = primary_record["snapshot_version"]

    specs_by_id = {s.reviewer_id: s for s in load_reviewer_specs(reviewers_path)}
    spec = specs_by_id.get(reviewer_id)
    if spec is None:
        raise DirectorLoopError(
            f"reviewer_id {reviewer_id!r} not found in reviewer config "
            f"(known: {sorted(specs_by_id)})."
        )
    if spec.role is not ReviewerRole.CRITIQUE:
        raise DirectorLoopError(f"reviewer_id {reviewer_id!r} is role {spec.role.value}, not CRITIQUE.")

    try:
        critique_observation, critique_model = run_reviewer(
            spec, snapshot=snapshot, primary_observation=primary_record["output"]
        )
    except ModelProviderError as exc:
        failure_record = build_failure_record(round_id, snapshot_id, snapshot_version, spec, exc)
        append_record(observations_path, failure_record)
        raise DirectorLoopError(f"critique reviewer {reviewer_id!r} failed: {exc}") from exc

    critique_record = build_success_record(
        round_id, snapshot_id, snapshot_version, spec, critique_observation,
        resolved_model=critique_model,
    )
    append_record(observations_path, critique_record)

    rebuild_rounds_history(observations_path=observations_path)

    return {
        "round_id": round_id,
        "snapshot_id": snapshot_id,
        "snapshot_path": str(snapshots_dir / f"{snapshot_id}.json"),
        "records": [primary_record, critique_record],
    }


def load_records_for_round(
    observations_path: Path, round_id: str, *, role: str | None = None
) -> list[dict[str, Any]]:
    """All successful records for round_id, optionally filtered to one
    reviewer_role. Read-only over the existing observations log."""
    if not observations_path.exists():
        raise DirectorLoopError(f"no observations file at {observations_path}.")
    out = []
    with observations_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("round_id") != round_id or "output" not in rec:
                continue
            if role is not None and rec.get("reviewer_role") != role:
                continue
            out.append(rec)
    return out


def load_reconciliation_packet(packets_dir: Path, round_id: str) -> dict[str, Any]:
    path = packets_dir / f"{round_id}.json"
    if not path.exists():
        raise DirectorLoopError(
            f"no deterministic reconciliation packet at {path} — SYNTHESIS requires one to already "
            "exist (run scripts/director_synthesis.py for this round first)."
        )
    return json.loads(path.read_text())


def build_final_founder_packet(
    *,
    round_id: str,
    snapshot_id: str,
    snapshot_version: int,
    primary_record: dict[str, Any],
    critique_records: list[dict[str, Any]],
    synthesis_record: dict[str, Any],
    reconciliation_packet: dict[str, Any],
    bridge_context: dict[str, Any],
) -> dict[str, Any]:
    """The final Founder-facing packet: the deterministic reconciliation
    packet embedded verbatim (never replaced) plus the SYNTHESIS reviewer's
    strategic recommendation layered on top, plus every reviewer identity
    and the exact bridge context the synthesis reviewer was given — full
    audit trail, nothing hidden."""
    synthesis_output = synthesis_record["output"]
    return {
        "round_id": round_id,
        "snapshot_id": snapshot_id,
        "snapshot_version": snapshot_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewers": {
            "primary": {
                "reviewer_id": primary_record["reviewer_id"], "provider": primary_record["provider"],
                "model": primary_record.get("model"), "confidence": primary_record["output"]["confidence"],
                "status": primary_record["output"]["status"],
            },
            "critiques": [
                {
                    "reviewer_id": r["reviewer_id"], "provider": r["provider"], "model": r.get("model"),
                    "confidence": r["output"]["confidence"], "status": r["output"]["status"],
                }
                for r in critique_records
            ],
            "synthesis": {
                "reviewer_id": synthesis_record["reviewer_id"], "provider": synthesis_record["provider"],
                "model": synthesis_record.get("model"), "confidence": synthesis_output["confidence"],
                "status": synthesis_output["status"],
            },
        },
        "deterministic_reconciliation_packet": reconciliation_packet,
        "strategic_synthesis": synthesis_output,
        "bridge_context_supplied": bridge_context,
        "recommendation_type": synthesis_output["recommendation_type"],
        "recommendation_status": synthesis_output["status"],
        "founder_approval_required": True,
    }


def run_synthesis_for_existing_round(
    *,
    round_id: str,
    reviewer_id: str,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    reviewers_path: Path | None = None,
) -> dict[str, Any]:
    """Run exactly one SYNTHESIS reviewer against an *existing* round: the
    persisted snapshot, the existing PRIMARY record, every existing
    CRITIQUE record, and the existing deterministic reconciliation packet
    — all loaded read-only, none regenerated or rerun. Also loads bounded
    persistent Director context from the bridge. Never touches the
    cursor. Saves the SYNTHESIS reviewer's own record to observations.jsonl
    and a new, separate final Founder Packet to
    .director/packets/{round_id}_final.json — the deterministic
    reconciliation packet at .director/packets/{round_id}.json is read,
    embedded, and never overwritten."""
    primary_records = load_records_for_round(observations_path, round_id, role="PRIMARY")
    if not primary_records:
        raise DirectorLoopError(f"no successful PRIMARY record found for round_id={round_id!r}.")
    primary_record = primary_records[-1]
    critique_records = load_records_for_round(observations_path, round_id, role="CRITIQUE")
    if not critique_records:
        raise DirectorLoopError(f"no successful CRITIQUE record found for round_id={round_id!r}.")

    snapshot_id = primary_record["snapshot_id"]
    snapshot_version = primary_record["snapshot_version"]
    snapshot = load_persisted_snapshot(snapshots_dir, snapshot_id)
    reconciliation_packet = load_reconciliation_packet(packets_dir, round_id)
    bridge_context = get_relevant_history()

    specs_by_id = {s.reviewer_id: s for s in load_reviewer_specs(reviewers_path)}
    spec = specs_by_id.get(reviewer_id)
    if spec is None:
        raise DirectorLoopError(
            f"reviewer_id {reviewer_id!r} not found in reviewer config (known: {sorted(specs_by_id)})."
        )
    if spec.role is not ReviewerRole.SYNTHESIS:
        raise DirectorLoopError(f"reviewer_id {reviewer_id!r} is role {spec.role.value}, not SYNTHESIS.")

    synthesis_attempts: list[dict[str, Any]] = []
    try:
        synthesis_observation, synthesis_model = run_reviewer(
            spec,
            snapshot=snapshot,
            primary_observation=primary_record["output"],
            critique_observations=[r["output"] for r in critique_records],
            reconciliation_packet=reconciliation_packet,
            bridge_context=bridge_context,
            attempts_sink=synthesis_attempts,
        )
    except ModelProviderError as exc:
        append_failed_attempt_records(
            observations_path, round_id, snapshot_id, snapshot_version, spec, synthesis_attempts,
            final_exception=exc,
        )
        raise DirectorLoopError(f"synthesis reviewer {reviewer_id!r} failed: {exc}") from exc
    append_failed_attempt_records(observations_path, round_id, snapshot_id, snapshot_version, spec, synthesis_attempts)

    synthesis_record = build_success_record(
        round_id, snapshot_id, snapshot_version, spec, synthesis_observation,
        resolved_model=synthesis_model,
    )
    append_record(observations_path, synthesis_record)

    final_packet = build_final_founder_packet(
        round_id=round_id, snapshot_id=snapshot_id, snapshot_version=snapshot_version,
        primary_record=primary_record, critique_records=critique_records,
        synthesis_record=synthesis_record, reconciliation_packet=reconciliation_packet,
        bridge_context=bridge_context,
    )
    packets_dir.mkdir(parents=True, exist_ok=True)
    final_packet_path = packets_dir / f"{round_id}_final.json"
    final_packet_path.write_text(json.dumps(final_packet, indent=2, default=str) + "\n")

    rebuild_rounds_history(observations_path=observations_path, packets_dir=packets_dir)

    return {
        "round_id": round_id,
        "snapshot_id": snapshot_id,
        "snapshot_path": str(snapshots_dir / f"{snapshot_id}.json"),
        "final_packet_path": str(final_packet_path),
        "records": [primary_record, *critique_records, synthesis_record],
    }


def run_diagnostic_review_chain(
    *,
    diagnostic_id: str,
    primary_reviewer_id: str = "director-primary",
    critique_reviewer_ids: list[str] | None = None,
    synthesis_reviewer_id: str = "openai-synthesis",
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR,
    reviewers_path: Path | None = None,
) -> dict[str, Any]:
    """Level 2A, step 2: after a diagnostic reaches DIAGNOSTIC_COMPLETE
    with run_status SUCCESS, feed its evidence back through the full
    review chain — PRIMARY, CRITIQUE, deterministic (generic, mechanical)
    reconciliation, SYNTHESIS — as a brand-new round.

    The original round and its snapshot are never touched: a NEW,
    immutable, diagnostic-augmented snapshot is built (the original
    snapshot's full content plus the diagnostic's evidence — nothing
    removed or rewritten) and given its own snapshot_id. Never touches the
    cursor — no new live-DB event window was consumed; this round is
    evidence-driven, not event-driven. Reviewer ids are looked up
    explicitly (same as run_critique_for_existing_round /
    run_synthesis_for_existing_round) — this call is itself the deliberate
    act, independent of each reviewer's `enabled` flag in reviewers.json."""
    diag_spec = load_diagnostic_spec(diagnostic_id, diagnostics_dir)
    if diag_spec.state is not DiagnosticState.DIAGNOSTIC_COMPLETE or diag_spec.run_status != "SUCCESS":
        raise DirectorLoopError(
            f"diagnostic {diagnostic_id!r} is state={diag_spec.state.value} run_status="
            f"{diag_spec.run_status!r} — refusing to feed an incomplete or failed diagnostic into "
            "the review chain."
        )
    diagnostic_evidence = load_diagnostic_evidence(diagnostic_id, diagnostics_dir)

    original_round_id = diag_spec.originating_round_id
    original_primary_records = load_records_for_round(observations_path, original_round_id, role="PRIMARY")
    if not original_primary_records:
        raise DirectorLoopError(f"no PRIMARY record found for originating round {original_round_id!r}.")
    original_snapshot_id = original_primary_records[-1]["snapshot_id"]
    original_snapshot = load_persisted_snapshot(snapshots_dir, original_snapshot_id)

    new_snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
    augmented_snapshot = {
        **original_snapshot,
        "snapshot_id": new_snapshot_id,
        "snapshot_kind": "diagnostic_augmented",
        "based_on_snapshot_id": original_snapshot_id,
        "diagnostic_evidence": {
            "diagnostic_id": diag_spec.diagnostic_id,
            "diagnostic_type": diag_spec.diagnostic_type,
            "originating_round_id": diag_spec.originating_round_id,
            "originating_recommendation": diag_spec.originating_recommendation,
            "scope": diag_spec.scope,
            "success_criteria": diag_spec.success_criteria,
            "completed_at": diag_spec.completed_at,
            "evidence": diagnostic_evidence,
        },
    }
    snapshot_version = augmented_snapshot.get("director_snapshot_version", 1)
    snapshot_path = persist_snapshot(snapshots_dir, new_snapshot_id, augmented_snapshot)

    new_round_id = f"round_{uuid.uuid4().hex[:16]}"
    critique_reviewer_ids = critique_reviewer_ids or ["hermes"]
    specs_by_id = {s.reviewer_id: s for s in load_reviewer_specs(reviewers_path)}

    primary_spec = specs_by_id.get(primary_reviewer_id)
    if primary_spec is None or primary_spec.role is not ReviewerRole.PRIMARY:
        raise DirectorLoopError(f"reviewer_id {primary_reviewer_id!r} is not a valid PRIMARY reviewer.")
    critique_specs = []
    for rid in critique_reviewer_ids:
        spec = specs_by_id.get(rid)
        if spec is None or spec.role is not ReviewerRole.CRITIQUE:
            raise DirectorLoopError(f"reviewer_id {rid!r} is not a valid CRITIQUE reviewer.")
        critique_specs.append(spec)
    synthesis_spec = specs_by_id.get(synthesis_reviewer_id)
    if synthesis_spec is None or synthesis_spec.role is not ReviewerRole.SYNTHESIS:
        raise DirectorLoopError(f"reviewer_id {synthesis_reviewer_id!r} is not a valid SYNTHESIS reviewer.")

    primary_attempts: list[dict[str, Any]] = []
    try:
        primary_observation, primary_model = run_reviewer(
            primary_spec, snapshot=augmented_snapshot, attempts_sink=primary_attempts,
        )
    except ModelProviderError as exc:
        append_failed_attempt_records(
            observations_path, new_round_id, new_snapshot_id, snapshot_version, primary_spec,
            primary_attempts, final_exception=exc,
        )
        raise DirectorLoopError(f"primary reviewer {primary_reviewer_id!r} failed: {exc}") from exc
    append_failed_attempt_records(
        observations_path, new_round_id, new_snapshot_id, snapshot_version, primary_spec, primary_attempts,
    )
    primary_record = build_success_record(
        new_round_id, new_snapshot_id, snapshot_version, primary_spec, primary_observation,
        resolved_model=primary_model,
    )
    append_record(observations_path, primary_record)

    critique_records: list[dict[str, Any]] = []
    for spec in critique_specs:
        critique_attempts: list[dict[str, Any]] = []
        try:
            critique_observation, critique_model = run_reviewer(
                spec, snapshot=augmented_snapshot,
                primary_observation=primary_observation.model_dump(mode="json"),
                attempts_sink=critique_attempts,
            )
        except ModelProviderError as exc:
            append_failed_attempt_records(
                observations_path, new_round_id, new_snapshot_id, snapshot_version, spec,
                critique_attempts, final_exception=exc,
            )
            continue
        append_failed_attempt_records(
            observations_path, new_round_id, new_snapshot_id, snapshot_version, spec, critique_attempts,
        )
        critique_record = build_success_record(
            new_round_id, new_snapshot_id, snapshot_version, spec, critique_observation,
            resolved_model=critique_model,
        )
        append_record(observations_path, critique_record)
        critique_records.append(critique_record)

    if not critique_records:
        raise DirectorLoopError("every CRITIQUE reviewer failed — refusing to reconcile with zero critiques.")

    reconciliation_packet = build_generic_reconciliation_packet(
        new_round_id, {"primary": primary_record, "critiques": critique_records}
    )
    packets_dir.mkdir(parents=True, exist_ok=True)
    (packets_dir / f"{new_round_id}.json").write_text(
        json.dumps(reconciliation_packet, indent=2, default=str) + "\n"
    )

    rebuild_rounds_history(observations_path=observations_path, packets_dir=packets_dir)

    synthesis_result = run_synthesis_for_existing_round(
        round_id=new_round_id, reviewer_id=synthesis_reviewer_id,
        observations_path=observations_path, snapshots_dir=snapshots_dir,
        packets_dir=packets_dir, reviewers_path=reviewers_path,
    )

    return {
        "diagnostic_id": diagnostic_id,
        "original_round_id": original_round_id,
        "new_round_id": new_round_id,
        "new_snapshot_id": new_snapshot_id,
        "snapshot_path": str(snapshot_path),
        "final_packet_path": synthesis_result["final_packet_path"],
        "records": synthesis_result["records"],
    }


def run_experiment_review_chain(
    *,
    experiment_id: str,
    primary_reviewer_id: str = "director-primary",
    critique_reviewer_ids: list[str] | None = None,
    synthesis_reviewer_id: str = "openai-synthesis",
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR,
    reviewers_path: Path | None = None,
) -> dict[str, Any]:
    """Level 2B, step 2: exact structural twin of run_diagnostic_review_chain
    (same augmented-snapshot pattern, same safety posture: original
    round/snapshot untouched, new immutable snapshot with its own id, cursor
    never touched, reviewer ids looked up explicitly) but for a completed
    Level 2B EXPERIMENT_COMPLETE/SUCCESS experiment instead of a Level 2A
    diagnostic — see director_experiments.py. Includes the same bounded
    transient-provider retry and dual-attempt recording as
    run_diagnostic_review_chain."""
    exp_spec = load_experiment_spec(experiment_id, experiments_dir)
    if exp_spec.state is not ExperimentState.EXPERIMENT_COMPLETE or exp_spec.run_status != "SUCCESS":
        raise DirectorLoopError(
            f"experiment {experiment_id!r} is state={exp_spec.state.value} run_status="
            f"{exp_spec.run_status!r} — refusing to feed an incomplete or failed experiment into "
            "the review chain."
        )
    experiment_evidence = load_experiment_evidence(experiment_id, experiments_dir)

    original_round_id = exp_spec.originating_round_id
    original_primary_records = load_records_for_round(observations_path, original_round_id, role="PRIMARY")
    if not original_primary_records:
        raise DirectorLoopError(f"no PRIMARY record found for originating round {original_round_id!r}.")
    original_snapshot_id = original_primary_records[-1]["snapshot_id"]
    original_snapshot = load_persisted_snapshot(snapshots_dir, original_snapshot_id)

    new_snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
    augmented_snapshot = {
        **original_snapshot,
        "snapshot_id": new_snapshot_id,
        "snapshot_kind": "experiment_augmented",
        "based_on_snapshot_id": original_snapshot_id,
        "experiment_evidence": {
            "experiment_id": exp_spec.experiment_id,
            "experiment_type": exp_spec.experiment_type,
            "originating_round_id": exp_spec.originating_round_id,
            "originating_recommendation": exp_spec.originating_recommendation,
            "scope": exp_spec.scope,
            "success_criteria": exp_spec.success_criteria,
            "completed_at": exp_spec.completed_at,
            "evidence": experiment_evidence,
        },
    }
    snapshot_version = augmented_snapshot.get("director_snapshot_version", 1)
    snapshot_path = persist_snapshot(snapshots_dir, new_snapshot_id, augmented_snapshot)

    new_round_id = f"round_{uuid.uuid4().hex[:16]}"
    critique_reviewer_ids = critique_reviewer_ids or ["hermes"]
    specs_by_id = {s.reviewer_id: s for s in load_reviewer_specs(reviewers_path)}

    primary_spec = specs_by_id.get(primary_reviewer_id)
    if primary_spec is None or primary_spec.role is not ReviewerRole.PRIMARY:
        raise DirectorLoopError(f"reviewer_id {primary_reviewer_id!r} is not a valid PRIMARY reviewer.")
    critique_specs = []
    for rid in critique_reviewer_ids:
        spec = specs_by_id.get(rid)
        if spec is None or spec.role is not ReviewerRole.CRITIQUE:
            raise DirectorLoopError(f"reviewer_id {rid!r} is not a valid CRITIQUE reviewer.")
        critique_specs.append(spec)
    synthesis_spec = specs_by_id.get(synthesis_reviewer_id)
    if synthesis_spec is None or synthesis_spec.role is not ReviewerRole.SYNTHESIS:
        raise DirectorLoopError(f"reviewer_id {synthesis_reviewer_id!r} is not a valid SYNTHESIS reviewer.")

    primary_attempts: list[dict[str, Any]] = []
    try:
        primary_observation, primary_model = run_reviewer(
            primary_spec, snapshot=augmented_snapshot, attempts_sink=primary_attempts,
        )
    except ModelProviderError as exc:
        append_failed_attempt_records(
            observations_path, new_round_id, new_snapshot_id, snapshot_version, primary_spec,
            primary_attempts, final_exception=exc,
        )
        raise DirectorLoopError(f"primary reviewer {primary_reviewer_id!r} failed: {exc}") from exc
    append_failed_attempt_records(
        observations_path, new_round_id, new_snapshot_id, snapshot_version, primary_spec, primary_attempts,
    )
    primary_record = build_success_record(
        new_round_id, new_snapshot_id, snapshot_version, primary_spec, primary_observation,
        resolved_model=primary_model,
    )
    append_record(observations_path, primary_record)

    critique_records: list[dict[str, Any]] = []
    for spec in critique_specs:
        critique_attempts: list[dict[str, Any]] = []
        try:
            critique_observation, critique_model = run_reviewer(
                spec, snapshot=augmented_snapshot,
                primary_observation=primary_observation.model_dump(mode="json"),
                attempts_sink=critique_attempts,
            )
        except ModelProviderError as exc:
            append_failed_attempt_records(
                observations_path, new_round_id, new_snapshot_id, snapshot_version, spec,
                critique_attempts, final_exception=exc,
            )
            continue
        append_failed_attempt_records(
            observations_path, new_round_id, new_snapshot_id, snapshot_version, spec, critique_attempts,
        )
        critique_record = build_success_record(
            new_round_id, new_snapshot_id, snapshot_version, spec, critique_observation,
            resolved_model=critique_model,
        )
        append_record(observations_path, critique_record)
        critique_records.append(critique_record)

    if not critique_records:
        raise DirectorLoopError("every CRITIQUE reviewer failed — refusing to reconcile with zero critiques.")

    reconciliation_packet = build_generic_reconciliation_packet(
        new_round_id, {"primary": primary_record, "critiques": critique_records}
    )
    packets_dir.mkdir(parents=True, exist_ok=True)
    (packets_dir / f"{new_round_id}.json").write_text(
        json.dumps(reconciliation_packet, indent=2, default=str) + "\n"
    )

    rebuild_rounds_history(observations_path=observations_path, packets_dir=packets_dir)

    synthesis_result = run_synthesis_for_existing_round(
        round_id=new_round_id, reviewer_id=synthesis_reviewer_id,
        observations_path=observations_path, snapshots_dir=snapshots_dir,
        packets_dir=packets_dir, reviewers_path=reviewers_path,
    )

    return {
        "experiment_id": experiment_id,
        "original_round_id": original_round_id,
        "new_round_id": new_round_id,
        "new_snapshot_id": new_snapshot_id,
        "snapshot_path": str(snapshot_path),
        "final_packet_path": synthesis_result["final_packet_path"],
        "records": synthesis_result["records"],
    }


def run_design_proposal_review_chain(
    *,
    originating_round_id: str,
    design_proposal: dict[str, Any],
    primary_reviewer_id: str = "director-primary",
    critique_reviewer_ids: list[str] | None = None,
    synthesis_reviewer_id: str = "openai-synthesis",
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    reviewers_path: Path | None = None,
) -> dict[str, Any]:
    """A genuinely different kind of round from run_diagnostic_review_chain:
    no diagnostic is executed here, no new evidence is generated — this
    feeds an authored, Claude-written experimental-design proposal (the
    design_proposal dict, embedded verbatim into a new augmented snapshot
    alongside the originating round's existing evidence) through the same
    PRIMARY -> CRITIQUE -> deterministic reconciliation -> SYNTHESIS chain,
    so the reviewers evaluate the PROPOSAL itself — not run anything, not
    produce new facts. Same safety posture as run_diagnostic_review_chain:
    the originating round/snapshot are untouched, a new immutable snapshot
    is built and given its own id, the cursor is never touched (no new
    live-DB event window), and reviewer ids are looked up explicitly."""
    original_primary_records = load_records_for_round(observations_path, originating_round_id, role="PRIMARY")
    if not original_primary_records:
        raise DirectorLoopError(f"no PRIMARY record found for originating round {originating_round_id!r}.")
    original_snapshot_id = original_primary_records[-1]["snapshot_id"]
    original_snapshot = load_persisted_snapshot(snapshots_dir, original_snapshot_id)

    new_snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
    augmented_snapshot = {
        **original_snapshot,
        "snapshot_id": new_snapshot_id,
        "snapshot_kind": "design_proposal_augmented",
        "based_on_snapshot_id": original_snapshot_id,
        "design_proposal": design_proposal,
    }
    snapshot_version = augmented_snapshot.get("director_snapshot_version", 1)
    snapshot_path = persist_snapshot(snapshots_dir, new_snapshot_id, augmented_snapshot)

    new_round_id = f"round_{uuid.uuid4().hex[:16]}"
    critique_reviewer_ids = critique_reviewer_ids or ["hermes"]
    specs_by_id = {s.reviewer_id: s for s in load_reviewer_specs(reviewers_path)}

    primary_spec = specs_by_id.get(primary_reviewer_id)
    if primary_spec is None or primary_spec.role is not ReviewerRole.PRIMARY:
        raise DirectorLoopError(f"reviewer_id {primary_reviewer_id!r} is not a valid PRIMARY reviewer.")
    critique_specs = []
    for rid in critique_reviewer_ids:
        spec = specs_by_id.get(rid)
        if spec is None or spec.role is not ReviewerRole.CRITIQUE:
            raise DirectorLoopError(f"reviewer_id {rid!r} is not a valid CRITIQUE reviewer.")
        critique_specs.append(spec)
    synthesis_spec = specs_by_id.get(synthesis_reviewer_id)
    if synthesis_spec is None or synthesis_spec.role is not ReviewerRole.SYNTHESIS:
        raise DirectorLoopError(f"reviewer_id {synthesis_reviewer_id!r} is not a valid SYNTHESIS reviewer.")

    try:
        primary_observation, primary_model = run_reviewer(primary_spec, snapshot=augmented_snapshot)
    except ModelProviderError as exc:
        raise DirectorLoopError(f"primary reviewer {primary_reviewer_id!r} failed: {exc}") from exc
    primary_record = build_success_record(
        new_round_id, new_snapshot_id, snapshot_version, primary_spec, primary_observation,
        resolved_model=primary_model,
    )
    append_record(observations_path, primary_record)

    critique_records: list[dict[str, Any]] = []
    for spec in critique_specs:
        try:
            critique_observation, critique_model = run_reviewer(
                spec, snapshot=augmented_snapshot,
                primary_observation=primary_observation.model_dump(mode="json"),
            )
        except ModelProviderError as exc:
            failure_record = build_failure_record(new_round_id, new_snapshot_id, snapshot_version, spec, exc)
            append_record(observations_path, failure_record)
            continue
        critique_record = build_success_record(
            new_round_id, new_snapshot_id, snapshot_version, spec, critique_observation,
            resolved_model=critique_model,
        )
        append_record(observations_path, critique_record)
        critique_records.append(critique_record)

    if not critique_records:
        raise DirectorLoopError("every CRITIQUE reviewer failed — refusing to reconcile with zero critiques.")

    reconciliation_packet = build_generic_reconciliation_packet(
        new_round_id, {"primary": primary_record, "critiques": critique_records}
    )
    packets_dir.mkdir(parents=True, exist_ok=True)
    (packets_dir / f"{new_round_id}.json").write_text(
        json.dumps(reconciliation_packet, indent=2, default=str) + "\n"
    )

    rebuild_rounds_history(observations_path=observations_path, packets_dir=packets_dir)

    synthesis_result = run_synthesis_for_existing_round(
        round_id=new_round_id, reviewer_id=synthesis_reviewer_id,
        observations_path=observations_path, snapshots_dir=snapshots_dir,
        packets_dir=packets_dir, reviewers_path=reviewers_path,
    )

    return {
        "originating_round_id": originating_round_id,
        "new_round_id": new_round_id,
        "new_snapshot_id": new_snapshot_id,
        "snapshot_path": str(snapshot_path),
        "final_packet_path": synthesis_result["final_packet_path"],
        "records": synthesis_result["records"],
    }


def run_level2b_experiment_review_chain(
    *,
    originating_round_id: str,
    level2b_evidence: dict[str, Any],
    review_question: str,
    review_scope_constraint: str,
    primary_reviewer_id: str = "director-primary",
    critique_reviewer_ids: list[str] | None = None,
    synthesis_reviewer_id: str = "openai-synthesis",
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    reviewers_path: Path | None = None,
) -> dict[str, Any]:
    """Level 2B, step 2: feed the results of an already-executed, disposable,
    isolated A/B experiment (director_level2b_experiment.py's evidence dict —
    no diagnostic runs here, no live/isolated DB access, nothing is executed
    by this function) through the same PRIMARY -> CRITIQUE -> deterministic
    reconciliation -> SYNTHESIS chain as run_diagnostic_review_chain /
    run_design_proposal_review_chain, but scoped to a Founder-specified
    review_question (embedded verbatim into the snapshot's JSON, which is
    what every reviewer role actually reads — see director_reviewers.
    run_reviewer) and a review_scope_constraint stating what the review must
    NOT conclude. Same safety posture: the originating round/snapshot are
    never touched, a new immutable snapshot is built and given its own id,
    the cursor is never touched (no new live-DB event window was consumed —
    this round is evidence-driven), and reviewer ids are looked up
    explicitly, independent of each reviewer's `enabled` flag."""
    original_primary_records = load_records_for_round(observations_path, originating_round_id, role="PRIMARY")
    if not original_primary_records:
        raise DirectorLoopError(f"no PRIMARY record found for originating round {originating_round_id!r}.")
    original_snapshot_id = original_primary_records[-1]["snapshot_id"]
    original_snapshot = load_persisted_snapshot(snapshots_dir, original_snapshot_id)

    new_snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
    augmented_snapshot = {
        **original_snapshot,
        "snapshot_id": new_snapshot_id,
        "snapshot_kind": "level2b_experiment_augmented",
        "based_on_snapshot_id": original_snapshot_id,
        "review_question": review_question,
        "review_scope_constraint": review_scope_constraint,
        "level2b_ab_experiment_evidence": level2b_evidence,
    }
    snapshot_version = augmented_snapshot.get("director_snapshot_version", 1)
    snapshot_path = persist_snapshot(snapshots_dir, new_snapshot_id, augmented_snapshot)

    new_round_id = f"round_{uuid.uuid4().hex[:16]}"
    critique_reviewer_ids = critique_reviewer_ids or ["hermes"]
    specs_by_id = {s.reviewer_id: s for s in load_reviewer_specs(reviewers_path)}

    primary_spec = specs_by_id.get(primary_reviewer_id)
    if primary_spec is None or primary_spec.role is not ReviewerRole.PRIMARY:
        raise DirectorLoopError(f"reviewer_id {primary_reviewer_id!r} is not a valid PRIMARY reviewer.")
    critique_specs = []
    for rid in critique_reviewer_ids:
        spec = specs_by_id.get(rid)
        if spec is None or spec.role is not ReviewerRole.CRITIQUE:
            raise DirectorLoopError(f"reviewer_id {rid!r} is not a valid CRITIQUE reviewer.")
        critique_specs.append(spec)
    synthesis_spec = specs_by_id.get(synthesis_reviewer_id)
    if synthesis_spec is None or synthesis_spec.role is not ReviewerRole.SYNTHESIS:
        raise DirectorLoopError(f"reviewer_id {synthesis_reviewer_id!r} is not a valid SYNTHESIS reviewer.")

    try:
        primary_observation, primary_model = run_reviewer(primary_spec, snapshot=augmented_snapshot)
    except ModelProviderError as exc:
        raise DirectorLoopError(f"primary reviewer {primary_reviewer_id!r} failed: {exc}") from exc
    primary_record = build_success_record(
        new_round_id, new_snapshot_id, snapshot_version, primary_spec, primary_observation,
        resolved_model=primary_model,
    )
    append_record(observations_path, primary_record)

    critique_records: list[dict[str, Any]] = []
    for spec in critique_specs:
        try:
            critique_observation, critique_model = run_reviewer(
                spec, snapshot=augmented_snapshot,
                primary_observation=primary_observation.model_dump(mode="json"),
            )
        except ModelProviderError as exc:
            failure_record = build_failure_record(new_round_id, new_snapshot_id, snapshot_version, spec, exc)
            append_record(observations_path, failure_record)
            continue
        critique_record = build_success_record(
            new_round_id, new_snapshot_id, snapshot_version, spec, critique_observation,
            resolved_model=critique_model,
        )
        append_record(observations_path, critique_record)
        critique_records.append(critique_record)

    if not critique_records:
        raise DirectorLoopError("every CRITIQUE reviewer failed — refusing to reconcile with zero critiques.")

    reconciliation_packet = build_generic_reconciliation_packet(
        new_round_id, {"primary": primary_record, "critiques": critique_records}
    )
    packets_dir.mkdir(parents=True, exist_ok=True)
    (packets_dir / f"{new_round_id}.json").write_text(
        json.dumps(reconciliation_packet, indent=2, default=str) + "\n"
    )

    rebuild_rounds_history(observations_path=observations_path, packets_dir=packets_dir)

    synthesis_result = run_synthesis_for_existing_round(
        round_id=new_round_id, reviewer_id=synthesis_reviewer_id,
        observations_path=observations_path, snapshots_dir=snapshots_dir,
        packets_dir=packets_dir, reviewers_path=reviewers_path,
    )

    return {
        "originating_round_id": originating_round_id,
        "new_round_id": new_round_id,
        "new_snapshot_id": new_snapshot_id,
        "snapshot_path": str(snapshot_path),
        "final_packet_path": synthesis_result["final_packet_path"],
        "records": synthesis_result["records"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--cursor-path", type=Path, default=DEFAULT_CURSOR_PATH)
    parser.add_argument("--observations-path", type=Path, default=DEFAULT_OBSERVATIONS_PATH)
    parser.add_argument("--snapshots-dir", type=Path, default=DEFAULT_SNAPSHOTS_DIR)
    parser.add_argument("--reviewers-path", type=Path, default=None)
    parser.add_argument("--max-events", type=int, default=500)
    parser.add_argument("--max-rows", type=int, default=50)
    parser.add_argument(
        "--critique-snapshot-id", type=str, default=None,
        help="Attach one CRITIQUE reviewer to an existing, already-persisted snapshot/round instead "
        "of running a fresh cycle. Never regenerates the snapshot, never reruns PRIMARY, never "
        "touches the cursor. Requires --critique-reviewer-id.",
    )
    parser.add_argument(
        "--critique-reviewer-id", type=str, default=None,
        help="Which reviewer_id from reviewers.json to run in --critique-snapshot-id mode.",
    )
    parser.add_argument(
        "--synthesize-round-id", type=str, default=None,
        help="Run one SYNTHESIS reviewer against an existing round's persisted snapshot, PRIMARY "
        "record, CRITIQUE record(s), and deterministic reconciliation packet. Never regenerates "
        "the snapshot, never reruns PRIMARY/CRITIQUE, never touches the cursor, never replaces the "
        "deterministic packet. Requires --synthesis-reviewer-id.",
    )
    parser.add_argument(
        "--synthesis-reviewer-id", type=str, default=None,
        help="Which reviewer_id from reviewers.json to run in --synthesize-round-id mode.",
    )
    parser.add_argument("--packets-dir", type=Path, default=DEFAULT_PACKETS_DIR)
    parser.add_argument(
        "--diagnostic-review-chain", type=str, default=None, metavar="DIAGNOSTIC_ID",
        help="Level 2A step 2: feed a DIAGNOSTIC_COMPLETE diagnostic's evidence back through "
        "PRIMARY -> CRITIQUE -> deterministic reconciliation -> SYNTHESIS as a brand-new round. "
        "Never touches the original round/snapshot/cursor.",
    )
    parser.add_argument("--diagnostics-dir", type=Path, default=DEFAULT_DIAGNOSTICS_DIR)
    args = parser.parse_args()

    if args.diagnostic_review_chain:
        try:
            round_result = run_diagnostic_review_chain(
                diagnostic_id=args.diagnostic_review_chain,
                observations_path=args.observations_path,
                snapshots_dir=args.snapshots_dir,
                packets_dir=args.packets_dir,
                diagnostics_dir=args.diagnostics_dir,
                reviewers_path=args.reviewers_path,
            )
        except DirectorLoopError as exc:
            print(f"director_loop: FAILED: {exc}", file=sys.stderr)
            return 1
        print(render_founder_report({
            "round_id": round_result["new_round_id"],
            "snapshot_id": round_result["new_snapshot_id"],
            "snapshot_path": round_result["snapshot_path"],
            "records": round_result["records"],
        }))
        print(f"\nOriginating round (preserved, untouched): {round_result['original_round_id']}")
        print(f"Final Founder Packet saved to: {round_result['final_packet_path']}")
        return 0

    if args.synthesize_round_id:
        if not args.synthesis_reviewer_id:
            print("director_loop: --synthesize-round-id requires --synthesis-reviewer-id", file=sys.stderr)
            return 1
        try:
            round_result = run_synthesis_for_existing_round(
                round_id=args.synthesize_round_id,
                reviewer_id=args.synthesis_reviewer_id,
                observations_path=args.observations_path,
                snapshots_dir=args.snapshots_dir,
                packets_dir=args.packets_dir,
                reviewers_path=args.reviewers_path,
            )
        except DirectorLoopError as exc:
            print(f"director_loop: FAILED: {exc}", file=sys.stderr)
            return 1
        print(render_founder_report(round_result))
        print(f"\nFinal Founder Packet saved to: {round_result['final_packet_path']}")
        return 0

    if args.critique_snapshot_id:
        if not args.critique_reviewer_id:
            print("director_loop: --critique-snapshot-id requires --critique-reviewer-id", file=sys.stderr)
            return 1
        try:
            round_result = run_critique_for_existing_round(
                snapshot_id=args.critique_snapshot_id,
                reviewer_id=args.critique_reviewer_id,
                observations_path=args.observations_path,
                snapshots_dir=args.snapshots_dir,
                reviewers_path=args.reviewers_path,
            )
        except DirectorLoopError as exc:
            print(f"director_loop: FAILED: {exc}", file=sys.stderr)
            return 1
        print(render_founder_report(round_result))
        return 0

    try:
        round_result = run_cycle(
            db_path=args.db_path,
            cursor_path=args.cursor_path,
            observations_path=args.observations_path,
            snapshots_dir=args.snapshots_dir,
            reviewers_path=args.reviewers_path,
            max_events=args.max_events,
            max_rows=args.max_rows,
        )
    except DirectorLoopError as exc:
        print(f"director_loop: FAILED: {exc}", file=sys.stderr)
        return 1

    print(render_founder_report(round_result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
