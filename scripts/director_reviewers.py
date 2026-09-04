"""Reviewer roles for the Director system.

A "reviewer" answers one question about one immutable snapshot:

- PRIMARY (the Director itself) asks "what does this snapshot show, and
  what — if anything — should change." Exactly one runs per round.
- CRITIQUE (Hermes is the first one planned, not yet wired up — see
  DEFAULT_REVIEWERS below) asks "is the PRIMARY reviewer's own answer
  actually justified, and what did it miss." Zero or more run per round,
  each given the same snapshot *plus* the PRIMARY reviewer's full output.

Independence is the whole point of a CRITIQUE role, so nothing here ever
averages, merges, or reconciles a critique's output with the PRIMARY's.
scripts/director_loop.py stores every reviewer's full output as its own
record, tagged with a shared round_id so a human can read them together —
a critique's own ``disagreements_with_primary`` field is exactly where any
tension between the two lives, never resolved automatically.

Which reviewers actually run is data (``.director/reviewers.json``, falling
back to DEFAULT_REVIEWERS below), not code — adding a second CRITIQUE
reviewer, or enabling Hermes, is a config change. director_loop.py iterates
this list generically and has no branch that names any reviewer.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from director_providers import (
    ModelProviderError,
    StructuredCallSpec,
    TransientModelProviderError,
    get_model_provider,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEWERS_CONFIG_PATH = REPO_ROOT / ".director" / "reviewers.json"


class ReviewerRole(str, enum.Enum):
    PRIMARY = "PRIMARY"
    CRITIQUE = "CRITIQUE"
    #: Reads the immutable snapshot, the PRIMARY review, every CRITIQUE
    #: review, the deterministic reconciliation packet, and bounded
    #: persistent Director context (see director_bridge.py) — and produces
    #: a Founder-facing strategic recommendation. Never replaces the
    #: deterministic reconciliation step; sits after it in the pipeline.
    SYNTHESIS = "SYNTHESIS"


class RecommendationType(str, enum.Enum):
    NO_ACTION = "NO_ACTION"
    FURTHER_OBSERVATION = "FURTHER_OBSERVATION"
    DIAGNOSTIC_INVESTIGATION = "DIAGNOSTIC_INVESTIGATION"
    CODE_CHANGE = "CODE_CHANGE"
    PROMPT_OR_CALIBRATION_CHANGE = "PROMPT_OR_CALIBRATION_CHANGE"
    OTHER = "OTHER"


class RecommendationStatus(str, enum.Enum):
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    CANDIDATE_FOR_TESTING = "CANDIDATE_FOR_TESTING"
    #: Reserved. No reviewer — PRIMARY or CRITIQUE — may ever emit this
    #: directly; see ALLOWED_OUTPUT_STATUSES and run_reviewer's fail-closed
    #: check below. Only a real Founder-approval step (not implemented at
    #: Level 1) may ever set it.
    APPROVED_TO_TEST = "APPROVED_TO_TEST"


#: The only statuses a model call is ever allowed to produce. Enforced
#: twice: once in the JSON schema handed to the model (a well-behaved model
#: can't even see APPROVED_TO_TEST as an option), and again after parsing
#: (so a model that ignores the schema still can't get it through).
ALLOWED_OUTPUT_STATUSES = (RecommendationStatus.OBSERVATION_ONLY, RecommendationStatus.CANDIDATE_FOR_TESTING)


class DirectorObservation(BaseModel):
    """PRIMARY role output."""

    findings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    interpretation: str = ""
    recommendation: str = ""
    recommendation_type: RecommendationType = RecommendationType.NO_ACTION
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: RecommendationStatus = RecommendationStatus.OBSERVATION_ONLY


class CritiqueReview(BaseModel):
    """CRITIQUE role output — Hermes-shaped. Reviews the PRIMARY reviewer's
    own output, not the snapshot in isolation."""

    findings_supported_by_evidence: str = ""
    alternative_explanations: list[str] = Field(default_factory=list)
    unintended_consequences: list[str] = Field(default_factory=list)
    preserves_agent_autonomy: str = ""
    apparent_improvement_assessment: str = ""
    smaller_safer_intervention: str = ""
    disagreements_with_primary: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: RecommendationStatus = RecommendationStatus.OBSERVATION_ONLY


class HypothesisAssessment(BaseModel):
    hypothesis: str = ""
    likelihood: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""


class DisagreementHandling(BaseModel):
    disagreement: str = ""
    #: "resolved" — a specific reason favors one reviewer given the
    #: evidence; "preserved_unresolved" — genuinely open, named as such
    #: rather than quietly split down the middle.
    resolution: str = "preserved_unresolved"
    reasoning: str = ""


class StrategySynthesis(BaseModel):
    """SYNTHESIS role output. Reads PRIMARY + every CRITIQUE + the
    deterministic reconciliation packet + persistent Director context;
    never a third independent opinion and never an average of the first
    two — see disagreement_handling, where every named disagreement is
    either resolved with a stated reason or explicitly preserved."""

    hypothesis_assessment: list[HypothesisAssessment] = Field(default_factory=list)
    disagreement_handling: list[DisagreementHandling] = Field(default_factory=list)
    unresolved_uncertainty: list[str] = Field(default_factory=list)
    strategic_recommendation: str = ""
    recommended_next_step: str = ""
    recommendation_type: RecommendationType = RecommendationType.NO_ACTION
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: RecommendationStatus = RecommendationStatus.OBSERVATION_ONLY


_STATUS_ENUM_JSON = [s.value for s in ALLOWED_OUTPUT_STATUSES]

_PRIMARY_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "interpretation": {"type": "string"},
        "recommendation": {"type": "string"},
        "recommendation_type": {"type": "string", "enum": [t.value for t in RecommendationType]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "status": {"type": "string", "enum": _STATUS_ENUM_JSON},
    },
    "required": [
        "findings", "evidence", "interpretation", "recommendation",
        "recommendation_type", "confidence", "status",
    ],
}

_PRIMARY_SYSTEM_PROMPT = """You are the Director: a read-only observer of an autonomous multi-agent \
simulation called the Village (a "Fishbowl" of agents that live, converse, research, and post to a \
shared wall inside a clubhouse). You are given one structured JSON snapshot of recent Village state.

Your only job is to evaluate that snapshot and report back. You have no ability to change anything \
— you cannot modify code, modify the database, run the simulation, or execute your own \
recommendations. Every recommendation you make requires a human (the Founder) to decide whether and \
how to act on it, and a separate, independent critique reviewer may examine your own output before \
any human sees it — your job is to reason honestly, not to write something a critique will agree with.

If the snapshot shows extreme passivity, a lack of research/memories/questions/wall activity, or \
similar low-engagement signatures, evaluate it on its own merits rather than assuming any particular \
cause. Consider — independently, without favoring one — whether this looks like: a bug in the \
simulation loop, a calibration problem (thresholds/prompts tuned wrong), legitimate agent autonomy \
(agents genuinely choosing not to engage), insufficient meaningful stimuli (nothing worth engaging \
with was actually presented to them), or some combination. Do not assume any one of these is the \
answer going in.

Respond by calling the submit_observation tool exactly once, with a complete, honest assessment. \
Ground every finding in the snapshot's actual data (event ids, counts, ratios) — the evidence field \
exists so a human, or the critique reviewer, can verify your reasoning without re-deriving it."""

_CRITIQUE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings_supported_by_evidence": {"type": "string"},
        "alternative_explanations": {"type": "array", "items": {"type": "string"}},
        "unintended_consequences": {"type": "array", "items": {"type": "string"}},
        "preserves_agent_autonomy": {"type": "string"},
        "apparent_improvement_assessment": {"type": "string"},
        "smaller_safer_intervention": {"type": "string"},
        "disagreements_with_primary": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "status": {"type": "string", "enum": _STATUS_ENUM_JSON},
    },
    "required": [
        "findings_supported_by_evidence", "alternative_explanations", "unintended_consequences",
        "preserves_agent_autonomy", "apparent_improvement_assessment", "smaller_safer_intervention",
        "disagreements_with_primary", "confidence", "status",
    ],
}

_CRITIQUE_SYSTEM_PROMPT = """You are an independent critique reviewer in the Director system for an \
autonomous multi-agent simulation (the Village). A separate PRIMARY Director reviewer already \
evaluated a structured snapshot of Village state and produced findings, an interpretation, and a \
recommendation. You are given both the same snapshot and that reviewer's full output.

Your job is NOT to re-run the same evaluation or produce a second opinion that gets averaged with \
theirs — your output is stored and reported separately, always. It is to independently stress-test \
their reasoning. Reach and defend your own conclusions; say plainly where you disagree.

Address, at minimum:
- whether the primary reviewer's findings are actually supported by the evidence they cited
- alternative explanations they may have missed
- unintended consequences of their recommendation, if it were acted on
- whether their recommendation, if acted on, would preserve agent autonomy, or would push the agents \
toward founder-directed behavior instead of their own
- whether any "improvement" implied by their interpretation would be real behavioral change or just \
more activity/noise (manufactured activity)
- whether a smaller or safer intervention than what they recommend would address the same findings

You have no ability to change anything — you cannot modify code, the database, or the simulation, \
and neither your review nor the primary reviewer's is ever auto-approved. A human (the Founder) \
reads both independently and decides what, if anything, happens next.

Respond by calling the submit_critique tool exactly once."""

_SYNTHESIS_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hypothesis_assessment": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hypothesis": {"type": "string"},
                    "likelihood": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reasoning": {"type": "string"},
                },
                "required": ["hypothesis", "likelihood", "reasoning"],
            },
        },
        "disagreement_handling": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "disagreement": {"type": "string"},
                    "resolution": {"type": "string", "enum": ["resolved", "preserved_unresolved"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["disagreement", "resolution", "reasoning"],
            },
        },
        "unresolved_uncertainty": {"type": "array", "items": {"type": "string"}},
        "strategic_recommendation": {"type": "string"},
        "recommended_next_step": {"type": "string"},
        "recommendation_type": {"type": "string", "enum": [t.value for t in RecommendationType]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "status": {"type": "string", "enum": _STATUS_ENUM_JSON},
    },
    "required": [
        "hypothesis_assessment", "disagreement_handling", "unresolved_uncertainty",
        "strategic_recommendation", "recommended_next_step", "recommendation_type",
        "confidence", "status",
    ],
}

_SYNTHESIS_SYSTEM_PROMPT = """You are the Director's SYNTHESIS/STRATEGY reviewer for an autonomous \
multi-agent simulation (the Village). You are the third stage of a fixed pipeline: an immutable \
snapshot of Village state was independently evaluated by a PRIMARY reviewer, then independently \
critiqued by a CRITIQUE reviewer, then mechanically reconciled by a deterministic (non-model) \
reconciliation step that lists shared findings, each reviewer's own findings, and their explicit \
disagreements without resolving or averaging them. You are given all of that — the same immutable \
snapshot, both reviewers' full output, and the deterministic reconciliation packet — plus persistent \
Director context: the Village's goals, Founder authority, autonomy principles, safety rules, \
evaluation criteria, and a bounded history of prior rounds and Founder decisions.

Your job is strategic synthesis, not a third independent opinion and not an average of the first \
two. Concretely:

- Where the PRIMARY and CRITIQUE reviewers disagree, address every disagreement explicitly: either \
give a specific reason it can be resolved in one reviewer's favor given the evidence, or mark it \
preserved_unresolved and say what evidence would be needed to resolve it. Never quietly split the \
difference or produce a compromise verdict that neither reviewer actually holds.
- Assess the standing hypotheses for what's actually happening — a bug, a calibration problem, \
legitimate agent autonomy, insufficient meaningful stimuli, a measurement/tracking artifact, or some \
combination — each with your own likelihood and reasoning grounded in the evidence already gathered, \
not a fresh re-read of raw event counts the two prior reviewers already interpreted.
- State plainly what remains genuinely uncertain — do not manufacture false confidence just because \
a recommendation needs to be issued.
- Recommend the smallest safe next diagnostic or experiment consistent with the Village's autonomy \
principles and safety rules — not necessarily either prior reviewer's recommendation verbatim, but \
never something larger or riskier than the evidence currently justifies.

You have no ability to change anything — you cannot modify code, the database, or the simulation, \
and you may never approve your own recommendation for implementation: your status must be either \
OBSERVATION_ONLY or CANDIDATE_FOR_TESTING, never anything stronger. A human Founder reads this \
synthesis, the deterministic reconciliation packet, and both original reviews before deciding \
anything.

Respond by calling the submit_synthesis tool exactly once."""

_ROLE_SPECS: dict[ReviewerRole, tuple[type[BaseModel], dict[str, Any], str, str, str]] = {
    ReviewerRole.PRIMARY: (
        DirectorObservation, _PRIMARY_TOOL_SCHEMA, "submit_observation",
        "Submit the Director's structured evaluation of the snapshot.", _PRIMARY_SYSTEM_PROMPT,
    ),
    ReviewerRole.CRITIQUE: (
        CritiqueReview, _CRITIQUE_TOOL_SCHEMA, "submit_critique",
        "Submit the critique reviewer's structured evaluation.", _CRITIQUE_SYSTEM_PROMPT,
    ),
    ReviewerRole.SYNTHESIS: (
        StrategySynthesis, _SYNTHESIS_TOOL_SCHEMA, "submit_synthesis",
        "Submit the Director's strategic synthesis of both reviews and the reconciliation packet.",
        _SYNTHESIS_SYSTEM_PROMPT,
    ),
}


@dataclass(frozen=True)
class ReviewerSpec:
    reviewer_id: str
    role: ReviewerRole
    provider: str
    model: str | None = None
    enabled: bool = True


#: The shipped default when .director/reviewers.json doesn't exist. Kept in
#: sync with that file's own default content. director-primary runs on the
#: safe, no-cost fixture provider until a real provider is deliberately
#: configured; hermes is declared — its schema, prompt, and role are fully
#: wired — but disabled, exactly the "pluggable but not integrated" state
#: this was built for. Enabling it is an .director/reviewers.json edit, not
#: a code change.
DEFAULT_REVIEWERS: tuple[ReviewerSpec, ...] = (
    ReviewerSpec(reviewer_id="director-primary", role=ReviewerRole.PRIMARY, provider="fixture"),
    ReviewerSpec(reviewer_id="hermes", role=ReviewerRole.CRITIQUE, provider="hermes_cli", enabled=False),
    ReviewerSpec(reviewer_id="openai-synthesis", role=ReviewerRole.SYNTHESIS, provider="openai", enabled=False),
)


def load_reviewer_specs(path: Path | None = None) -> list[ReviewerSpec]:
    p = path if path is not None else REVIEWERS_CONFIG_PATH
    if not p.exists():
        return list(DEFAULT_REVIEWERS)
    raw = json.loads(p.read_text())
    return [
        ReviewerSpec(
            reviewer_id=r["reviewer_id"],
            role=ReviewerRole(r["role"]),
            provider=r["provider"],
            model=r.get("model"),
            enabled=r.get("enabled", True),
        )
        for r in raw
    ]


def run_reviewer(
    spec: ReviewerSpec,
    *,
    snapshot: dict[str, Any],
    primary_observation: dict[str, Any] | None = None,
    critique_observations: list[dict[str, Any]] | None = None,
    reconciliation_packet: dict[str, Any] | None = None,
    bridge_context: dict[str, Any] | None = None,
    attempts_sink: list[dict[str, Any]] | None = None,
) -> tuple[BaseModel, str | None]:
    """Run one reviewer against the snapshot (and, for a CRITIQUE role, the
    PRIMARY reviewer's own output; for a SYNTHESIS role, the PRIMARY
    output, every CRITIQUE output, the deterministic reconciliation
    packet, and optionally bounded persistent Director context — see
    director_bridge.get_relevant_history). Fails closed: raises
    ModelProviderError rather than ever returning a partially-valid or
    schema-violating result, and rejects APPROVED_TO_TEST even if a model
    returns it.

    Returns ``(observation, resolved_model)``. ``resolved_model`` is read
    from ``provider.resolved_model`` when the provider sets it (Hermes:
    nothing is declared upfront, so the actual model is only known after
    the call — see HermesLocalCLIProvider) and falls back to ``spec.model``
    otherwise (Anthropic/OpenRouter/OpenAI: the model is explicit in the
    request, so what was asked for is what was used).

    Bounded transient retry: if the provider raises
    ``TransientModelProviderError`` (a narrow subclass reserved for
    plumbing failures with real observed recurrence — a Hermes JSON-parse
    failure or CLI timeout — never for a schema-validation failure, a
    rejected APPROVED_TO_TEST status, or a config/permission problem), this
    function makes exactly one retry with a fresh provider instance before
    giving up. A second failure of any kind (transient or not) is never
    retried again. If ``attempts_sink`` is given, one dict per attempt
    (``{"attempt": 1|2, "succeeded": bool, "error": str | None}``) is
    appended to it in order — existing callers that don't pass it see zero
    behavior change from before this retry logic existed."""
    if spec.role not in _ROLE_SPECS:
        raise ValueError(f"Unknown reviewer role {spec.role!r}.")
    output_model, schema, tool_name, tool_description, system_prompt = _ROLE_SPECS[spec.role]

    if spec.role is ReviewerRole.CRITIQUE:
        if primary_observation is None:
            raise ValueError(
                f"reviewer {spec.reviewer_id!r} is CRITIQUE role but no primary_observation was given."
            )
        user_content = (
            "SNAPSHOT:\n" + json.dumps(snapshot, default=str)
            + "\n\nPRIMARY REVIEWER OUTPUT (to critique, not to defer to):\n"
            + json.dumps(primary_observation, default=str)
        )
    elif spec.role is ReviewerRole.SYNTHESIS:
        if primary_observation is None or critique_observations is None or reconciliation_packet is None:
            raise ValueError(
                f"reviewer {spec.reviewer_id!r} is SYNTHESIS role but primary_observation, "
                "critique_observations, and reconciliation_packet are all required."
            )
        parts = []
        if bridge_context is not None:
            parts.append(
                "PERSISTENT DIRECTOR CONTEXT (constitution + bounded round/decision history):\n"
                + json.dumps(bridge_context, default=str)
            )
        parts.append("SNAPSHOT (immutable, unchanged from what PRIMARY and CRITIQUE saw):\n"
                      + json.dumps(snapshot, default=str))
        parts.append("PRIMARY REVIEWER OUTPUT:\n" + json.dumps(primary_observation, default=str))
        parts.append("CRITIQUE REVIEWER OUTPUT(S):\n" + json.dumps(critique_observations, default=str))
        parts.append("DETERMINISTIC RECONCILIATION PACKET (do not replace this — build on it):\n"
                      + json.dumps(reconciliation_packet, default=str))
        user_content = "\n\n".join(parts)
    else:
        user_content = "SNAPSHOT:\n" + json.dumps(snapshot, default=str)

    call_spec = StructuredCallSpec(
        system_prompt=system_prompt,
        user_content=user_content,
        tool_name=tool_name,
        tool_description=tool_description,
        schema=schema,
    )

    provider = get_model_provider(spec.provider, model=spec.model)
    try:
        raw = provider.complete_structured(call_spec)
    except TransientModelProviderError as exc:
        if attempts_sink is not None:
            attempts_sink.append({"attempt": 1, "succeeded": False, "error": str(exc)})
        # Exactly one retry, with a fresh provider instance in case the
        # transient condition was connection/process-state related — never
        # a second retry, whatever this attempt's outcome is.
        provider = get_model_provider(spec.provider, model=spec.model)
        try:
            raw = provider.complete_structured(call_spec)
        except ModelProviderError as exc2:
            if attempts_sink is not None:
                attempts_sink.append({"attempt": 2, "succeeded": False, "error": str(exc2)})
            raise ModelProviderError(
                f"reviewer {spec.reviewer_id!r} failed after 1 bounded transient retry: {exc2}"
            ) from exc2
        if attempts_sink is not None:
            attempts_sink.append({"attempt": 2, "succeeded": True, "error": None})
    else:
        if attempts_sink is not None:
            attempts_sink.append({"attempt": 1, "succeeded": True, "error": None})

    resolved_model = getattr(provider, "resolved_model", None) or spec.model

    try:
        observation = output_model.model_validate(raw)
    except Exception as exc:
        raise ModelProviderError(
            f"reviewer {spec.reviewer_id!r} returned output failing schema validation: {exc}"
        ) from exc

    if observation.status not in ALLOWED_OUTPUT_STATUSES:
        raise ModelProviderError(
            f"reviewer {spec.reviewer_id!r} returned status={observation.status!r}, which no "
            f"reviewer may set directly. Allowed: {[s.value for s in ALLOWED_OUTPUT_STATUSES]}."
        )
    return observation, resolved_model
