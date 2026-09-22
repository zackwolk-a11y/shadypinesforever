"""Fixture proofs for scripts/director_autonomous_loop.py.

DESIGN + FIXTURE-TEST ONLY, per explicit Founder instruction. Nothing in
this script:
  - touches the real live Village database (a fresh, isolated, on-disk
    SQLite fixture DB is built once via Base.metadata.create_all and reused
    read-only across every scenario)
  - makes a paid/network model call (every real provider class —
    Anthropic, OpenRouter, OpenAI, Hermes CLI — is monkeypatched to RAISE
    if merely instantiated, for the whole run; only "fixture" and a local
    ScriptedFixtureProvider, both zero-network, are ever used)
  - touches director_diagnostics.py's real 5-diagnostic-type catalog
    content or the actual speaker-selection investigation — every scenario
    here registers and uses its own disposable, clearly-namespaced
    "_fixture_test_probe_*" diagnostic type instead, and passes an
    explicit diagnostic_catalog override into run_autonomous_investigation
    rather than relying on the module's real AUTONOMOUS_DIAGNOSTIC_CATALOG
    default
  - flips AUTONOMOUS_EXECUTION_ENABLED on disk; every scenario that needs
    it True monkeypatches the module attribute for the duration of that
    one scenario and restores it in a finally block

Run: .venv/bin/python scripts/director_autonomous_loop_fixturetest.py
Exits 0 iff every scenario passes; prints a PASS/FAIL line per scenario.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_autonomous_loop as dal  # noqa: E402
import director_bridge as db_bridge  # noqa: E402
import director_diagnostics as dd  # noqa: E402
import director_loop as dloop  # noqa: E402
import director_providers as dp  # noqa: E402
from director_diagnostics import DiagnosticSafetyError  # noqa: E402
from director_providers import FixtureModelProvider, TransientModelProviderError  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []

# ---------------------------------------------------------------------------
# CRITICAL isolation fix: director_loop.py's chain functions
# (run_diagnostic_review_chain, run_synthesis_for_existing_round) call
# director_bridge.rebuild_rounds_history(observations_path=..., packets_dir=...)
# WITHOUT overriding history_path — so even with fully isolated
# observations/snapshots/packets dirs, that call would still derive and
# overwrite the REAL .director/history/rounds.jsonl with fixture-test round
# ids. Redirect it, for this test process only, to a disposable fixture
# path. Never touches scripts/director_loop.py itself.
# ---------------------------------------------------------------------------
_REAL_ROUNDS_HISTORY_PATH = db_bridge.ROUNDS_HISTORY_PATH
_FIXTURE_HISTORY_DIR = Path(tempfile.mkdtemp(prefix="director_autonomous_fixturetest_history_"))
_FIXTURE_HISTORY_PATH = _FIXTURE_HISTORY_DIR / "rounds.jsonl"


def _redirected_rebuild_rounds_history(*, observations_path: Path, packets_dir: Path, history_path: Path | None = None) -> Any:
    del history_path
    return db_bridge.rebuild_rounds_history(
        observations_path=observations_path, packets_dir=packets_dir, history_path=_FIXTURE_HISTORY_PATH,
    )


dloop.rebuild_rounds_history = _redirected_rebuild_rounds_history


def record(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"{'PASS' if passed else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not passed else ""))


@contextmanager
def expect(exc_type: type[BaseException]):
    try:
        yield
    except exc_type:
        return
    else:
        raise AssertionError(f"expected {exc_type.__name__} to be raised, but nothing was raised")


# ---------------------------------------------------------------------------
# No-paid-call guarantee: every real network/paid provider class is replaced
# with a stand-in that raises the instant it's constructed, for the whole
# run. If any code path anywhere in this script ever reached a real
# provider, every single scenario below would fail loudly instead of
# silently succeeding on a real call.
# ---------------------------------------------------------------------------

class _MustNotBeCalled:
    def __init__(self, *a: Any, **k: Any) -> None:
        raise AssertionError(
            f"{self.__class__.__name__} was instantiated — a real/paid provider must NEVER be "
            "reachable from a fixture test. This is a test-harness bug, not an expected code path."
        )


for _name in ("anthropic", "openrouter", "openai", "hermes_cli"):
    dp._PROVIDERS[_name] = type(f"MustNotBeCalled_{_name}", (_MustNotBeCalled,), {"name": _name, "is_fixture": False})


class ScriptedFixtureProvider:
    """Same zero-network guarantee as FixtureModelProvider, but returns
    caller-queued field overrides in call order (one dict per
    complete_structured call) instead of always the same generic
    placeholder — lets a test script control exactly what PRIMARY/CRITIQUE/
    SYNTHESIS "say" without ever calling a real model."""

    name = "scripted_fixture_test_only"
    is_fixture = True
    queue: deque[dict[str, Any]] = deque()

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        del model, api_key

    def complete_structured(self, spec: Any) -> dict[str, Any]:
        base = {
            field_name: FixtureModelProvider._placeholder(field_name, prop)
            for field_name, prop in spec.schema.get("properties", {}).items()
        }
        if ScriptedFixtureProvider.queue:
            item = ScriptedFixtureProvider.queue.popleft()
            if isinstance(item, BaseException):
                raise item
            base.update(item)
        return base


dp._PROVIDERS["scripted_fixture_test_only"] = ScriptedFixtureProvider


class ScriptedPaidLookingProvider(ScriptedFixtureProvider):
    """Identical to ScriptedFixtureProvider (same zero-network queue
    mechanism) except is_fixture=False and a class-level call counter —
    used only by the model-call-budget scenario, which needs a provider
    _enforce_call_budget actually counts (real providers are is_fixture=
    False; ScriptedFixtureProvider is deliberately is_fixture=True and so
    is invisible to the budget guard by design)."""

    name = "scripted_paid_test_only"
    is_fixture = False
    queue: deque[dict[str, Any]] = deque()
    call_count = 0

    def complete_structured(self, spec: Any) -> dict[str, Any]:
        ScriptedPaidLookingProvider.call_count += 1
        base = {
            field_name: FixtureModelProvider._placeholder(field_name, prop)
            for field_name, prop in spec.schema.get("properties", {}).items()
        }
        if ScriptedPaidLookingProvider.queue:
            item = ScriptedPaidLookingProvider.queue.popleft()
            if isinstance(item, BaseException):
                raise item
            base.update(item)
        return base


dp._PROVIDERS["scripted_paid_test_only"] = ScriptedPaidLookingProvider


def queue_cycle(*, primary: dict[str, Any], critique: dict[str, Any], synthesis: dict[str, Any]) -> None:
    ScriptedFixtureProvider.queue.append(primary)
    ScriptedFixtureProvider.queue.append(critique)
    ScriptedFixtureProvider.queue.append(synthesis)


# ---------------------------------------------------------------------------
# Isolated fixture environment: one throwaway directory tree per test run,
# a schema-complete but content-empty SQLite DB (Base.metadata.create_all —
# never the live DB), and a temp reviewers.json pointing every role at a
# zero-network provider.
# ---------------------------------------------------------------------------

def build_env() -> dict[str, Path]:
    root = Path(tempfile.mkdtemp(prefix="director_autonomous_fixturetest_"))
    (root / "diagnostics").mkdir()
    (root / "experiments").mkdir()
    (root / "autonomous").mkdir()
    (root / "snapshots").mkdir()
    (root / "packets").mkdir()

    from sqlalchemy import create_engine
    import app.db.models  # noqa: F401
    from app.db.base import Base

    db_path = root / "fixture.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    assert db_path.stat().st_size >= 8192, "fixture DB too small to pass check_live_db's minimum-size gate"

    observations_path = root / "observations.jsonl"
    observations_path.write_text("")

    return {
        "root": root, "db_path": db_path, "diagnostics_dir": root / "diagnostics",
        "experiments_dir": root / "experiments",
        "autonomous_dir": root / "autonomous", "snapshots_dir": root / "snapshots",
        "packets_dir": root / "packets", "observations_path": observations_path,
    }


def write_reviewers_json(root: Path, provider: str) -> Path:
    path = root / "reviewers.json"
    path.write_text(json.dumps([
        {"reviewer_id": "director-primary", "role": "PRIMARY", "provider": provider, "enabled": True},
        {"reviewer_id": "hermes", "role": "CRITIQUE", "provider": provider, "enabled": True},
        {"reviewer_id": "openai-synthesis", "role": "SYNTHESIS", "provider": provider, "enabled": True},
    ], indent=2))
    return path


def seed_originating_round(env: dict[str, Path], round_id: str, snapshot_id: str) -> None:
    """Mimics an already-completed Level 1 PRIMARY round — the thing every
    Level 2A/2B round in the real pipeline is built on top of. Purely
    synthetic content, unrelated to any real Village investigation."""
    (env["snapshots_dir"] / f"{snapshot_id}.json").write_text(json.dumps({
        "snapshot_id": snapshot_id, "director_snapshot_version": 1,
        "note": "synthetic seed snapshot for autonomous-loop fixture testing — not real Village state",
    }))
    record_line = {
        "round_id": round_id, "observation_id": "obs_seed", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_id": "director-primary", "reviewer_role": "PRIMARY", "provider": "fixture", "model": None,
        "snapshot_id": snapshot_id, "snapshot_version": 1,
        "output": {
            "findings": ["synthetic seed finding"], "evidence": ["synthetic seed evidence"],
            "interpretation": "synthetic seed round for fixture testing", "recommendation": "n/a",
            "recommendation_type": "FURTHER_OBSERVATION", "confidence": 0.5, "status": "OBSERVATION_ONLY",
        },
    }
    with env["observations_path"].open("a") as f:
        f.write(json.dumps(record_line) + "\n")


# ---------------------------------------------------------------------------
# A disposable diagnostic implementation, unrelated to the real Village
# investigation — pure function of scope, no DB access at all needed for
# these orchestration proofs (DiagnosticContext boundary enforcement is
# already separately proven by director_diagnostics.py itself; this proves
# the autonomous loop's cycle/stopping-rule/catalog machinery instead).
# ---------------------------------------------------------------------------

@dd.register_diagnostic("_fixture_test_probe")
def _fixture_test_probe(ctx: Any, scope: dict[str, Any]) -> dict[str, Any]:
    return {"probe_marker": scope.get("marker", "default"), "note": "disposable fixture-test-only diagnostic"}


def seed_human_run_template(env: dict[str, Path], diagnostic_type: str, round_id: str, snapshot_id: str) -> str:
    """Establishes the 'a human already ran this once' precondition
    _select_diagnostic_template requires before the autonomous loop may ever
    clone this diagnostic_type's parameters."""
    spec = dd.create_candidate_diagnostic(
        diagnostic_type=diagnostic_type, originating_round_id=round_id, originating_snapshot_id=snapshot_id,
        originating_recommendation="fixture-test seed: human-run template", evidence_refs=[],
        allowed_operations={"read_live_db_tables": [], "read_repo_files": [], "capabilities": []},
        scope={"marker": "seed"}, success_criteria="always succeeds", failure_criteria="never",
        timeout_seconds=5, diagnostics_dir=env["diagnostics_dir"],
    )
    dd.approve_diagnostic(spec.diagnostic_id, approved_by="Founder", diagnostics_dir=env["diagnostics_dir"])
    dd.run_diagnostic(spec.diagnostic_id, db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"])
    return spec.diagnostic_id


def run_investigation(
    env: dict[str, Path], reviewers_path: Path, round_id: str, *, max_cycles: int,
    catalog: frozenset[str] = frozenset(), level2b_catalog: frozenset[str] = frozenset(),
    max_paid_calls: int = dal.HARD_MAX_PAID_CALLS_CEILING,
) -> dict[str, Any]:
    return dal.run_autonomous_investigation(
        originating_round_id=round_id, max_cycles=max_cycles, max_paid_calls=max_paid_calls,
        db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"], experiments_dir=env["experiments_dir"],
        observations_path=env["observations_path"], snapshots_dir=env["snapshots_dir"], packets_dir=env["packets_dir"],
        reviewers_path=reviewers_path, autonomous_dir=env["autonomous_dir"],
        diagnostic_catalog=catalog, level2b_catalog=level2b_catalog,
    )


# ---------------------------------------------------------------------------
# A disposable Level 2B experiment implementation, unrelated to the real
# speaker-selection investigation — proves director_experiments.py's
# generalized state machine (create_candidate_experiment -> approve_experiment
# -> run_experiment) and the autonomous loop's Level 2B branch wire up
# correctly, without touching director_level2b_experiment.py at all.
# ---------------------------------------------------------------------------

import director_experiments as dexp  # noqa: E402


@dexp.register_experiment("_fixture_test_experiment")
def _fixture_test_experiment(ctx: Any, scope: dict[str, Any]) -> dict[str, Any]:
    return {"experiment_marker": scope.get("marker", "default"), "note": "disposable fixture-test-only experiment"}


def seed_human_run_experiment_template(env: dict[str, Path], experiment_type: str, round_id: str, snapshot_id: str) -> str:
    """Level 2B analog of seed_human_run_template — establishes the 'a
    human already ran this once' precondition _select_experiment_template
    requires."""
    spec = dexp.create_candidate_experiment(
        experiment_type=experiment_type, originating_round_id=round_id, originating_snapshot_id=snapshot_id,
        originating_recommendation="fixture-test seed: human-run experiment template", evidence_refs=[],
        allowed_operations={"capabilities": []},
        scope={"marker": "seed"}, success_criteria="always succeeds", failure_criteria="never",
        timeout_seconds=5, experiments_dir=env["experiments_dir"],
    )
    dexp.approve_experiment(spec.experiment_id, approved_by="Founder", experiments_dir=env["experiments_dir"])
    dexp.run_experiment(spec.experiment_id, experiments_dir=env["experiments_dir"])
    return spec.experiment_id


PRIMARY_FINDINGS_A = {"findings": ["fixture finding A"], "evidence": ["fixture evidence A"]}
PRIMARY_FINDINGS_B = {"findings": ["fixture finding B"], "evidence": ["fixture evidence B"]}
BENIGN_CRITIQUE = {"disagreements_with_primary": [], "alternative_explanations": []}
BENIGN_SYNTHESIS_BASE = {"disagreement_handling": [], "unresolved_uncertainty": []}


# ---------------------------------------------------------------------------
# Scenario 1: shipped default is inert
# ---------------------------------------------------------------------------

def scenario_shipped_default_is_inert() -> None:
    env = build_env()
    assert dal.AUTONOMOUS_EXECUTION_ENABLED is False, "test must start from the real shipped (disabled) state"
    before = list(env["autonomous_dir"].iterdir())
    with expect(dal.AutonomousExecutionNotAuthorizedError):
        run_investigation(env, write_reviewers_json(env["root"], "fixture"), "round_seed", max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    after = list(env["autonomous_dir"].iterdir())
    assert before == after == [], f"run_autonomous_investigation must create nothing before the gate check; saw {after}"
    # run_cycle direct call must refuse too, even with a hand-built IssueState.
    state = dal.IssueState(issue_id="issue_should_not_run", originating_round_id="round_seed", created_at="2026-01-01T00:00:00+00:00")
    with expect(dal.AutonomousExecutionNotAuthorizedError):
        dal.run_cycle(state, db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"],
                      observations_path=env["observations_path"], snapshots_dir=env["snapshots_dir"],
                      packets_dir=env["packets_dir"], autonomous_dir=env["autonomous_dir"])
    shutil.rmtree(env["root"])
    record("shipped default (AUTONOMOUS_EXECUTION_ENABLED=False) is inert", True)


# ---------------------------------------------------------------------------
# Scenario 2: catalog template replay + fail-closed on never-run type
# ---------------------------------------------------------------------------

def scenario_template_replay_and_fail_closed() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_2", "snap_seed_2"
    seed_originating_round(env, round_id, snapshot_id)
    diag_id = seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)

    template = dal._select_diagnostic_template("_fixture_test_probe", env["diagnostics_dir"])
    assert template.diagnostic_id == diag_id, "must replay the exact human-run spec, not invent a new one"
    assert template.scope == {"marker": "seed"}, "must clone scope byte-for-byte"

    with expect(DiagnosticSafetyError):
        dal._select_diagnostic_template("_fixture_test_probe_never_run_by_a_human", env["diagnostics_dir"])
    shutil.rmtree(env["root"])
    record("catalog template is replayed from a human-run spec; unknown/never-run type fails closed", True)


# ---------------------------------------------------------------------------
# Scenario 3: Option B — recommendation_type NO_ACTION stops immediately
# ---------------------------------------------------------------------------

def scenario_option_b_no_change() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_3", "snap_seed_3"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY", "confidence": 0.8},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.8},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY",
                   "strategic_recommendation": "No change is justified by the evidence.", "confidence": 0.8},
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 1, packet
    assert packet["stop_decision"] == "STOP_NO_CHANGE_JUSTIFIED", packet
    assert packet["option"] == "B_NO_CHANGE_RECOMMENDATION", packet
    shutil.rmtree(env["root"])
    record("NO_ACTION stops after exactly 1 cycle with Founder Packet Option B", True)


# ---------------------------------------------------------------------------
# Scenario 4: Option A — recommendation_type CODE_CHANGE stops immediately
# ---------------------------------------------------------------------------

def scenario_option_a_code_change() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_4", "snap_seed_4"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "CODE_CHANGE", "status": "CANDIDATE_FOR_TESTING", "confidence": 0.9},
        critique={**BENIGN_CRITIQUE, "status": "CANDIDATE_FOR_TESTING", "confidence": 0.85},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "CODE_CHANGE", "status": "CANDIDATE_FOR_TESTING",
                   "strategic_recommendation": "Evidence supports a bounded production change.", "confidence": 0.88},
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 1, packet
    assert packet["stop_decision"] == "STOP_SUFFICIENT_FOR_RECOMMENDATION", packet
    assert packet["option"] == "A_PRODUCTION_CHANGE_RECOMMENDATION", packet
    # Even here — the "recommend a change" path — status is CANDIDATE_FOR_TESTING, never
    # APPROVED_TO_TEST, and the loop performed no implementation of any kind.
    final = json.loads(Path(packet["cycle_results"][0]["final_packet_path"]).read_text())
    assert final["recommendation_status"] == "CANDIDATE_FOR_TESTING", final
    shutil.rmtree(env["root"])
    record("CODE_CHANGE stops after exactly 1 cycle with Founder Packet Option A, status never exceeds CANDIDATE_FOR_TESTING", True)


# ---------------------------------------------------------------------------
# Scenario 5: attempted permission expansion forces escalation, overriding
# an otherwise-continuable recommendation_type
# ---------------------------------------------------------------------------

def scenario_permission_expansion_escalation() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_5", "snap_seed_5"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.7},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.7},
        synthesis={
            **BENIGN_SYNTHESIS_BASE, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
            "strategic_recommendation": "We should just modify production directly and bypass the safety boundary "
                                         "to run the village once more without founder review.",
            "confidence": 0.7,
        },
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 1, packet
    assert packet["stop_decision"] == "STOP_SAFETY_ESCALATION", packet
    assert packet["option"] == "C_FOUNDER_ESCALATION", packet
    flags = packet["cycle_results"][0]["permission_expansion_flags"]
    assert flags, "expected at least one permission-expansion pattern to be flagged"
    assert "modify (the )?production" in flags[0] or any("production" in f for f in flags), flags
    shutil.rmtree(env["root"])
    record("permission-expansion phrasing in reviewer prose forces escalation, overriding a continuable recommendation_type", True)


def scenario_permission_expansion_negation_awareness() -> None:
    """Post-stress-test fix (Founder Packet 2026-09-04, self-test finding):
    the 2026-09-03 run escalated on a SYNTHESIS reviewer's own explicit
    prohibition ("...do not alter prompts or code and do not run the
    Village") because the bare pattern matched inside it. Adversarial cases
    in both directions, tested directly against check_permission_expansion
    (a pure function) rather than through the full scripted-provider
    harness — no autonomous cycle needs to run to exercise this."""
    negated_cases = [
        "Stop at diagnosis—do not alter prompts or code and do not run the Village.",
        "This finding supports no production changes at this time.",
        "We should never expand the loop's permission scope based on this evidence.",
        "The reviewer should not merge anything into production from this round.",
        "Founder approval is required; do not skip founder review under any circumstance.",
        "This does not require any database restore or migration.",
        "The recommendation explicitly avoids any plan to bypass the safety guard.",
    ]
    for text in negated_cases:
        hits = dal.check_permission_expansion(text)
        assert hits == [], f"expected NO hits for legitimate prohibition: {text!r}, got {hits}"

    positive_cases = [
        "The next step should be to run the Village for another five days to gather more data.",
        "The loop should expand its own permission to write to the live database.",
        "Just bypass the safety guard and proceed.",
        "We recommend the team modify production directly.",
        "Someone should raise the cycle limit so the loop can keep going.",
    ]
    for text in positive_cases:
        hits = dal.check_permission_expansion(text)
        assert hits, f"expected a hit for genuine risky statement: {text!r}"

    # A negation earlier in the text must not blind the detector to a real,
    # separate, unnegated risky statement later in the same field.
    mixed = (
        "We will not skip founder review for this recommendation. Separately, the loop "
        "should also expand its own permission to reach new data sources."
    )
    mixed_hits = dal.check_permission_expansion(mixed)
    assert mixed_hits, "a real risky statement elsewhere in the text must still be caught"
    # Exactly one hit: the unnegated "expand its own permission" clause. The
    # negated "skip founder" clause must not ALSO produce its own hit (the
    # "in: ..." field of a legitimate hit necessarily echoes the surrounding
    # text for readability, so we check which PATTERN fired, not whether the
    # word "founder" appears anywhere in the message).
    assert len(mixed_hits) == 1, f"expected exactly one hit (the unnegated clause), got: {mixed_hits}"
    assert "expand" in mixed_hits[0].split(" in: ")[0], mixed_hits
    assert "skip founder" not in mixed_hits[0].split(" in: ")[0], mixed_hits

    record(
        "permission-expansion negation-awareness: legitimate prohibitions do not escalate, "
        "genuine risky language (including alongside an unrelated prohibition) still does",
        True,
    )


# ---------------------------------------------------------------------------
# Scenario 6: 2 consecutive cycles with no materially new evidence stop
# the loop before max_cycles or catalog exhaustion would have
# ---------------------------------------------------------------------------

def scenario_no_new_evidence_streak() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_6", "snap_seed_6"
    seed_originating_round(env, round_id, snapshot_id)
    catalog = frozenset({"_fixture_test_probe_x", "_fixture_test_probe_y", "_fixture_test_probe_z"})
    for t in catalog:
        dd.register_diagnostic(t)(lambda ctx, scope: {"note": "disposable"})
        seed_human_run_template(env, t, round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    # Cycle 1: findings A (new, streak resets to 0). Cycle 2: findings A again
    # (identical to cycle 1 -> streak=1, still CONTINUE). Cycle 3: findings A
    # again (identical to cycle 2 -> streak=2 -> STOP_NO_NEW_EVIDENCE).
    for _ in range(3):
        queue_cycle(
            primary={**PRIMARY_FINDINGS_A, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6},
            critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6},
            synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
                       "strategic_recommendation": "Investigate further.", "confidence": 0.6},
        )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=catalog)
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 3, packet
    assert packet["stop_decision"] == "STOP_NO_NEW_EVIDENCE", packet
    assert packet["option"] == "C_FOUNDER_ESCALATION", packet
    shutil.rmtree(env["root"])
    record("2 consecutive cycles with identical evidence stop the loop at cycle 3 (before max_cycles=5 or catalog exhaustion)", True)


# ---------------------------------------------------------------------------
# Scenario 7: max_cycles is enforced even when evidence keeps changing and
# catalog entries remain — both as a pure evaluate_stopping_rules unit
# check and as a real 5-cycle end-to-end run
# ---------------------------------------------------------------------------

def scenario_max_cycles() -> None:
    # Pure unit check: cycles_run already at the ceiling, catalog still has
    # untried entries, evidence still fresh — max_cycles must win anyway.
    state = dal.IssueState(
        issue_id="issue_unit", originating_round_id="round_x", created_at="2026-01-01T00:00:00+00:00",
        cycles_run=5, max_cycles=5, no_new_evidence_streak=0,
    )
    decision = dal.evaluate_stopping_rules(
        state, recommendation_type="DIAGNOSTIC_INVESTIGATION", permission_expansion_flags=[],
        diagnostic_catalog=frozenset({"a", "b", "c", "d", "e", "f"}), level2b_catalog=frozenset(),
    )
    assert decision == dal.StoppingDecision.STOP_MAX_CYCLES, decision

    # Real end-to-end: 6-entry catalog, fresh evidence and DIAGNOSTIC_INVESTIGATION
    # every single cycle (nothing else would ever stop it) — must still halt
    # at exactly cycle 5, never cycle 6.
    env = build_env()
    round_id, snapshot_id = "round_seed_7", "snap_seed_7"
    seed_originating_round(env, round_id, snapshot_id)
    catalog = frozenset({f"_fixture_test_probe_mc{i}" for i in range(6)})
    for t in catalog:
        dd.register_diagnostic(t)(lambda ctx, scope: {"note": "disposable"})
        seed_human_run_template(env, t, round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    for i in range(6):  # queue enough for 6 cycles; only 5 should ever actually run
        marker = {**PRIMARY_FINDINGS_A, "findings": [f"fixture finding cycle {i}"], "evidence": [f"fixture evidence cycle {i}"]}
        queue_cycle(
            primary={**marker, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6},
            critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6},
            synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
                       "strategic_recommendation": "Keep investigating.", "confidence": 0.6},
        )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=catalog)
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    ScriptedFixtureProvider.queue.clear()  # discard the unused 6th cycle's queued entries
    assert packet["cycles_run"] == 5, packet
    assert packet["stop_decision"] == "STOP_MAX_CYCLES", packet
    assert packet["option"] == "C_FOUNDER_ESCALATION", packet
    shutil.rmtree(env["root"])
    record("max_cycles=5 halts the loop at exactly cycle 5 even with fresh evidence and catalog entries remaining", True)


# ---------------------------------------------------------------------------
# Scenario 8: catalog exhaustion (all pre-approved diagnostic types tried,
# issue still unresolved) escalates rather than inventing a new action
# ---------------------------------------------------------------------------

def scenario_catalog_exhaustion() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_8", "snap_seed_8"
    seed_originating_round(env, round_id, snapshot_id)
    catalog = frozenset({"_fixture_test_probe_p", "_fixture_test_probe_q"})
    for t in catalog:
        dd.register_diagnostic(t)(lambda ctx, scope: {"note": "disposable"})
        seed_human_run_template(env, t, round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    for i in range(2):
        marker = {**PRIMARY_FINDINGS_A, "findings": [f"fixture finding {i}"], "evidence": [f"fixture evidence {i}"]}
        queue_cycle(
            primary={**marker, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6},
            critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6},
            synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
                       "strategic_recommendation": "Keep investigating.", "confidence": 0.6},
        )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=catalog)
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 2, packet  # NOT 5 — stopped early because the 2-entry catalog ran out
    assert packet["stop_decision"] == "STOP_SAFETY_ESCALATION", packet
    assert packet["option"] == "C_FOUNDER_ESCALATION", packet
    shutil.rmtree(env["root"])
    record("exhausting a small pre-approved catalog (2 entries) escalates at cycle 2, well before max_cycles=5", True)


# ---------------------------------------------------------------------------
# Scenario 9: max_cycles ceiling of 5 cannot be raised by a caller
# ---------------------------------------------------------------------------

def scenario_max_cycles_ceiling_not_overridable() -> None:
    env = build_env()
    with expect(dal.AutonomousLoopSafetyError):
        dal.create_issue(originating_round_id="round_x", max_cycles=6, autonomous_dir=env["autonomous_dir"])
    with expect(dal.AutonomousLoopSafetyError):
        dal.create_issue(originating_round_id="round_x", max_cycles=0, autonomous_dir=env["autonomous_dir"])
    shutil.rmtree(env["root"])
    record("max_cycles cannot be set above 5 (or below 1) even by a direct caller", True)


# ---------------------------------------------------------------------------
# Scenario 10 (item 1): the autonomous loop's Level 2B branch runs a
# catalog-addressable experiment end to end via director_experiments.py —
# never touching director_level2b_experiment.py's real speaker-selection
# mechanism, using its own disposable "_fixture_test_experiment" type.
# ---------------------------------------------------------------------------

def scenario_level2b_experiment_runs_via_catalog() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_10", "snap_seed_10"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_experiment_template(env, "_fixture_test_experiment", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY", "confidence": 0.7},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.7},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY",
                   "strategic_recommendation": "No change justified.", "confidence": 0.7},
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(
            env, reviewers_path, round_id, max_cycles=5,
            level2b_catalog=frozenset({"_fixture_test_experiment"}),
        )
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 1, packet
    assert packet["experiment_ids"], "expected a real experiment_id to have been created and run"
    assert packet["level2b_experiments_tried"] == ["_fixture_test_experiment"], packet
    assert packet["cycle_results"][0]["action"] == "RUN_LEVEL2B_EXPERIMENT:_fixture_test_experiment", packet
    shutil.rmtree(env["root"])
    record("Level 2B branch runs a catalog-addressable experiment end to end via director_experiments.py", True)


def scenario_level2a_tried_before_level2b() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_11", "snap_seed_11"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    seed_human_run_experiment_template(env, "_fixture_test_experiment", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    # Cycle 1 (should consume the sole Level 2A catalog entry): DIAGNOSTIC_INVESTIGATION, new evidence.
    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
                   "strategic_recommendation": "Keep investigating.", "confidence": 0.6},
    )
    # Cycle 2 (Level 2A now exhausted, should fall through to the Level 2B entry): NO_ACTION to stop cleanly.
    queue_cycle(
        primary={**PRIMARY_FINDINGS_B, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY", "confidence": 0.8},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.8},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY",
                   "strategic_recommendation": "No change justified.", "confidence": 0.8},
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(
            env, reviewers_path, round_id, max_cycles=5,
            catalog=frozenset({"_fixture_test_probe"}), level2b_catalog=frozenset({"_fixture_test_experiment"}),
        )
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 2, packet
    assert packet["cycle_results"][0]["action"] == "RUN_DIAGNOSTIC:_fixture_test_probe", packet
    assert packet["cycle_results"][1]["action"] == "RUN_LEVEL2B_EXPERIMENT:_fixture_test_experiment", packet
    shutil.rmtree(env["root"])
    record("Level 2A catalog is exhausted before the loop ever falls through to Level 2B", True)


# ---------------------------------------------------------------------------
# Scenario 12/13 (item 2): evidence-driven bounded template selection —
# among multiple already-human-approved scopes for the same diagnostic_type,
# the loop selects the one overlapping this issue's accumulated evidence
# identifiers, never inventing a new scope; with no overlap it falls back
# to the old always-replay-latest behavior.
# ---------------------------------------------------------------------------

def scenario_evidence_driven_template_selection_prefers_overlap() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_12", "snap_seed_12"
    # Originating round's PRIMARY evidence cites identifier "111" specifically.
    (env["snapshots_dir"] / f"{snapshot_id}.json").write_text(json.dumps({"snapshot_id": snapshot_id, "director_snapshot_version": 1}))
    record_line = {
        "round_id": round_id, "observation_id": "obs_seed", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_id": "director-primary", "reviewer_role": "PRIMARY", "provider": "fixture", "model": None,
        "snapshot_id": snapshot_id, "snapshot_version": 1,
        "output": {
            "findings": ["conversation_id 111 shows the defect"], "evidence": ["event_id 111"],
            "interpretation": "seed", "recommendation": "n/a",
            "recommendation_type": "FURTHER_OBSERVATION", "confidence": 0.5, "status": "OBSERVATION_ONLY",
        },
    }
    with env["observations_path"].open("a") as f:
        f.write(json.dumps(record_line) + "\n")

    # Older template: scope mentions 111 (matches accumulated evidence). Newer template: scope
    # mentions 222 (does not match) — under the OLD always-latest behavior, 222 would always win.
    dd.register_diagnostic("_fixture_test_probe_overlap")(lambda ctx, scope: {"note": "disposable"})
    older = dd.create_candidate_diagnostic(
        diagnostic_type="_fixture_test_probe_overlap", originating_round_id=round_id, originating_snapshot_id=snapshot_id,
        originating_recommendation="seed older", evidence_refs=[], allowed_operations={"capabilities": []},
        scope={"conversation_id": 111}, success_criteria="ok", failure_criteria="never",
        timeout_seconds=5, diagnostics_dir=env["diagnostics_dir"],
    )
    dd.approve_diagnostic(older.diagnostic_id, approved_by="Founder", diagnostics_dir=env["diagnostics_dir"])
    dd.run_diagnostic(older.diagnostic_id, db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"])
    newer = dd.create_candidate_diagnostic(
        diagnostic_type="_fixture_test_probe_overlap", originating_round_id=round_id, originating_snapshot_id=snapshot_id,
        originating_recommendation="seed newer", evidence_refs=[], allowed_operations={"capabilities": []},
        scope={"conversation_id": 222}, success_criteria="ok", failure_criteria="never",
        timeout_seconds=5, diagnostics_dir=env["diagnostics_dir"],
    )
    dd.approve_diagnostic(newer.diagnostic_id, approved_by="Founder", diagnostics_dir=env["diagnostics_dir"])
    dd.run_diagnostic(newer.diagnostic_id, db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"])
    assert (newer.completed_at or newer.created_at) >= (older.completed_at or older.created_at)

    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")
    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY", "confidence": 0.7},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.7},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY",
                   "strategic_recommendation": "done", "confidence": 0.7},
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe_overlap"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    used_diagnostic_id = packet["diagnostic_ids"][0]
    used_spec = dd.load_spec(used_diagnostic_id, env["diagnostics_dir"])
    assert used_spec.scope == {"conversation_id": 111}, (
        f"expected the OLDER, evidence-overlapping template (conversation_id=111) to be selected over "
        f"the newer non-overlapping one; got scope={used_spec.scope}"
    )
    shutil.rmtree(env["root"])
    record("evidence-driven template selection picks the scope overlapping accumulated evidence, not just the most recent", True)


def scenario_template_selection_falls_back_to_latest_with_no_overlap() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_13", "snap_seed_13"
    seed_originating_round(env, round_id, snapshot_id)  # generic seed evidence, no numeric identifiers matching either template

    dd.register_diagnostic("_fixture_test_probe_fallback")(lambda ctx, scope: {"note": "disposable"})
    older = dd.create_candidate_diagnostic(
        diagnostic_type="_fixture_test_probe_fallback", originating_round_id=round_id, originating_snapshot_id=snapshot_id,
        originating_recommendation="seed older", evidence_refs=[], allowed_operations={"capabilities": []},
        scope={"conversation_id": 333}, success_criteria="ok", failure_criteria="never",
        timeout_seconds=5, diagnostics_dir=env["diagnostics_dir"],
    )
    dd.approve_diagnostic(older.diagnostic_id, approved_by="Founder", diagnostics_dir=env["diagnostics_dir"])
    dd.run_diagnostic(older.diagnostic_id, db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"])
    newer = dd.create_candidate_diagnostic(
        diagnostic_type="_fixture_test_probe_fallback", originating_round_id=round_id, originating_snapshot_id=snapshot_id,
        originating_recommendation="seed newer", evidence_refs=[], allowed_operations={"capabilities": []},
        scope={"conversation_id": 444}, success_criteria="ok", failure_criteria="never",
        timeout_seconds=5, diagnostics_dir=env["diagnostics_dir"],
    )
    dd.approve_diagnostic(newer.diagnostic_id, approved_by="Founder", diagnostics_dir=env["diagnostics_dir"])
    dd.run_diagnostic(newer.diagnostic_id, db_path=env["db_path"], diagnostics_dir=env["diagnostics_dir"])

    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")
    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY", "confidence": 0.7},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.7},
        synthesis={**BENIGN_SYNTHESIS_BASE, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY",
                   "strategic_recommendation": "done", "confidence": 0.7},
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe_fallback"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    used_spec = dd.load_spec(packet["diagnostic_ids"][0], env["diagnostics_dir"])
    assert used_spec.scope == {"conversation_id": 444}, (
        f"expected fallback to the most-recent template when no evidence overlap exists; got {used_spec.scope}"
    )
    shutil.rmtree(env["root"])
    record("with no evidence overlap, template selection falls back to the most recent (old default behavior preserved)", True)


# ---------------------------------------------------------------------------
# Scenario 14 (item 3): diminishing-return detection recognizes SYNTHESIS
# disagreement-resolution and confidence movement as materially new content
# even when PRIMARY's raw findings/evidence repeat verbatim.
# ---------------------------------------------------------------------------

def scenario_diminishing_returns_recognizes_synthesis_movement() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_14", "snap_seed_14"
    seed_originating_round(env, round_id, snapshot_id)
    catalog = frozenset({"_fixture_test_probe_m1", "_fixture_test_probe_m2", "_fixture_test_probe_m3"})
    for t in catalog:
        dd.register_diagnostic(t)(lambda ctx, scope: {"note": "disposable"})
        seed_human_run_template(env, t, round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    # Cycles 1 and 2: byte-identical PRIMARY findings/evidence AND identical synthesis
    # disagreement/confidence -> streak should reach 1 after cycle 2 (matches old behavior).
    for _ in range(2):
        queue_cycle(
            primary={**PRIMARY_FINDINGS_A, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6},
            critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6},
            synthesis={
                "disagreement_handling": [{"disagreement": "X", "resolution": "preserved_unresolved", "reasoning": "r"}],
                "hypothesis_assessment": [{"hypothesis": "H", "likelihood": 0.5, "reasoning": "r"}],
                "unresolved_uncertainty": [], "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
                "strategic_recommendation": "Investigate further.", "confidence": 0.5,
            },
        )
    # Cycle 3: PRIMARY findings/evidence STILL byte-identical, but the disagreement is now
    # resolved and confidence moved sharply -> fingerprint must differ, streak must reset to 0.
    queue_cycle(
        primary={**PRIMARY_FINDINGS_A, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6},
        critique={**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6},
        synthesis={
            "disagreement_handling": [{"disagreement": "X", "resolution": "resolved", "reasoning": "r2"}],
            "hypothesis_assessment": [{"hypothesis": "H", "likelihood": 0.9, "reasoning": "r2"}],
            "unresolved_uncertainty": [], "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY",
            "strategic_recommendation": "Converging.", "confidence": 0.9,
        },
    )
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=catalog)
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    # If SYNTHESIS movement were ignored (old PRIMARY-only fingerprint), this would have hit
    # STOP_NO_NEW_EVIDENCE at cycle 3 (2 consecutive identical PRIMARY-only fingerprints:
    # cycle2==cycle1, cycle3==cycle2). With SYNTHESIS movement included, cycle 3's fingerprint
    # differs from cycle 2's, so the loop only stops here because the catalog (3 entries) is
    # now exhausted -- a different, correct reason.
    assert packet["cycles_run"] == 3, packet
    assert packet["stop_decision"] == "STOP_SAFETY_ESCALATION", packet
    final_state = dal.load_issue_state(packet["issue_id"], env["autonomous_dir"])
    assert final_state.no_new_evidence_streak == 0, (
        f"expected the streak to have reset at cycle 3 due to synthesis movement, got "
        f"{final_state.no_new_evidence_streak}"
    )
    shutil.rmtree(env["root"])
    record("SYNTHESIS disagreement-resolution and confidence movement reset the no-new-evidence streak even with identical PRIMARY facts", True)


# ---------------------------------------------------------------------------
# Scenario 15/16/17 (item 4): bounded transient-provider retry.
# ---------------------------------------------------------------------------

def _round_reviewer_records(observations_path: Path, reviewer_id: str) -> list[dict[str, Any]]:
    records = []
    for line in observations_path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("reviewer_id") == reviewer_id:
            records.append(rec)
    return records


def scenario_transient_retry_succeeds_and_records_both_attempts() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_15", "snap_seed_15"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    ScriptedFixtureProvider.queue.append(TransientModelProviderError("simulated transient JSON-parse flake"))
    ScriptedFixtureProvider.queue.append({**PRIMARY_FINDINGS_A, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY", "confidence": 0.6})
    ScriptedFixtureProvider.queue.append({**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6})
    ScriptedFixtureProvider.queue.append({**BENIGN_SYNTHESIS_BASE, "recommendation_type": "NO_ACTION", "status": "OBSERVATION_ONLY",
                                           "strategic_recommendation": "done", "confidence": 0.6})
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 1, packet
    assert packet["stop_decision"] == "STOP_NO_CHANGE_JUSTIFIED", packet  # the cycle still succeeded overall
    primary_records = _round_reviewer_records(env["observations_path"], "director-primary")
    primary_records = [r for r in primary_records if r["round_id"] == packet["round_ids"][0]]
    failed = [r for r in primary_records if "error" in r]
    succeeded = [r for r in primary_records if "output" in r]
    assert len(failed) == 1 and failed[0].get("attempt_number") == 1, primary_records
    assert len(succeeded) == 1, primary_records
    shutil.rmtree(env["root"])
    record("a transient failure followed by a successful retry records BOTH attempts and the cycle still completes", True)


def scenario_transient_retry_exhausted_escalates_with_two_failure_records() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_16", "snap_seed_16"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    ScriptedFixtureProvider.queue.append(TransientModelProviderError("flake 1"))
    ScriptedFixtureProvider.queue.append(TransientModelProviderError("flake 2 -- retry also fails"))
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["cycles_run"] == 1, packet
    assert packet["stop_decision"] == "STOP_SAFETY_ESCALATION", packet
    primary_records = _round_reviewer_records(env["observations_path"], "director-primary")
    failed = [r for r in primary_records if "error" in r and r.get("attempt_number") in (1, 2)]
    assert len(failed) == 2, primary_records
    assert {r["attempt_number"] for r in failed} == {1, 2}, primary_records
    shutil.rmtree(env["root"])
    record("a transient failure whose retry also fails escalates after exactly 2 attempts, both recorded, never a 3rd", True)


def scenario_nontransient_failure_is_never_retried() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_17", "snap_seed_17"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    # A schema-validation failure (confidence must be a number) -- NOT a TransientModelProviderError
    # -- must never be retried, per the Founder's explicit instruction.
    ScriptedFixtureProvider.queue.append({**PRIMARY_FINDINGS_A, "recommendation_type": "NO_ACTION",
                                           "status": "OBSERVATION_ONLY", "confidence": "not-a-number"})
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["stop_decision"] == "STOP_SAFETY_ESCALATION", packet
    primary_records = _round_reviewer_records(env["observations_path"], "director-primary")
    failed = [r for r in primary_records if "error" in r]
    assert len(failed) == 1, f"a non-transient (schema validation) failure must never be retried: {primary_records}"
    shutil.rmtree(env["root"])
    record("a non-transient (schema validation) failure is recorded once and never retried", True)


# ---------------------------------------------------------------------------
# Scenario 18/19 (item 5): hard per-run model-call budget.
# ---------------------------------------------------------------------------

def scenario_model_call_budget_stops_safely_before_exceeding() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_18", "snap_seed_18"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_paid_test_only")

    ScriptedPaidLookingProvider.call_count = 0
    ScriptedPaidLookingProvider.queue.append({**PRIMARY_FINDINGS_A, "recommendation_type": "DIAGNOSTIC_INVESTIGATION", "status": "OBSERVATION_ONLY", "confidence": 0.6})
    ScriptedPaidLookingProvider.queue.append({**BENIGN_CRITIQUE, "status": "OBSERVATION_ONLY", "confidence": 0.6})
    ScriptedPaidLookingProvider.queue.append({**BENIGN_SYNTHESIS_BASE, "recommendation_type": "DIAGNOSTIC_INVESTIGATION",
                                               "status": "OBSERVATION_ONLY", "strategic_recommendation": "x", "confidence": 0.6})
    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    try:
        packet = run_investigation(
            env, reviewers_path, round_id, max_cycles=5, catalog=frozenset({"_fixture_test_probe"}), max_paid_calls=2,
        )
    finally:
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    assert packet["paid_calls_used"] == 2, packet  # PRIMARY + CRITIQUE happened; SYNTHESIS (3rd) was blocked
    assert packet["max_paid_calls"] == 2, packet
    assert packet["stop_decision"] == "STOP_SAFETY_ESCALATION", packet
    assert ScriptedPaidLookingProvider.call_count == 2, (
        f"expected exactly 2 real provider calls to have actually happened, got {ScriptedPaidLookingProvider.call_count}"
    )
    shutil.rmtree(env["root"])
    record("a 2-call budget permits exactly 2 real provider calls and blocks the 3rd before it happens, stopping safely", True)


def scenario_max_paid_calls_ceiling_not_overridable() -> None:
    env = build_env()
    with expect(dal.AutonomousLoopSafetyError):
        dal.create_issue(originating_round_id="round_x", max_paid_calls=dal.HARD_MAX_PAID_CALLS_CEILING + 1, autonomous_dir=env["autonomous_dir"])
    with expect(dal.AutonomousLoopSafetyError):
        dal.create_issue(originating_round_id="round_x", max_paid_calls=0, autonomous_dir=env["autonomous_dir"])
    shutil.rmtree(env["root"])
    record(f"max_paid_calls cannot be set above the hard ceiling ({dal.HARD_MAX_PAID_CALLS_CEILING}) or below 1", True)


# ---------------------------------------------------------------------------
# Scenario 20 (item 7): single-process concurrency lock.
# ---------------------------------------------------------------------------

def scenario_concurrency_lock_blocks_second_run() -> None:
    env = build_env()
    round_id, snapshot_id = "round_seed_20", "snap_seed_20"
    seed_originating_round(env, round_id, snapshot_id)
    seed_human_run_template(env, "_fixture_test_probe", round_id, snapshot_id)
    reviewers_path = write_reviewers_json(env["root"], "scripted_fixture_test_only")

    dal.AUTONOMOUS_EXECUTION_ENABLED = True
    lock_cm = dal._autonomous_run_lock(env["autonomous_dir"])
    lock_cm.__enter__()
    try:
        with expect(dal.ConcurrentAutonomousRunError):
            run_investigation(env, reviewers_path, round_id, max_cycles=1, catalog=frozenset({"_fixture_test_probe"}))
    finally:
        lock_cm.__exit__(None, None, None)
        dal.AUTONOMOUS_EXECUTION_ENABLED = False
    # Confirm nothing was created: the lock check happens before create_issue.
    assert list((env["autonomous_dir"]).glob("issue_*")) == [], "no issue should have been created while locked out"
    shutil.rmtree(env["root"])
    record("a second concurrent autonomous run against the same Director state is refused, not queued or interleaved", True)


def _snapshot_real_state() -> dict[str, Any]:
    """Everything this fixture-test run must leave provably untouched:
    the real Director history ledger, the real cursor, and the real live
    Village database (event count + clock)."""
    real_history = _REAL_ROUNDS_HISTORY_PATH.read_bytes() if _REAL_ROUNDS_HISTORY_PATH.exists() else None
    cursor_path = REPO_ROOT / ".director" / "cursor.json"
    real_cursor = cursor_path.read_bytes() if cursor_path.exists() else None
    live_db = None
    try:
        import sqlite3
        from app.core.db_safety import CANONICAL_LIVE_DB_PATH
        if CANONICAL_LIVE_DB_PATH.exists():
            conn = sqlite3.connect(f"file:{CANONICAL_LIVE_DB_PATH}?mode=ro", uri=True)
            try:
                live_db = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            finally:
                conn.close()
    except Exception:  # noqa: BLE001 — best-effort; absence of the live DB is not this test's concern
        live_db = "unavailable"
    return {"history": real_history, "cursor": real_cursor, "live_db_event_count": live_db}


def main() -> int:
    before = _snapshot_real_state()
    scenarios = [
        scenario_shipped_default_is_inert,
        scenario_template_replay_and_fail_closed,
        scenario_option_b_no_change,
        scenario_option_a_code_change,
        scenario_permission_expansion_escalation,
        scenario_permission_expansion_negation_awareness,
        scenario_no_new_evidence_streak,
        scenario_max_cycles,
        scenario_catalog_exhaustion,
        scenario_max_cycles_ceiling_not_overridable,
        scenario_level2b_experiment_runs_via_catalog,
        scenario_level2a_tried_before_level2b,
        scenario_evidence_driven_template_selection_prefers_overlap,
        scenario_template_selection_falls_back_to_latest_with_no_overlap,
        scenario_diminishing_returns_recognizes_synthesis_movement,
        scenario_transient_retry_succeeds_and_records_both_attempts,
        scenario_transient_retry_exhausted_escalates_with_two_failure_records,
        scenario_nontransient_failure_is_never_retried,
        scenario_model_call_budget_stops_safely_before_exceeding,
        scenario_max_paid_calls_ceiling_not_overridable,
        scenario_concurrency_lock_blocks_second_run,
    ]
    for scenario in scenarios:
        try:
            scenario()
        except Exception as exc:  # noqa: BLE001 — a scenario failure must never abort the whole report
            record(scenario.__name__, False, f"{type(exc).__name__}: {exc}")
        finally:
            dal.AUTONOMOUS_EXECUTION_ENABLED = False  # never leave the gate open between scenarios

    after = _snapshot_real_state()
    real_state_untouched = before == after
    record("real .director/history/rounds.jsonl, cursor.json, and live Village DB event count all unchanged", real_state_untouched,
           "" if real_state_untouched else f"before={before} after={after}")

    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} scenarios passed.")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
