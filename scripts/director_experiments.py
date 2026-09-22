"""Director Level 2B: bounded, isolated, Founder-approved, disposable
experiments — generalized into the same closed-catalog shape as
director_diagnostics.py's Level 2A diagnostics, so
scripts/director_autonomous_loop.py can invoke a Level 2B experiment the
same safe way it invokes a Level 2A diagnostic: pick a registered
experiment_type from a hardcoded catalog, replay-or-select parameters a
human already exercised, run it, record evidence — never invent a new
experiment_type, never invent parameters, never touch production code or
the live database.

The key difference from Level 2A: a Level 2B experiment is stricter than a
Level 2A diagnostic, not just differently scoped. ``ExperimentContext``
reuses DiagnosticContext's exact isolated-DB-creation and
service-function-calling guards (director_diagnostics.
create_guarded_isolated_sqlite_session / resolve_allowed_service_function —
imported, not reimplemented, so a future safety fix to either lands in
exactly one place) but has NO read_live_db and NO read_repo_file at all —
not merely unused, structurally absent. A Level 2B experiment must never
read the live database, even read-only; it only ever operates inside a
fresh, disposable, isolated database it creates itself, exactly like
director_level2b_experiment.py's existing speaker-selection A/B experiment
already does.

Founder-approval state machine (identical shape to Level 2A's, the Director
may never self-promote):

    CANDIDATE_FOR_EXPERIMENT --[approve_experiment()]--> APPROVED_FOR_EXPERIMENT
    APPROVED_FOR_EXPERIMENT --[run_experiment(), automatic]--> EXPERIMENT_COMPLETE

Exactly two legitimate callers of ``approve_experiment``, distinguishable
forever by the ``approved_by`` field it stamps onto the spec — a human
(default, ``approved_by="Founder"``) for a brand-new experiment_type or
anything outside the closed catalog, or (only once separately
Founder-authorized) ``director_autonomous_loop.py``'s ``run_cycle``, tagged
``approved_by="autonomous_director_loop"``, constrained to
``AUTONOMOUS_LEVEL2B_CATALOG`` and to replaying-or-selecting-among
parameters a human already ran to completion — mirrors
director_diagnostics.approve_diagnostic's authorization boundary exactly;
see that module's docstring for the full reasoning.

The real, already-built, already-fixture-tested, already-Founder-reviewed
speaker-selection fair-opportunity A/B experiment
(director_level2b_experiment.py) is registered here as ONE experiment_type
(``"speaker_selection_fair_opportunity_ab"``) — a thin wrapper that calls
its existing, unmodified ``run_all`` / ``compute_falsification`` /
``compute_closure_respecting_summary`` functions. Registering it is a pure
Python declaration with zero execution; it is NOT added to
director_autonomous_loop.AUTONOMOUS_LEVEL2B_CATALOG by this delivery, and
no human-run ExperimentSpec exists for it yet — both are deliberately left
for a separate, later, explicit step (running it once through this new
state machine is itself a "continue investigating the Village" act, out of
scope for this architecture-only change). Until that happens, the
autonomous loop's template-selection would correctly fail closed
(ExperimentSafetyError: no completed, human-run spec exists) if this type
were ever added to the catalog prematurely.
"""

from __future__ import annotations

import enum
import json
import signal
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from director_diagnostics import (
    STANDARD_FORBIDDEN_OPERATIONS,
    DiagnosticSafetyError,
    DiagnosticTimeoutError,
    create_guarded_isolated_sqlite_session,
    resolve_allowed_service_function,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DIRECTOR_DIR = REPO_ROOT / ".director"
DEFAULT_EXPERIMENTS_DIR = DIRECTOR_DIR / "experiments"

#: Reuse director_diagnostics' exception types directly rather than
#: declaring parallel ExperimentSafetyError/ExperimentTimeoutError classes
#: — a caller catching DiagnosticSafetyError already correctly catches both
#: Level 2A and Level 2B safety failures with one except clause.
ExperimentSafetyError = DiagnosticSafetyError
ExperimentTimeoutError = DiagnosticTimeoutError


class ExperimentState(str, enum.Enum):
    CANDIDATE_FOR_EXPERIMENT = "CANDIDATE_FOR_EXPERIMENT"
    APPROVED_FOR_EXPERIMENT = "APPROVED_FOR_EXPERIMENT"
    EXPERIMENT_COMPLETE = "EXPERIMENT_COMPLETE"


class ExperimentSpec(BaseModel):
    experiment_id: str
    experiment_type: str
    originating_round_id: str
    originating_snapshot_id: str
    originating_recommendation: str
    evidence_refs: list[str] = Field(default_factory=list)
    #: Only "capabilities" (e.g. "create_isolated_test_db") and
    #: "call_service_functions" are meaningful here — there is no
    #: read_live_db_tables/read_repo_files equivalent because
    #: ExperimentContext has no such methods at all.
    allowed_operations: dict[str, list[str]]
    forbidden_operations: list[str] = Field(default_factory=lambda: list(STANDARD_FORBIDDEN_OPERATIONS))
    scope: dict[str, Any] = Field(default_factory=dict)
    success_criteria: str
    failure_criteria: str
    timeout_seconds: int
    output_evidence_dir: str  # relative to .director/experiments/
    state: ExperimentState = ExperimentState.CANDIDATE_FOR_EXPERIMENT
    created_at: str
    approved_at: str | None = None
    approved_by: str | None = None
    completed_at: str | None = None
    run_status: str | None = None  # "SUCCESS" | "FAILED"
    run_error: str | None = None


class ExperimentContext:
    """The entire capability surface a Level 2B experiment implementation
    gets — deliberately narrower than DiagnosticContext: no read_live_db,
    no read_repo_file, structurally absent rather than merely unused. An
    experiment operates only inside isolated database(s) it creates
    itself, exactly like director_level2b_experiment.py's existing
    speaker-selection A/B experiment already does."""

    def __init__(self, spec: ExperimentSpec, *, experiments_dir: Path) -> None:
        self._spec = spec
        self._evidence_dir = (experiments_dir / spec.experiment_id).resolve()
        self._allowed_capabilities = set(spec.allowed_operations.get("capabilities", []))
        self._allowed_service_functions = set(spec.allowed_operations.get("call_service_functions", []))
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        self._isolated_dirs: list[Path] = []
        self._isolated_sessions: list[Any] = []

    def write_evidence(self, filename: str, content: str) -> Path:
        path = (self._evidence_dir / filename).resolve()
        if self._evidence_dir not in path.parents and path != self._evidence_dir:
            raise DiagnosticSafetyError(f"write_evidence refuses path outside {self._evidence_dir}: {filename!r}")
        path.write_text(content)
        return path

    def create_isolated_test_db(self) -> Any:
        """Same guard as DiagnosticContext.create_isolated_test_db, reused
        verbatim via director_diagnostics.create_guarded_isolated_sqlite_session
        — not reimplemented. Requires "create_isolated_test_db" declared in
        this experiment's allowed_operations.capabilities."""
        if "create_isolated_test_db" not in self._allowed_capabilities:
            raise DiagnosticSafetyError(
                "create_isolated_test_db refused: not declared in this experiment's "
                "allowed_operations.capabilities."
            )
        tmp_dir, session = create_guarded_isolated_sqlite_session(prefix="director_experiment_isolated_")
        self._isolated_dirs.append(tmp_dir)
        self._isolated_sessions.append(session)
        return session

    def call_service_function(self, module_path: str, function_name: str, *args: Any, **kwargs: Any) -> Any:
        """Same two-layer check as DiagnosticContext.call_service_function
        — the global ceiling (director_diagnostics.ALLOWED_SERVICE_FUNCTIONS,
        checked via resolve_allowed_service_function) and this experiment's
        own declared subset, both required."""
        declared = f"{module_path}.{function_name}"
        if declared not in self._allowed_service_functions:
            raise DiagnosticSafetyError(
                f"call_service_function refuses {declared} — not declared in this experiment's "
                f"allowed_operations.call_service_functions ({sorted(self._allowed_service_functions)})."
            )
        fn = resolve_allowed_service_function(module_path, function_name)
        return fn(*args, **kwargs)

    def cleanup(self) -> None:
        from app.core.db_safety import safe_rmtree

        for session in self._isolated_sessions:
            try:
                session.close()
            except Exception:  # noqa: BLE001 — cleanup must never mask the real outcome
                pass
        for tmp_dir in self._isolated_dirs:
            try:
                safe_rmtree(tmp_dir)
            except Exception:  # noqa: BLE001
                pass


ExperimentImplementation = Callable[[ExperimentContext, dict[str, Any]], dict[str, Any]]
_EXPERIMENT_IMPLEMENTATIONS: dict[str, ExperimentImplementation] = {}


def register_experiment(experiment_type: str) -> Callable[[ExperimentImplementation], ExperimentImplementation]:
    def decorator(fn: ExperimentImplementation) -> ExperimentImplementation:
        _EXPERIMENT_IMPLEMENTATIONS[experiment_type] = fn
        return fn
    return decorator


@register_experiment("speaker_selection_fair_opportunity_ab")
def speaker_selection_fair_opportunity_ab(ctx: ExperimentContext, scope: dict[str, Any]) -> dict[str, Any]:
    """Thin wrapper around director_level2b_experiment.py's existing,
    unmodified, already-Founder-reviewed speaker-selection fair-opportunity
    A/B experiment — calls its real run_all/compute_falsification/
    compute_closure_respecting_summary functions exactly as
    director_level2b_experiment.main() does, and returns the same evidence
    shape. `ctx` is unused: run_all() already manages its own isolated
    DB(s) internally (via director_diagnostics.DiagnosticContext, the same
    guarded machinery ExperimentContext itself is built on) — this
    implementation exists to make the *type* catalog-addressable, not to
    grant it a new capability surface. `scope` may optionally supply
    `participant_ids` (a list[str]); anything else is ignored."""
    import director_level2b_experiment as l2b

    participant_ids = scope.get("participant_ids")
    run1 = l2b.run_all(participant_ids)
    run2 = l2b.run_all(participant_ids)
    deterministic = json.dumps(run1, sort_keys=True, default=str) == json.dumps(run2, sort_keys=True, default=str)
    falsification = l2b.compute_falsification(run1)
    falsification["deterministic_where_baseline_is_deterministic"]["result"] = deterministic
    falsification["overall_candidate_b_passes_falsification"] = all(
        falsification[k]["result"] is True for k in l2b.REQUIRED_PASSING_CHECKS
    )
    return {
        "experiment": "Level 2B speaker/floor-selection fairness A/B — disposable, isolated, fixture-only",
        "participant_ids": participant_ids or [f"agent_{i+1}" for i in range(8)],
        "results": run1,
        "determinism_check": {"run1_equals_run2": deterministic},
        "falsification": falsification,
        "closure_respecting_summary": l2b.compute_closure_respecting_summary(run1),
    }


def create_candidate_experiment(
    *,
    experiment_type: str,
    originating_round_id: str,
    originating_snapshot_id: str,
    originating_recommendation: str,
    evidence_refs: list[str],
    allowed_operations: dict[str, list[str]],
    scope: dict[str, Any],
    success_criteria: str,
    failure_criteria: str,
    timeout_seconds: int,
    forbidden_operations: list[str] | None = None,
    experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR,
) -> ExperimentSpec:
    """Create a new experiment in CANDIDATE_FOR_EXPERIMENT state. Never
    transitions further — see approve_experiment."""
    experiment_id = f"exp_{uuid.uuid4().hex[:16]}"
    forbidden = list(STANDARD_FORBIDDEN_OPERATIONS)
    if forbidden_operations:
        forbidden += [f for f in forbidden_operations if f not in forbidden]
    spec = ExperimentSpec(
        experiment_id=experiment_id,
        experiment_type=experiment_type,
        originating_round_id=originating_round_id,
        originating_snapshot_id=originating_snapshot_id,
        originating_recommendation=originating_recommendation,
        evidence_refs=evidence_refs,
        allowed_operations=allowed_operations,
        forbidden_operations=forbidden,
        scope=scope,
        success_criteria=success_criteria,
        failure_criteria=failure_criteria,
        timeout_seconds=timeout_seconds,
        output_evidence_dir=experiment_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_spec(spec, experiments_dir)
    return spec


def spec_path(experiment_id: str, experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR) -> Path:
    return experiments_dir / experiment_id / "spec.json"


def save_spec(spec: ExperimentSpec, experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR) -> Path:
    path = spec_path(spec.experiment_id, experiments_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.model_dump_json(indent=2) + "\n")
    return path


def load_spec(experiment_id: str, experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR) -> ExperimentSpec:
    path = spec_path(experiment_id, experiments_dir)
    if not path.exists():
        raise DiagnosticSafetyError(f"no experiment spec at {path}.")
    return ExperimentSpec.model_validate_json(path.read_text())


def approve_experiment(
    experiment_id: str, *, approved_by: str = "Founder", experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR,
) -> ExperimentSpec:
    """THE ONLY function that moves a spec from CANDIDATE_FOR_EXPERIMENT to
    APPROVED_FOR_EXPERIMENT. See this module's docstring for the two
    legitimate callers. This function itself does not — and structurally
    cannot — verify which situation it's being called from; the
    authorization boundary lives entirely in the caller, exactly mirroring
    director_diagnostics.approve_diagnostic."""
    spec = load_spec(experiment_id, experiments_dir)
    if spec.state is not ExperimentState.CANDIDATE_FOR_EXPERIMENT:
        raise DiagnosticSafetyError(
            f"experiment {experiment_id!r} is in state {spec.state.value}, not "
            f"{ExperimentState.CANDIDATE_FOR_EXPERIMENT.value} — refusing to approve."
        )
    spec.state = ExperimentState.APPROVED_FOR_EXPERIMENT
    spec.approved_at = datetime.now(timezone.utc).isoformat()
    spec.approved_by = approved_by
    save_spec(spec, experiments_dir)
    return spec


class _Alarm:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds

    def __enter__(self) -> None:
        def _handler(signum: int, frame: Any) -> None:
            raise DiagnosticTimeoutError(f"experiment exceeded its {self.seconds}s timeout.")
        self._previous = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(self.seconds)

    def __exit__(self, *exc: Any) -> None:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, self._previous)


def run_experiment(
    experiment_id: str, *, experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR,
) -> ExperimentSpec:
    """Execute one APPROVED_FOR_EXPERIMENT experiment. Fails closed at
    every stage exactly like director_diagnostics.run_diagnostic — wrong
    state, unknown experiment_type, any operation outside the declared
    allowlist, or a timeout — none of these ever leave the spec in
    EXPERIMENT_COMPLETE with run_status other than "SUCCESS". Unlike
    run_diagnostic, there is no live-DB health check here at all — a Level
    2B experiment never touches the live database, so there is nothing to
    check."""
    spec = load_spec(experiment_id, experiments_dir)
    if spec.state is not ExperimentState.APPROVED_FOR_EXPERIMENT:
        raise DiagnosticSafetyError(
            f"experiment {experiment_id!r} is in state {spec.state.value}, not "
            f"{ExperimentState.APPROVED_FOR_EXPERIMENT.value} — refusing to run."
        )
    impl = _EXPERIMENT_IMPLEMENTATIONS.get(spec.experiment_type)
    if impl is None:
        raise DiagnosticSafetyError(f"unknown experiment_type {spec.experiment_type!r}.")

    ctx = ExperimentContext(spec, experiments_dir=experiments_dir)
    try:
        try:
            with _Alarm(spec.timeout_seconds):
                evidence = impl(ctx, spec.scope)
        except (DiagnosticSafetyError, DiagnosticTimeoutError) as exc:
            spec.run_status = "FAILED"
            spec.run_error = str(exc)
            save_spec(spec, experiments_dir)
            raise
        except Exception as exc:  # noqa: BLE001 — any implementation error fails the experiment, never propagates as success
            spec.run_status = "FAILED"
            spec.run_error = f"{type(exc).__name__}: {exc}"
            save_spec(spec, experiments_dir)
            raise DiagnosticSafetyError(spec.run_error) from exc
    finally:
        ctx.cleanup()

    ctx.write_evidence("evidence.json", json.dumps(evidence, indent=2, default=str))
    spec.state = ExperimentState.EXPERIMENT_COMPLETE
    spec.run_status = "SUCCESS"
    spec.completed_at = datetime.now(timezone.utc).isoformat()
    save_spec(spec, experiments_dir)
    return spec


def load_evidence(experiment_id: str, experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR) -> dict[str, Any]:
    path = experiments_dir / experiment_id / "evidence.json"
    if not path.exists():
        raise DiagnosticSafetyError(f"no evidence file at {path} — experiment hasn't completed.")
    return json.loads(path.read_text())
