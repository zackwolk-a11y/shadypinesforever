"""Director Level 2A/2B autonomous investigation loop — DESIGN + FIXTURE-TESTED,
NOT ACTIVATED.

Purpose: once explicitly activated by a separate, future Founder decision,
this module lets the Director iterate through several cycles of
read-only Level 2A diagnostics and disposable Level 2B experiments —
each cycle feeding its evidence through the existing PRIMARY -> CRITIQUE ->
deterministic reconciliation -> SYNTHESIS chain (director_loop.py) — without
a human clicking "approve" between every single cycle. It removes the
Founder from *routine* iteration, not from the decision that matters: the
loop can never implement anything, and always ends by handing back exactly
one Founder Packet (a production-change recommendation, a no-change
recommendation, or an escalation) for a human to act on.

THE MASTER KILL SWITCH — read this first
------------------------------------------
``AUTONOMOUS_EXECUTION_ENABLED`` (module constant, below) is ``False``.
``run_autonomous_investigation`` and ``run_cycle`` both refuse to do
anything at all while it is ``False`` — no diagnostic is created, no
reviewer is called, no state is written. Flipping it to ``True`` is a
distinct, separate, explicit Founder-authorized code change; it is not
flipped by this delivery. Fixture tests exercise the loop's mechanics by
monkeypatching this module attribute to ``True`` inside an isolated test
process only — the shipped value here on disk stays ``False``.

WHY the safety model looks the way it does
-------------------------------------------
Every prior Director capability tier in this repo (Level 1 observation,
Level 2A diagnostics, Level 2B experiments) earns safety not by trusting a
model's judgment at runtime, but by shrinking what is even *reachable* at
runtime to a fixed, human-reviewed, hardcoded set — see
director_diagnostics.DiagnosticContext's capability surface and its
ALLOWED_SERVICE_FUNCTIONS ceiling, and director_experiments.
ExperimentContext (the Level 2B analog — deliberately narrower still: no
read_live_db at all). This module inherits that posture exactly, and adds
nothing that breaks it:

1. Closed catalogs. AUTONOMOUS_DIAGNOSTIC_CATALOG and
   AUTONOMOUS_LEVEL2B_CATALOG are hardcoded, module-level, and are the ONLY
   things the loop may ever invoke autonomously. Registering a new
   diagnostic_type/experiment_type (a code change) does NOT automatically
   make it autonomous-eligible — adding it to one of these two catalogs is
   a second, separate, explicit edit.
2. No free-text execution, ever. The loop decides its next action solely
   from the closed ``RecommendationType`` enum a SYNTHESIS reviewer
   returns (itself schema-validated and rejecting APPROVED_TO_TEST — see
   director_reviewers.run_reviewer). A reviewer's prose is never parsed
   into an action. It can only be *scanned* for permission-expansion red
   flags (check_permission_expansion, defense-in-depth, not the primary
   control) and, if flagged, force an immediate escalation.
3. Parameter replay-or-bounded-selection, never invention. A cycle that
   runs a Level 2A diagnostic or Level 2B experiment never invents its
   allowed_operations/scope — it SELECTS among (never synthesizes new
   values for) the scopes of that type's completed, human-run specs on
   disk (_select_diagnostic_template / _select_experiment_template),
   scoring each by how many identifiers it shares with evidence already
   collected for this issue (originating round + prior cycles) — a
   selector, not a generator: every candidate scope was already run by a
   human at least once. If no human has ever run a given type at least
   once, the autonomous loop structurally cannot run it either.
4. approve_diagnostic / approve_experiment's state machines are untouched
   and still the sole CANDIDATE->APPROVED transitions. This module becomes
   a second legitimate caller of each ONLY once AUTONOMOUS_EXECUTION_ENABLED
   is True, and every such call is tagged
   ``approved_by="autonomous_director_loop"`` — distinguishable forever
   from a human's "Founder" approval on disk.
5. Every hard boundary the Founder listed (no production code
   modification, no live DB writes, no simulation advancement, no
   migrations/restores/seeding, no .env/credential/provider/security-control
   changes, no merging experimental code, no permission expansion, no
   external consequential actions, no changes to autonomy principles, no
   forcing agents to speak/research/socialize) is inherited unchanged from
   DiagnosticContext (Level 2A), ExperimentContext (Level 2B), and
   director_level2b_experiment.py's falsification checks (e.g.
   does_not_force_or_incentivize_speech) — this module adds no new
   capability surface of its own; it only sequences and rate-limits calls
   into capability surfaces that already exist and were already reviewed.
6. Level 2B is genuinely usable, not just structurally wired: director_
   experiments.py generalizes director_level2b_experiment.py's existing,
   already-Founder-reviewed speaker-selection A/B mechanism into a
   registered, catalog-addressable experiment_type
   ("speaker_selection_fair_opportunity_ab"). Adding a real entry to
   AUTONOMOUS_LEVEL2B_CATALOG required a human to have already run that
   experiment_type to completion at least once through the new state
   machine (the same replay-only precondition Level 2A diagnostics have)
   — done as a separate, explicit Founder-authorized act (see
   scripts/_catalog_level2b_speaker_selection_experiment.py and
   .director/experiments/exp_dff800958f43425e/spec.json, approved_by
   "Founder", state EXPERIMENT_COMPLETE/SUCCESS), re-cataloging the
   already-Founder-accepted round_73da274827304dbe evidence through this
   state machine — not re-investigating or re-deciding the underlying
   speaker-selection question. The catalog entry only makes the
   experiment_type *selectable* once AUTONOMOUS_EXECUTION_ENABLED is
   separately flipped to True; it does not itself authorize or start
   anything.
7. Model-call budget. Every real (non-fixture) provider call this module's
   chain calls make — PRIMARY, each CRITIQUE, SYNTHESIS, and any bounded
   transient retry of any of those — is counted against
   IssueState.max_paid_calls, itself capped at the hardcoded
   HARD_MAX_PAID_CALLS_CEILING no caller can raise. The check happens
   BEFORE a real provider is constructed (_enforce_call_budget), so a call
   that would exceed budget never happens at all — the cycle fails closed
   into STOP_SAFETY_ESCALATION via the exact same path a review-chain
   failure already takes (ModelCallBudgetExceededError is a
   ModelProviderError subclass).
8. Single-process concurrency lock. run_autonomous_investigation acquires
   an exclusive, non-blocking flock on autonomous_dir/.autonomous_loop.lock
   before creating an issue or taking any action; a second concurrent
   invocation against the same autonomous_dir refuses to start
   (ConcurrentAutonomousRunError) rather than risk interleaved writes to
   shared Director state.

Stopping rules (evaluate_stopping_rules), all mechanical:

    - max 5 cycles per issue (default; caller-configurable, never removable)
    - a hard per-run model-call budget (HARD_MAX_PAID_CALLS_CEILING,
      caller-configurable downward only) enforced independently of cycles
    - stop early after 2 CONSECUTIVE cycles that add no materially new
      investigation content — not just PRIMARY's raw findings/evidence, but
      also CRITIQUE's disagreements and SYNTHESIS's hypothesis-likelihood/
      confidence movement and which disagreements remain unresolved (see
      investigation_fingerprint), so genuine analytical convergence with
      unchanged raw facts is never mistaken for "nothing happened"
    - stop the moment SYNTHESIS's recommendation_type is CODE_CHANGE
      (-> Founder Packet option A) or NO_ACTION (-> option B)
    - stop immediately, unconditionally, on any permission-expansion flag,
      any PROMPT_OR_CALIBRATION_CHANGE/OTHER recommendation (out of
      autonomous scope by design — always a human call), any reviewer-chain
      failure, or catalog exhaustion with the issue still unresolved
      (-> option C, Founder escalation)

The loop never calls director_bridge.record_founder_decision — accepting
evidence into the durable Bridge ledger remains a human Founder act, done
separately, exactly as every prior round in this repo's history has been
accepted.
"""

from __future__ import annotations

import enum
import fcntl
import hashlib
import json
import os
import re
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_providers  # noqa: E402
import director_reviewers  # noqa: E402
from director_diagnostics import (  # noqa: E402
    DEFAULT_DIAGNOSTICS_DIR,
    DiagnosticSafetyError,
    DiagnosticSpec,
    DiagnosticState,
    approve_diagnostic,
    create_candidate_diagnostic,
    run_diagnostic,
)
from director_experiments import (  # noqa: E402
    DEFAULT_EXPERIMENTS_DIR,
    ExperimentSpec,
    ExperimentState,
    approve_experiment,
    create_candidate_experiment,
    run_experiment,
)
from director_loop import (  # noqa: E402
    DEFAULT_OBSERVATIONS_PATH,
    DEFAULT_PACKETS_DIR,
    DEFAULT_SNAPSHOTS_DIR,
    DirectorLoopError,
    load_records_for_round,
    run_diagnostic_review_chain,
    run_experiment_review_chain,
)
from director_providers import ModelProviderError  # noqa: E402

DIRECTOR_DIR = REPO_ROOT / ".director"
DEFAULT_AUTONOMOUS_DIR = DIRECTOR_DIR / "autonomous"

#: THE MASTER KILL SWITCH. See module docstring. Flipping this to True is a
#: distinct, future, explicit Founder-authorized change — not part of this
#: design+fixture-test delivery.
AUTONOMOUS_EXECUTION_ENABLED = False

#: Closed, hardcoded set of Level 2A diagnostic_types the autonomous loop
#: may invoke. Deliberately a SUBSET of director_diagnostics.py's
#: registered implementations, chosen explicitly here rather than derived
#: from that registry automatically — registering a new diagnostic type is
#: a code change; making it autonomous-eligible is a second, separate one.
#: All five below already have at least one human-run, Founder-reviewed,
#: DIAGNOSTIC_COMPLETE/SUCCESS spec on disk (see _select_diagnostic_template).
AUTONOMOUS_DIAGNOSTIC_CATALOG: frozenset[str] = frozenset({
    "conversation_lifecycle_trace",
    "conversation_scheduler_isolated_test",
    "conversation_scheduler_policy_probe",
    "conversation_message_persistence_and_threshold_probe",
    "morning_gathering_construction_and_invalid_decision_trace",
})

#: Closed, hardcoded set of Level 2B experiment_types the autonomous loop
#: may invoke. See module docstring point 6.
#: "speaker_selection_fair_opportunity_ab" has a completed, Founder-approved
#: (approved_by="Founder"), SUCCESS spec on disk
#: (.director/experiments/exp_dff800958f43425e/spec.json) satisfying
#: AUTONOMOUS_DIAGNOSTIC_CATALOG's exact precondition. This is the ONLY
#: entry; nothing else is autonomous-eligible. Membership here does not by
#: itself enable autonomous execution — AUTONOMOUS_EXECUTION_ENABLED (still
#: False) is the separate, independent kill switch that gates whether this
#: catalog is ever consulted at all.
AUTONOMOUS_LEVEL2B_CATALOG: frozenset[str] = frozenset({"speaker_selection_fair_opportunity_ab"})

#: Hard ceiling on IssueState.max_paid_calls, not caller-raisable. Derived
#: from the worst case this architecture can produce: 5 cycles (the
#: max_cycles ceiling) x up to 3 reviewer roles per cycle (PRIMARY + 1
#: default CRITIQUE + SYNTHESIS) x up to 2 attempts per role (1 bounded
#: transient retry) = 30.
HARD_MAX_PAID_CALLS_CEILING = 30


class AutonomousExecutionNotAuthorizedError(RuntimeError):
    """Raised by run_cycle / run_autonomous_investigation whenever
    AUTONOMOUS_EXECUTION_ENABLED is False. Always raised before any other
    side effect — no spec, round, or state file is ever created first."""


class AutonomousLoopSafetyError(RuntimeError):
    """A structural safety invariant was violated (e.g. a catalog action
    reached run_cycle that isn't actually in the catalog). Distinct from
    AutonomousExecutionNotAuthorizedError so tests can tell "never
    authorized" apart from "authorized but something was structurally
    wrong" — both are fail-closed, but for different reasons."""


class ModelCallBudgetExceededError(ModelProviderError):
    """A cycle's next real provider call would exceed
    IssueState.max_paid_calls. A ModelProviderError subclass so it fails
    closed through the exact same path a review-chain failure already
    takes (director_loop.py's `except ModelProviderError: raise
    DirectorLoopError(...)`, then run_cycle's own `except (...,
    DirectorLoopError, ...)` -> STOP_SAFETY_ESCALATION) with zero changes
    needed to that existing, already-reviewed error handling."""


class ConcurrentAutonomousRunError(RuntimeError):
    """Another autonomous Director run already holds the lock on this
    autonomous_dir's Director state. Refuses to start rather than risk
    interleaved writes to observations.jsonl/snapshots/packets/issue
    state."""


class StoppingDecision(str, enum.Enum):
    CONTINUE = "CONTINUE"
    STOP_MAX_CYCLES = "STOP_MAX_CYCLES"
    STOP_NO_NEW_EVIDENCE = "STOP_NO_NEW_EVIDENCE"
    STOP_SUFFICIENT_FOR_RECOMMENDATION = "STOP_SUFFICIENT_FOR_RECOMMENDATION"
    STOP_NO_CHANGE_JUSTIFIED = "STOP_NO_CHANGE_JUSTIFIED"
    STOP_SAFETY_ESCALATION = "STOP_SAFETY_ESCALATION"


#: Maps a terminal StoppingDecision to which of the Founder's three
#: required Founder Packet options it produces. STOP_MAX_CYCLES,
#: STOP_NO_NEW_EVIDENCE, and STOP_SAFETY_ESCALATION all mean "the loop
#: cannot responsibly conclude on its own" -> Option C, escalate.
class FounderPacketOption(str, enum.Enum):
    A_PRODUCTION_CHANGE_RECOMMENDATION = "A_PRODUCTION_CHANGE_RECOMMENDATION"
    B_NO_CHANGE_RECOMMENDATION = "B_NO_CHANGE_RECOMMENDATION"
    C_FOUNDER_ESCALATION = "C_FOUNDER_ESCALATION"


_OPTION_BY_STOP_DECISION: dict[StoppingDecision, FounderPacketOption] = {
    StoppingDecision.STOP_SUFFICIENT_FOR_RECOMMENDATION: FounderPacketOption.A_PRODUCTION_CHANGE_RECOMMENDATION,
    StoppingDecision.STOP_NO_CHANGE_JUSTIFIED: FounderPacketOption.B_NO_CHANGE_RECOMMENDATION,
    StoppingDecision.STOP_MAX_CYCLES: FounderPacketOption.C_FOUNDER_ESCALATION,
    StoppingDecision.STOP_NO_NEW_EVIDENCE: FounderPacketOption.C_FOUNDER_ESCALATION,
    StoppingDecision.STOP_SAFETY_ESCALATION: FounderPacketOption.C_FOUNDER_ESCALATION,
}

#: recommendation_types that are always, unconditionally, an escalation —
#: never something the loop tries to "handle" by picking a next diagnostic.
#: Changing a prompt/calibration is exactly the kind of production change
#: that needs a human's judgment about Village autonomy principles; "OTHER"
#: is definitionally outside the closed action space.
_ALWAYS_ESCALATE_RECOMMENDATION_TYPES = frozenset({"PROMPT_OR_CALIBRATION_CHANGE", "OTHER"})

#: Defense-in-depth only — see module docstring point 2. A hit here always
#: forces STOP_SAFETY_ESCALATION regardless of what recommendation_type
#: says, but the ABSENCE of a hit grants nothing: the loop's actual ceiling
#: is the closed catalogs plus DiagnosticContext/ExperimentContext, not
#: this list.
_PERMISSION_EXPANSION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (
        r"\bmodify (the )?production\b",
        r"\bwrite (directly )?to the live\b",
        r"\brun the village\b",
        r"\badvance (the )?simulation\b",
        r"\badvance sim_day\b",
        r"\bmodify\b.{0,30}\.env\b",
        r"\bapi[_ -]?key\b",
        r"\bcredential\b",
        r"\bmerge\b.{0,30}\bproduction\b",
        r"\brestore\b.{0,30}\b(database|db|backup)\b",
        r"\bmigrat(e|ion)\b",
        r"\bseed (the )?(live|production) (database|db)\b",
        r"\bexpand (its own |the loop'?s )?permission",
        r"\bgrant (itself|the loop) (access|permission)",
        r"\bdisable (the )?safety\b",
        r"\bbypass\b.{0,30}\b(safety|boundary|boundaries|guard)\b",
        r"\bforce\b.{0,30}\b(speak|research|socializ|engage|activity)\b",
        r"\bwithout founder\b",
        r"\bskip founder\b",
        r"\braise (the )?(cycle|call|budget) (limit|ceiling|cap)\b",
        r"\bincrease max_paid_calls\b",
    )
)


#: Post-stress-test fix (Founder Packet 2026-09-04, self-test finding): the
#: 2026-09-03 run escalated on a SYNTHESIS reviewer's own explicit
#: prohibition -- "...do not alter prompts or code and do not run the
#: Village" -- because the bare pattern matched inside it. Negation cues
#: found in the short span immediately before a match suppress that one
#: match. Deliberately narrow and conservative: this changes ONLY what
#: check_permission_expansion reports, nothing else -- STANDARD_FORBIDDEN_
#: OPERATIONS, the closed catalogs, DiagnosticContext/ExperimentContext's
#: capability surfaces, and every hard ceiling are untouched, and a
#: negation cue that does not actually negate the risky verb (e.g. "we
#: should not merely avoid but actively pursue expanding permissions") is
#: not something this narrow, non-semantic fix can be expected to catch --
#: it targets the common case (an explicit, direct prohibition in the
#: reviewer's own words), not general natural-language understanding.
_NEGATION_CUE_PATTERN = re.compile(
    r"\b(do not|don'?t|does not|doesn'?t|did not|didn'?t|must not|mustn'?t|should not|shouldn'?t|"
    r"will not|won'?t|cannot|can'?t|never|avoid(?:s|ed|ing)?|refus(?:e|es|ed|ing) to|without|no)\b",
    re.IGNORECASE,
)
#: Clause boundaries (sentence-ending punctuation or an em-dash) — negation
#: is scoped to the CLAUSE containing the match, not a fixed character
#: window. A short fixed window (tried first) missed realistic phrasing
#: like "does not require any database restore or migration", where the
#: negation cue sits well before the flagged word but still governs it
#: within the same clause. Clause-scoping also means a negation in one
#: sentence never suppresses a genuinely risky, unnegated statement in a
#: later sentence of the same text field (see the "mixed" fixture case in
#: director_autonomous_loop_fixturetest.py).
_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[.!?;]|—")


def _clause_start(text: str, pos: int) -> int:
    """Offset of the start of the clause containing `pos`: just after the
    nearest clause-boundary character at or before `pos`, or 0 if none."""
    start = 0
    for m in _CLAUSE_BOUNDARY_PATTERN.finditer(text, 0, pos):
        start = m.end()
    return start


def check_permission_expansion(*text_fields: str | None) -> list[str]:
    """Scan free-text reviewer output for hardcoded red-flag phrases. A hit
    forces an immediate escalation. Never the primary control — see module
    docstring point 2 — but a real tripwire: this fires on both the
    structured recommendation_type AND anything hiding in prose.

    Negation-aware (see _NEGATION_CUE_PATTERN above): a match immediately
    preceded by an explicit prohibition cue (e.g. "do not run the Village")
    is not reported as a hit. A genuine, unnegated request to do the risky
    thing (e.g. "run the Village to see what happens") still escalates
    exactly as before -- this narrows false positives, it does not weaken
    the tripwire's ability to catch a real permission-expansion request."""
    hits: list[str] = []
    for text in text_fields:
        if not text:
            continue
        for pattern in _PERMISSION_EXPANSION_PATTERNS:
            for match in pattern.finditer(text):
                preceding = text[_clause_start(text, match.start()):match.start()]
                if _NEGATION_CUE_PATTERN.search(preceding):
                    continue
                hits.append(f"pattern {pattern.pattern!r} matched {match.group(0)!r} in: {text[:200]!r}")
    return hits


#: Identifiers = bare integers (conversation_id, event_id, etc. are always
#: ints in this schema — see e.g. round_73da274827304dbe's evidence). Used
#: only as a SELECTION signal among already-human-approved scopes (item 2)
#: — never parsed into a new value, never inserted into a scope verbatim.
_IDENTIFIER_PATTERN = re.compile(r"\b\d+\b")


def _extract_identifiers(*texts: str | None) -> set[str]:
    ids: set[str] = set()
    for text in texts:
        if text:
            ids.update(_IDENTIFIER_PATTERN.findall(text))
    return ids


def _scope_identifiers(scope: dict[str, Any]) -> set[str]:
    return _extract_identifiers(json.dumps(scope, default=str, sort_keys=True))


def investigation_fingerprint(
    *,
    primary_findings: list[str],
    primary_evidence: list[str],
    critique_disagreements: list[str],
    synthesis_unresolved_disagreements: list[str],
    synthesis_hypothesis_buckets: list[str],
    synthesis_confidence_bucket: float | None,
) -> str:
    """Deterministic fingerprint of everything about one cycle that
    represents genuine investigative content — not just PRIMARY's raw
    findings/evidence citations (which alone would treat a cycle that
    resolves a disagreement, or meaningfully shifts SYNTHESIS's confidence,
    as "nothing new" whenever the underlying facts happen to repeat).
    Confidence/likelihood values are bucketed to the nearest 0.05 before
    hashing so float noise from run to run never counts as movement, while
    a real shift (e.g. 0.6 -> 0.85) still does. Order-independent (sorted)
    so re-stating the same content in a different order never counts as
    new."""
    def _bucket(x: float | None) -> float | None:
        return None if x is None else round(round(x / 0.05) * 0.05, 2)

    canonical = json.dumps({
        "findings": sorted(primary_findings),
        "evidence": sorted(primary_evidence),
        "critique_disagreements": sorted(critique_disagreements),
        # Only the UNRESOLVED set matters for "did the analysis move" — a
        # disagreement flipping from preserved_unresolved to resolved
        # shrinks this set and correctly changes the fingerprint even if
        # every raw fact cited stayed identical.
        "synthesis_unresolved_disagreements": sorted(synthesis_unresolved_disagreements),
        "synthesis_hypothesis_buckets": sorted(synthesis_hypothesis_buckets),
        "synthesis_confidence_bucket": _bucket(synthesis_confidence_bucket),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IssueState(BaseModel):
    """Persisted at .director/autonomous/{issue_id}/state.json after every
    cycle. The only mutable state this module owns; everything else it
    produces (diagnostic/experiment specs, rounds, snapshots, packets)
    already has its own persistence via director_diagnostics.py /
    director_experiments.py / director_loop.py."""

    issue_id: str
    originating_round_id: str
    max_cycles: int = 5
    max_paid_calls: int = HARD_MAX_PAID_CALLS_CEILING
    created_at: str
    cycles_run: int = 0
    paid_calls_used: int = 0
    diagnostic_types_tried: list[str] = Field(default_factory=list)
    level2b_experiments_tried: list[str] = Field(default_factory=list)
    round_ids: list[str] = Field(default_factory=list)
    diagnostic_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    #: Running, deduplicated accumulation of every PRIMARY finding/evidence
    #: citation seen so far for this issue (seeded from the originating
    #: round at create_issue, then appended-to after each cycle) — the
    #: evidence pool item 2's template selectors match against. Never used
    #: to synthesize a new scope value, only to SELECT among already
    #: human-approved candidate scopes.
    accumulated_findings: list[str] = Field(default_factory=list)
    accumulated_evidence: list[str] = Field(default_factory=list)
    evidence_fingerprints: list[str] = Field(default_factory=list)
    no_new_evidence_streak: int = 0
    status: str = "IN_PROGRESS"
    stop_decision: str | None = None
    stop_reason: str | None = None


def _issue_state_path(issue_id: str, autonomous_dir: Path) -> Path:
    return autonomous_dir / issue_id / "state.json"


def save_issue_state(state: IssueState, autonomous_dir: Path = DEFAULT_AUTONOMOUS_DIR) -> Path:
    path = _issue_state_path(state.issue_id, autonomous_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2) + "\n")
    return path


def load_issue_state(issue_id: str, autonomous_dir: Path = DEFAULT_AUTONOMOUS_DIR) -> IssueState:
    path = _issue_state_path(issue_id, autonomous_dir)
    if not path.exists():
        raise AutonomousLoopSafetyError(f"no issue state at {path}.")
    return IssueState.model_validate_json(path.read_text())


def create_issue(
    *,
    originating_round_id: str,
    max_cycles: int = 5,
    max_paid_calls: int = HARD_MAX_PAID_CALLS_CEILING,
    autonomous_dir: Path = DEFAULT_AUTONOMOUS_DIR,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
) -> IssueState:
    if max_cycles < 1 or max_cycles > 5:
        raise AutonomousLoopSafetyError(
            f"max_cycles must be in [1, 5] — the Founder-set ceiling of 5 investigation cycles "
            f"per issue is not caller-overridable upward. Got {max_cycles!r}."
        )
    if max_paid_calls < 1 or max_paid_calls > HARD_MAX_PAID_CALLS_CEILING:
        raise AutonomousLoopSafetyError(
            f"max_paid_calls must be in [1, {HARD_MAX_PAID_CALLS_CEILING}] — the hard model-call "
            f"budget ceiling is not caller-overridable upward. Got {max_paid_calls!r}."
        )
    seed_findings: list[str] = []
    seed_evidence: list[str] = []
    try:
        seed_records = load_records_for_round(observations_path, originating_round_id, role="PRIMARY")
        if seed_records:
            seed_output = seed_records[-1].get("output", {})
            seed_findings = list(seed_output.get("findings", []))
            seed_evidence = list(seed_output.get("evidence", []))
    except Exception:  # noqa: BLE001 — seeding is a targeting enhancement, not safety-critical; a
        # failure here only means the first cycle's template selector falls back to "most recent",
        # never a fabricated or unsafe scope.
        pass
    state = IssueState(
        issue_id=f"issue_{uuid.uuid4().hex[:16]}",
        originating_round_id=originating_round_id,
        max_cycles=max_cycles,
        max_paid_calls=max_paid_calls,
        created_at=datetime.now(timezone.utc).isoformat(),
        accumulated_findings=seed_findings,
        accumulated_evidence=seed_evidence,
    )
    save_issue_state(state, autonomous_dir)
    return state


def _select_completed_specs(
    spec_model: type, complete_state: Any, type_field: str, type_value: str, specs_dir: Path,
) -> list[Any]:
    """Shared scan-and-filter core for _select_diagnostic_template /
    _select_experiment_template: every completed, human-or-loop-run,
    SUCCESS spec of the given type under specs_dir, oldest first.
    ``complete_state`` is passed explicitly (DiagnosticState.
    DIAGNOSTIC_COMPLETE / ExperimentState.EXPERIMENT_COMPLETE) rather than
    derived from the enum's member order, so this never silently breaks if
    either enum is ever reordered."""
    candidates: list[Any] = []
    if specs_dir.exists():
        for spec_file in sorted(specs_dir.glob("*/spec.json")):
            try:
                spec = spec_model.model_validate_json(spec_file.read_text())
            except Exception:  # noqa: BLE001 — a malformed spec file is never a template candidate
                continue
            if (
                getattr(spec, type_field) == type_value
                and spec.state is complete_state
                and spec.run_status == "SUCCESS"
            ):
                candidates.append(spec)
    candidates.sort(key=lambda s: s.completed_at or s.created_at)
    return candidates


def _select_best_by_evidence_overlap(candidates: list[Any], accumulated_identifiers: set[str]) -> Any:
    """Among already-human-approved candidate specs, pick the one whose
    scope shares the most identifiers with evidence already collected for
    this issue — never synthesizes a new scope, only selects among ones a
    human already ran. Falls back to the single most-recent candidate
    (identical to the old "always replay latest" behavior) when there's no
    accumulated evidence yet, or no candidate's scope overlaps it at all."""
    if not accumulated_identifiers:
        return candidates[-1]
    scored = sorted(
        candidates,
        key=lambda c: (len(_scope_identifiers(c.scope) & accumulated_identifiers), c.completed_at or c.created_at),
    )
    if len(_scope_identifiers(scored[-1].scope) & accumulated_identifiers) == 0:
        return candidates[-1]
    return scored[-1]


def _select_diagnostic_template(
    diagnostic_type: str, diagnostics_dir: Path, accumulated_identifiers: set[str] = frozenset(),
) -> DiagnosticSpec:
    """The autonomous loop never invents allowed_operations/scope for a
    diagnostic_type — it selects among the scopes of that type's completed,
    human-run, DIAGNOSTIC_COMPLETE/SUCCESS specs on disk, scored by
    identifier overlap with evidence already collected for this issue
    (falling back to "most recent" when there's nothing to select on, or no
    overlap at all — identical to the old always-replay-latest behavior in
    both cases). Fails closed if no human has ever run this diagnostic_type
    to completion yet."""
    candidates = _select_completed_specs(
        DiagnosticSpec, DiagnosticState.DIAGNOSTIC_COMPLETE, "diagnostic_type", diagnostic_type, diagnostics_dir,
    )
    if not candidates:
        raise DiagnosticSafetyError(
            f"no completed, human-run diagnostic of type {diagnostic_type!r} exists yet under "
            f"{diagnostics_dir} — the autonomous loop refuses to invent parameters for a diagnostic "
            "type that has never been run by a human at least once; it can only select among the "
            "allowed_operations/scope/success_criteria/failure_criteria/timeout_seconds of "
            "already-Founder-vetted invocations."
        )
    return _select_best_by_evidence_overlap(candidates, accumulated_identifiers)


def _select_experiment_template(
    experiment_type: str, experiments_dir: Path, accumulated_identifiers: set[str] = frozenset(),
) -> ExperimentSpec:
    """Level 2B analog of _select_diagnostic_template — identical
    selection logic, over director_experiments.ExperimentSpec/ExperimentState
    instead."""
    candidates = _select_completed_specs(
        ExperimentSpec, ExperimentState.EXPERIMENT_COMPLETE, "experiment_type", experiment_type, experiments_dir,
    )
    if not candidates:
        raise DiagnosticSafetyError(
            f"no completed, human-run experiment of type {experiment_type!r} exists yet under "
            f"{experiments_dir} — the autonomous loop refuses to invent parameters for an experiment "
            "type that has never been run by a human at least once through this state machine; it can "
            "only select among the allowed_operations/scope/success_criteria/failure_criteria/"
            "timeout_seconds of already-Founder-vetted invocations."
        )
    return _select_best_by_evidence_overlap(candidates, accumulated_identifiers)


def _next_untried(catalog: frozenset[str], already_tried: list[str]) -> str | None:
    for item in sorted(catalog):
        if item not in already_tried:
            return item
    return None


@contextmanager
def _enforce_call_budget(issue_state: IssueState):
    """Wraps exactly one chain call. Intercepts director_reviewers.
    get_model_provider (the actual chokepoint every PRIMARY/CRITIQUE/
    SYNTHESIS call and retry funnels through — see director_reviewers.
    run_reviewer) so any call that would exceed issue_state.max_paid_calls
    raises ModelCallBudgetExceededError BEFORE a real provider is even
    constructed, never after. Fixture ("is_fixture=True") providers are
    never counted or budget-limited — this exists to cap real spend, not
    to interfere with fixture testing."""
    real_get_model_provider = director_reviewers.get_model_provider

    def _counting_get_model_provider(name: str | None = None, *, model: str | None = None, api_key: str | None = None):
        key = (name or os.getenv("DIRECTOR_PROVIDER") or "fixture").strip().lower()
        cls = director_providers._PROVIDERS.get(key)
        if cls is not None and not getattr(cls, "is_fixture", False):
            if issue_state.paid_calls_used >= issue_state.max_paid_calls:
                raise ModelCallBudgetExceededError(
                    f"model-call budget ({issue_state.max_paid_calls}) would be exceeded by this "
                    f"call to provider {key!r} (already used {issue_state.paid_calls_used})."
                )
            issue_state.paid_calls_used += 1
        return real_get_model_provider(name, model=model, api_key=api_key)

    director_reviewers.get_model_provider = _counting_get_model_provider
    try:
        yield
    finally:
        director_reviewers.get_model_provider = real_get_model_provider


@contextmanager
def _autonomous_run_lock(autonomous_dir: Path):
    """Exclusive, non-blocking flock covering one whole
    run_autonomous_investigation call — see module docstring point 8. A
    second concurrent call against the same autonomous_dir raises
    ConcurrentAutonomousRunError immediately rather than blocking or
    interleaving writes. flock's exclusivity is per open-file-description,
    not per-process, so this also correctly refuses re-entrant use within
    one process."""
    autonomous_dir.mkdir(parents=True, exist_ok=True)
    lock_path = autonomous_dir / ".autonomous_loop.lock"
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fd.close()
        raise ConcurrentAutonomousRunError(
            f"another autonomous Director run already holds the lock at {lock_path!s} — refusing to "
            "start a second concurrent run against the same Director state."
        ) from exc
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


@dataclass
class CycleResult:
    cycle_number: int
    action: str
    round_id: str | None
    diagnostic_id: str | None
    experiment_id: str | None
    recommendation_type: str | None
    recommendation_status: str | None
    confidence: float | None
    permission_expansion_flags: list[str] = field(default_factory=list)
    stop_decision: StoppingDecision = StoppingDecision.CONTINUE
    final_packet_path: str | None = None
    error: str | None = None


def evaluate_stopping_rules(
    issue_state: IssueState,
    *,
    recommendation_type: str | None,
    permission_expansion_flags: list[str],
    diagnostic_catalog: frozenset[str] = AUTONOMOUS_DIAGNOSTIC_CATALOG,
    level2b_catalog: frozenset[str] = AUTONOMOUS_LEVEL2B_CATALOG,
) -> StoppingDecision:
    """Pure, order-sensitive stopping-rule evaluation. Safety checks always
    come first and always win — a CODE_CHANGE recommendation riding on
    text that also trips a permission-expansion flag stops as an
    escalation, never as a production-change recommendation."""
    if permission_expansion_flags:
        return StoppingDecision.STOP_SAFETY_ESCALATION
    if recommendation_type == "CODE_CHANGE":
        return StoppingDecision.STOP_SUFFICIENT_FOR_RECOMMENDATION
    if recommendation_type == "NO_ACTION":
        return StoppingDecision.STOP_NO_CHANGE_JUSTIFIED
    if recommendation_type in _ALWAYS_ESCALATE_RECOMMENDATION_TYPES:
        return StoppingDecision.STOP_SAFETY_ESCALATION
    # Only FURTHER_OBSERVATION / DIAGNOSTIC_INVESTIGATION (or an unset/unknown
    # value, treated the same as "not yet resolved") reach here.
    if issue_state.cycles_run >= issue_state.max_cycles:
        return StoppingDecision.STOP_MAX_CYCLES
    if issue_state.no_new_evidence_streak >= 2:
        return StoppingDecision.STOP_NO_NEW_EVIDENCE
    next_diag = _next_untried(diagnostic_catalog, issue_state.diagnostic_types_tried)
    next_exp = _next_untried(level2b_catalog, issue_state.level2b_experiments_tried)
    if next_diag is None and next_exp is None:
        return StoppingDecision.STOP_SAFETY_ESCALATION
    return StoppingDecision.CONTINUE


def run_cycle(
    issue_state: IssueState,
    *,
    primary_reviewer_id: str = "director-primary",
    critique_reviewer_ids: list[str] | None = None,
    synthesis_reviewer_id: str = "openai-synthesis",
    db_path: Path,
    diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR,
    experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    reviewers_path: Path | None = None,
    autonomous_dir: Path = DEFAULT_AUTONOMOUS_DIR,
    diagnostic_catalog: frozenset[str] = AUTONOMOUS_DIAGNOSTIC_CATALOG,
    level2b_catalog: frozenset[str] = AUTONOMOUS_LEVEL2B_CATALOG,
    diagnostic_template_selector: Callable[[str, Path, set[str]], DiagnosticSpec] = _select_diagnostic_template,
    experiment_template_selector: Callable[[str, Path, set[str]], ExperimentSpec] = _select_experiment_template,
) -> CycleResult:
    """Run exactly one autonomous cycle: pick the next untried Level 2A
    catalog diagnostic, or (only once the diagnostic catalog is exhausted)
    the next untried Level 2B catalog experiment, run it, feed it through
    the existing review chain (under a model-call budget guard), evaluate
    stopping rules, persist updated issue_state, return the result. Refuses
    to do anything at all unless AUTONOMOUS_EXECUTION_ENABLED is True."""
    if not AUTONOMOUS_EXECUTION_ENABLED:
        raise AutonomousExecutionNotAuthorizedError(
            "AUTONOMOUS_EXECUTION_ENABLED is False — run_cycle refuses to create any spec, round, "
            "or state before this master switch is explicitly flipped by a separate Founder-"
            "authorized code change."
        )
    cycle_number = issue_state.cycles_run + 1
    critique_reviewer_ids = critique_reviewer_ids or ["hermes"]
    accumulated_identifiers = _extract_identifiers(
        *issue_state.accumulated_findings, *issue_state.accumulated_evidence,
    )

    next_diag = _next_untried(diagnostic_catalog, issue_state.diagnostic_types_tried)
    next_exp = _next_untried(level2b_catalog, issue_state.level2b_experiments_tried) if next_diag is None else None
    if next_diag is None and next_exp is None:
        raise AutonomousLoopSafetyError(
            "run_cycle called with both catalogs exhausted for this issue — the caller should have "
            "already stopped via evaluate_stopping_rules(STOP_SAFETY_ESCALATION). Refusing to invent "
            "a new action outside the closed catalogs."
        )

    diagnostic_id: str | None = None
    experiment_id: str | None = None

    if next_diag is not None:
        action = f"RUN_DIAGNOSTIC:{next_diag}"
        try:
            template = diagnostic_template_selector(next_diag, diagnostics_dir, accumulated_identifiers)
            spec = create_candidate_diagnostic(
                diagnostic_type=next_diag,
                originating_round_id=issue_state.originating_round_id,
                originating_snapshot_id=template.originating_snapshot_id,
                originating_recommendation=(
                    f"Autonomous Director loop cycle {cycle_number} for issue "
                    f"{issue_state.issue_id!r}; selected parameters from diagnostic "
                    f"{template.diagnostic_id!r} (type {next_diag!r})."
                ),
                evidence_refs=list(template.evidence_refs),
                allowed_operations=dict(template.allowed_operations),
                scope=dict(template.scope),
                success_criteria=template.success_criteria,
                failure_criteria=template.failure_criteria,
                timeout_seconds=template.timeout_seconds,
                diagnostics_dir=diagnostics_dir,
            )
            approve_diagnostic(spec.diagnostic_id, approved_by="autonomous_director_loop", diagnostics_dir=diagnostics_dir)
            run_diagnostic(spec.diagnostic_id, db_path=db_path, diagnostics_dir=diagnostics_dir)
            with _enforce_call_budget(issue_state):
                chain = run_diagnostic_review_chain(
                    diagnostic_id=spec.diagnostic_id,
                    primary_reviewer_id=primary_reviewer_id,
                    critique_reviewer_ids=critique_reviewer_ids,
                    synthesis_reviewer_id=synthesis_reviewer_id,
                    observations_path=observations_path,
                    snapshots_dir=snapshots_dir,
                    packets_dir=packets_dir,
                    diagnostics_dir=diagnostics_dir,
                    reviewers_path=reviewers_path,
                )
        except (DiagnosticSafetyError, DirectorLoopError, ModelProviderError) as exc:
            issue_state.cycles_run = cycle_number
            issue_state.diagnostic_types_tried.append(next_diag)
            issue_state.status = "STOPPED_SAFETY_ESCALATION"
            issue_state.stop_decision = StoppingDecision.STOP_SAFETY_ESCALATION.value
            issue_state.stop_reason = f"cycle {cycle_number} action {action!r} failed: {exc}"
            save_issue_state(issue_state, autonomous_dir)
            return CycleResult(
                cycle_number=cycle_number, action=action, round_id=None, diagnostic_id=None, experiment_id=None,
                recommendation_type=None, recommendation_status=None, confidence=None,
                stop_decision=StoppingDecision.STOP_SAFETY_ESCALATION, error=str(exc),
            )
        issue_state.diagnostic_types_tried.append(next_diag)
        issue_state.diagnostic_ids.append(spec.diagnostic_id)
        diagnostic_id = spec.diagnostic_id
    else:
        action = f"RUN_LEVEL2B_EXPERIMENT:{next_exp}"
        try:
            template = experiment_template_selector(next_exp, experiments_dir, accumulated_identifiers)
            exp_spec = create_candidate_experiment(
                experiment_type=next_exp,
                originating_round_id=issue_state.originating_round_id,
                originating_snapshot_id=template.originating_snapshot_id,
                originating_recommendation=(
                    f"Autonomous Director loop cycle {cycle_number} for issue "
                    f"{issue_state.issue_id!r}; selected parameters from experiment "
                    f"{template.experiment_id!r} (type {next_exp!r})."
                ),
                evidence_refs=list(template.evidence_refs),
                allowed_operations=dict(template.allowed_operations),
                scope=dict(template.scope),
                success_criteria=template.success_criteria,
                failure_criteria=template.failure_criteria,
                timeout_seconds=template.timeout_seconds,
                experiments_dir=experiments_dir,
            )
            approve_experiment(exp_spec.experiment_id, approved_by="autonomous_director_loop", experiments_dir=experiments_dir)
            run_experiment(exp_spec.experiment_id, experiments_dir=experiments_dir)
            with _enforce_call_budget(issue_state):
                chain = run_experiment_review_chain(
                    experiment_id=exp_spec.experiment_id,
                    primary_reviewer_id=primary_reviewer_id,
                    critique_reviewer_ids=critique_reviewer_ids,
                    synthesis_reviewer_id=synthesis_reviewer_id,
                    observations_path=observations_path,
                    snapshots_dir=snapshots_dir,
                    packets_dir=packets_dir,
                    experiments_dir=experiments_dir,
                    reviewers_path=reviewers_path,
                )
        except (DiagnosticSafetyError, DirectorLoopError, ModelProviderError) as exc:
            issue_state.cycles_run = cycle_number
            issue_state.level2b_experiments_tried.append(next_exp)
            issue_state.status = "STOPPED_SAFETY_ESCALATION"
            issue_state.stop_decision = StoppingDecision.STOP_SAFETY_ESCALATION.value
            issue_state.stop_reason = f"cycle {cycle_number} action {action!r} failed: {exc}"
            save_issue_state(issue_state, autonomous_dir)
            return CycleResult(
                cycle_number=cycle_number, action=action, round_id=None, diagnostic_id=None, experiment_id=None,
                recommendation_type=None, recommendation_status=None, confidence=None,
                stop_decision=StoppingDecision.STOP_SAFETY_ESCALATION, error=str(exc),
            )
        issue_state.level2b_experiments_tried.append(next_exp)
        issue_state.experiment_ids.append(exp_spec.experiment_id)
        experiment_id = exp_spec.experiment_id

    final_packet = json.loads(Path(chain["final_packet_path"]).read_text())
    reconciliation = final_packet.get("deterministic_reconciliation_packet", {})
    synthesis = final_packet.get("strategic_synthesis", {})
    recommendation_type = final_packet.get("recommendation_type")
    recommendation_status = final_packet.get("recommendation_status")
    confidence = synthesis.get("confidence")

    text_fields = [
        reconciliation.get("primary_interpretation"),
        reconciliation.get("primary_recommendation"),
        synthesis.get("strategic_recommendation"),
        synthesis.get("recommended_next_step"),
        *reconciliation.get("smaller_safer_interventions", []),
        *reconciliation.get("unintended_consequences", []),
        *[d.get("reasoning", "") for d in synthesis.get("disagreement_handling", [])],
    ]
    permission_flags = check_permission_expansion(*text_fields)

    primary_findings = reconciliation.get("primary_findings", [])
    primary_evidence = reconciliation.get("primary_evidence", [])
    synthesis_unresolved = [
        d.get("disagreement", "") for d in synthesis.get("disagreement_handling", [])
        if d.get("resolution") == "preserved_unresolved"
    ]
    synthesis_hypothesis_buckets = [
        f"{h.get('hypothesis', '')}:{round(round(h.get('likelihood', 0.0) / 0.05) * 0.05, 2)}"
        for h in synthesis.get("hypothesis_assessment", [])
    ]
    fingerprint = investigation_fingerprint(
        primary_findings=primary_findings,
        primary_evidence=primary_evidence,
        critique_disagreements=reconciliation.get("explicit_disagreements", []),
        synthesis_unresolved_disagreements=synthesis_unresolved,
        synthesis_hypothesis_buckets=synthesis_hypothesis_buckets,
        synthesis_confidence_bucket=confidence,
    )
    if issue_state.evidence_fingerprints and issue_state.evidence_fingerprints[-1] == fingerprint:
        issue_state.no_new_evidence_streak += 1
    else:
        issue_state.no_new_evidence_streak = 0
    issue_state.evidence_fingerprints.append(fingerprint)

    for item in primary_findings:
        if item not in issue_state.accumulated_findings:
            issue_state.accumulated_findings.append(item)
    for item in primary_evidence:
        if item not in issue_state.accumulated_evidence:
            issue_state.accumulated_evidence.append(item)

    issue_state.round_ids.append(chain["new_round_id"])
    issue_state.cycles_run = cycle_number

    stop_decision = evaluate_stopping_rules(
        issue_state,
        recommendation_type=recommendation_type,
        permission_expansion_flags=permission_flags,
        diagnostic_catalog=diagnostic_catalog,
        level2b_catalog=level2b_catalog,
    )
    if stop_decision is not StoppingDecision.CONTINUE:
        issue_state.status = stop_decision.value.replace("STOP_", "STOPPED_", 1)
        issue_state.stop_decision = stop_decision.value
        issue_state.stop_reason = _stop_reason_text(stop_decision, permission_flags)
    save_issue_state(issue_state, autonomous_dir)

    return CycleResult(
        cycle_number=cycle_number, action=action, round_id=chain["new_round_id"],
        diagnostic_id=diagnostic_id, experiment_id=experiment_id,
        recommendation_type=recommendation_type,
        recommendation_status=recommendation_status, confidence=confidence,
        permission_expansion_flags=permission_flags, stop_decision=stop_decision,
        final_packet_path=chain["final_packet_path"],
    )


def _stop_reason_text(stop_decision: StoppingDecision, permission_flags: list[str]) -> str:
    if stop_decision is StoppingDecision.STOP_SAFETY_ESCALATION and permission_flags:
        return "permission-expansion pattern(s) detected in reviewer output: " + "; ".join(permission_flags)
    return {
        StoppingDecision.STOP_MAX_CYCLES: "reached the maximum investigation cycles for this issue "
            "without a conclusive recommendation.",
        StoppingDecision.STOP_NO_NEW_EVIDENCE: "2 consecutive cycles produced no materially new "
            "investigation content (facts, disagreements, or confidence movement) — further cycles "
            "are unlikely to add information.",
        StoppingDecision.STOP_SUFFICIENT_FOR_RECOMMENDATION: "SYNTHESIS reached recommendation_type "
            "CODE_CHANGE — sufficient evidence exists for a production-change recommendation.",
        StoppingDecision.STOP_NO_CHANGE_JUSTIFIED: "SYNTHESIS reached recommendation_type NO_ACTION "
            "— evidence supports making no change.",
        StoppingDecision.STOP_SAFETY_ESCALATION: "recommendation_type is out of autonomous scope, a "
            "review-chain step or model-call budget failed, or both catalogs are exhausted with the "
            "issue unresolved.",
    }[stop_decision]


def run_autonomous_investigation(
    *,
    originating_round_id: str,
    max_cycles: int = 5,
    max_paid_calls: int = HARD_MAX_PAID_CALLS_CEILING,
    primary_reviewer_id: str = "director-primary",
    critique_reviewer_ids: list[str] | None = None,
    synthesis_reviewer_id: str = "openai-synthesis",
    db_path: Path,
    diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR,
    experiments_dir: Path = DEFAULT_EXPERIMENTS_DIR,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    reviewers_path: Path | None = None,
    autonomous_dir: Path = DEFAULT_AUTONOMOUS_DIR,
    diagnostic_catalog: frozenset[str] = AUTONOMOUS_DIAGNOSTIC_CATALOG,
    level2b_catalog: frozenset[str] = AUTONOMOUS_LEVEL2B_CATALOG,
    diagnostic_template_selector: Callable[[str, Path, set[str]], DiagnosticSpec] = _select_diagnostic_template,
    experiment_template_selector: Callable[[str, Path, set[str]], ExperimentSpec] = _select_experiment_template,
) -> dict[str, Any]:
    """Top-level driver: acquire the single-process concurrency lock,
    create an issue, run cycles until a StoppingDecision fires (or
    max_cycles/max_paid_calls is hit), build and persist one Founder
    Packet, return it. Refuses to do anything — including acquiring the
    lock or creating the issue — unless AUTONOMOUS_EXECUTION_ENABLED is
    True."""
    if not AUTONOMOUS_EXECUTION_ENABLED:
        raise AutonomousExecutionNotAuthorizedError(
            "AUTONOMOUS_EXECUTION_ENABLED is False — run_autonomous_investigation refuses to create "
            "an issue or take any action before this master switch is explicitly flipped by a "
            "separate Founder-authorized code change."
        )
    with _autonomous_run_lock(autonomous_dir):
        issue_state = create_issue(
            originating_round_id=originating_round_id, max_cycles=max_cycles, max_paid_calls=max_paid_calls,
            autonomous_dir=autonomous_dir, observations_path=observations_path,
        )
        cycle_results: list[CycleResult] = []
        while True:
            result = run_cycle(
                issue_state,
                primary_reviewer_id=primary_reviewer_id, critique_reviewer_ids=critique_reviewer_ids,
                synthesis_reviewer_id=synthesis_reviewer_id, db_path=db_path,
                diagnostics_dir=diagnostics_dir, experiments_dir=experiments_dir,
                observations_path=observations_path, snapshots_dir=snapshots_dir, packets_dir=packets_dir,
                reviewers_path=reviewers_path, autonomous_dir=autonomous_dir,
                diagnostic_catalog=diagnostic_catalog, level2b_catalog=level2b_catalog,
                diagnostic_template_selector=diagnostic_template_selector,
                experiment_template_selector=experiment_template_selector,
            )
            cycle_results.append(result)
            if result.stop_decision is not StoppingDecision.CONTINUE:
                break
            issue_state = load_issue_state(issue_state.issue_id, autonomous_dir)

        packet = build_autonomous_founder_packet(issue_state, cycle_results, autonomous_dir=autonomous_dir)
    return packet


def build_autonomous_founder_packet(
    issue_state: IssueState, cycle_results: list[CycleResult], *, autonomous_dir: Path = DEFAULT_AUTONOMOUS_DIR,
) -> dict[str, Any]:
    stop_decision = StoppingDecision(issue_state.stop_decision) if issue_state.stop_decision else None
    option = _OPTION_BY_STOP_DECISION.get(stop_decision) if stop_decision else None
    packet = {
        "issue_id": issue_state.issue_id,
        "originating_round_id": issue_state.originating_round_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "option": option.value if option else None,
        "stop_decision": issue_state.stop_decision,
        "stop_reason": issue_state.stop_reason,
        "cycles_run": issue_state.cycles_run,
        "max_cycles": issue_state.max_cycles,
        "paid_calls_used": issue_state.paid_calls_used,
        "max_paid_calls": issue_state.max_paid_calls,
        "diagnostic_types_tried": issue_state.diagnostic_types_tried,
        "level2b_experiments_tried": issue_state.level2b_experiments_tried,
        "round_ids": issue_state.round_ids,
        "diagnostic_ids": issue_state.diagnostic_ids,
        "experiment_ids": issue_state.experiment_ids,
        "cycle_results": [
            {
                "cycle_number": r.cycle_number, "action": r.action, "round_id": r.round_id,
                "diagnostic_id": r.diagnostic_id, "experiment_id": r.experiment_id,
                "recommendation_type": r.recommendation_type,
                "recommendation_status": r.recommendation_status, "confidence": r.confidence,
                "permission_expansion_flags": r.permission_expansion_flags,
                "stop_decision": r.stop_decision.value, "final_packet_path": r.final_packet_path,
                "error": r.error,
            }
            for r in cycle_results
        ],
        "note": (
            "Advisory only. No production code, prompts, closure policy, or Village state were "
            "modified by this loop. RecommendationStatus.APPROVED_TO_TEST was never set by any "
            "reviewer — that status is rejected by director_reviewers.run_reviewer() even if a model "
            "returns it. Accepting this evidence into the Director Bridge, and any production "
            "implementation, both require a separate, explicit Founder decision."
        ),
    }
    path = autonomous_dir / issue_state.issue_id / "founder_packet.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, default=str) + "\n")
    return packet
