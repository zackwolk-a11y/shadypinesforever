#!/usr/bin/env python3
"""Director synthesis layer: turns one round's already-stored reviewer
records into a Founder Packet.

Reads only what's already on disk — the PRIMARY (Gemini) and CRITIQUE
(Hermes) records for a given round_id in .director/observations.jsonl.
Never calls a model, never regenerates a snapshot, never reruns a
reviewer, never touches the Village DB.

This is deliberately not a generic NLP diff. Cross-referencing which
claims two reviewers independently confirmed, where they actually
disagree, and what the smallest safe next step is requires reading both
reviews, not string-matching them — see _synthesize_round_b433606f27d04e8a
below, whose synthesis content was authored by reading the two specific
stored reviews it operates on. A future round's synthesis needs the same
direct reading, by a human or by Claude, not a rerun of this function
against different text. What IS generic and reusable here is the
mechanism: loading a round's records, the FounderPacket shape, persisting
it outside the Village DB, and rendering a Founder-facing summary.

Output lives at .director/packets/{round_id}.json — .director/, like the
rest of the Director's own state, is never the Village's SQLite database.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from director_reviewers import RecommendationStatus, RecommendationType, ReviewerRole  # noqa: E402
from director_bridge import rebuild_rounds_history  # noqa: E402

DIRECTOR_DIR = REPO_ROOT / ".director"
DEFAULT_OBSERVATIONS_PATH = DIRECTOR_DIR / "observations.jsonl"
DEFAULT_PACKETS_DIR = DIRECTOR_DIR / "packets"


class SynthesisError(RuntimeError):
    """The packet could not be built from what's on disk."""


class ReviewerIdentity(BaseModel):
    reviewer_id: str
    role: str
    provider: str
    model: str | None
    confidence: float
    status: str


class CompetingExplanation(BaseModel):
    source: str
    explanation: str


class FounderPacket(BaseModel):
    """Level 1 synthesis output. Disagreement is a first-class field here,
    never collapsed into one blended verdict — confidence_by_reviewer keeps
    both numbers, explicit_disagreements keeps Hermes' own words, and
    nothing in this shape has room for an averaged score."""

    round_id: str
    snapshot_id: str
    snapshot_version: int
    generated_at: str
    reviewers: list[ReviewerIdentity]

    shared_factual_findings: list[str] = Field(default_factory=list)
    gemini_only_findings: list[str] = Field(default_factory=list)
    hermes_only_findings: list[str] = Field(default_factory=list)
    explicit_disagreements: list[str] = Field(default_factory=list)
    competing_explanations: list[CompetingExplanation] = Field(default_factory=list)
    evidence_references: dict[str, list[str]] = Field(default_factory=dict)
    confidence_by_reviewer: dict[str, float] = Field(default_factory=dict)
    risks_of_acting_too_early: list[str] = Field(default_factory=list)
    smallest_safe_next_diagnostic_step: str = ""

    recommendation_type: RecommendationType
    recommendation_status: RecommendationStatus
    founder_approval_required: bool

    synthesis_note: str = ""


def load_round_records(round_id: str, observations_path: Path = DEFAULT_OBSERVATIONS_PATH) -> dict[str, Any]:
    if not observations_path.exists():
        raise SynthesisError(f"no observations file at {observations_path}.")
    primary = None
    critiques = []
    with observations_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("round_id") != round_id or "output" not in rec:
                continue
            if rec["reviewer_role"] == ReviewerRole.PRIMARY.value:
                primary = rec
            elif rec["reviewer_role"] == ReviewerRole.CRITIQUE.value:
                critiques.append(rec)
    if primary is None:
        raise SynthesisError(f"no successful PRIMARY record found for round_id={round_id!r}.")
    if not critiques:
        raise SynthesisError(f"no successful CRITIQUE record found for round_id={round_id!r}.")
    return {"primary": primary, "critiques": critiques}


def build_generic_reconciliation_packet(round_id: str, records: dict[str, Any]) -> dict[str, Any]:
    """A genuinely mechanical, reusable reconciliation — unlike
    ``_synthesize_round_b433606f27d04e8a`` below (hand-authored prose for
    one specific round), this derives every field directly from structure
    CritiqueReview already provides (``disagreements_with_primary``,
    ``alternative_explanations``, ``unintended_consequences`` are already
    itemized lists — no NLP dedup or cross-referencing judgment is needed
    to "preserve disagreement rather than averaging it away": Hermes'
    disagreements are just carried through verbatim, tagged by reviewer,
    never blended with Gemini's). This is what Level 2A's automated
    diagnostic-driven rounds use, since there is no human/Claude available
    to hand-author prose for a round that just happened automatically."""
    primary = records["primary"]
    critiques = records["critiques"]
    primary_out = primary["output"]

    explicit_disagreements = []
    alternative_explanations = []
    unintended_consequences = []
    critique_findings_assessment = []
    smaller_safer_interventions = []
    confidence_by_reviewer = {f"{primary['reviewer_id']} (PRIMARY)": primary_out["confidence"]}
    for c in critiques:
        out = c["output"]
        tag = c["reviewer_id"]
        explicit_disagreements += [f"[{tag}] {d}" for d in out.get("disagreements_with_primary", [])]
        alternative_explanations += [f"[{tag}] {e}" for e in out.get("alternative_explanations", [])]
        unintended_consequences += [f"[{tag}] {u}" for u in out.get("unintended_consequences", [])]
        if out.get("findings_supported_by_evidence"):
            critique_findings_assessment.append(f"[{tag}] {out['findings_supported_by_evidence']}")
        if out.get("smaller_safer_intervention"):
            smaller_safer_interventions.append(f"[{tag}] {out['smaller_safer_intervention']}")
        confidence_by_reviewer[f"{tag} (CRITIQUE)"] = out["confidence"]

    return {
        "round_id": round_id,
        "reconciliation_method": "generic_mechanical",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_findings": primary_out.get("findings", []),
        "primary_evidence": primary_out.get("evidence", []),
        "primary_interpretation": primary_out.get("interpretation", ""),
        "primary_recommendation": primary_out.get("recommendation", ""),
        "critique_findings_assessment": critique_findings_assessment,
        "critique_alternative_explanations": alternative_explanations,
        "explicit_disagreements": explicit_disagreements,
        "unintended_consequences": unintended_consequences,
        "smaller_safer_interventions": smaller_safer_interventions,
        "confidence_by_reviewer": confidence_by_reviewer,
        "recommendation_type": primary_out.get("recommendation_type", "OTHER"),
        "recommendation_status": primary_out.get("status", "OBSERVATION_ONLY"),
        "founder_approval_required": primary_out.get("status") == "CANDIDATE_FOR_TESTING",
    }


def _synthesize_round_b433606f27d04e8a(primary: dict[str, Any], critique: dict[str, Any]) -> dict[str, Any]:
    """Synthesis content for round_b433606f27d04e8a specifically, authored
    by reading the full stored output of both director-primary (Gemini)
    and hermes (Hermes CRITIQUE) — see the module docstring for why this
    isn't a generic algorithm. Every item below traces to a specific
    sentence in one or both of those two records; nothing here is new
    evidence, a third opinion, or an average of the two."""
    return {
        "shared_factual_findings": [
            "Passive action rate is 94.6% (193 of 204 actions) — Hermes independently confirmed "
            "this is 'accurately calculated from the action counts.'",
            "Three conversations ended immediately with reason 'the room went quiet' and 0 turns, "
            "at events 8, 113, 218 — both reviewers cite the identical three event ids.",
            "Three INVALID_AGENT_DECISION events occurred (missing target_agent_id at 131, no open "
            "conversation to join at 187, missing content at 220) — both reviewers cite identical "
            "event ids and reasons; Hermes confirms these are 'correctly identified.'",
        ],
        "gemini_only_findings": [
            "Framing of the passive-action pattern as the simulation being 'stuck in a loop' — "
            "Hermes does not dispute the count but reframes the same numbers as possibly normal "
            "early-stage behavior rather than a 'loop.'",
            "The composite interpretation that these three facts together show 'a fundamental "
            "breakdown in agent autonomy regarding social engagement' — Hermes explicitly "
            "characterizes this specific interpretive leap as unsupported by the evidence shown.",
        ],
        "hermes_only_findings": [
            "Public dialogue and SEND_MESSAGE actions did occur (event 68: Lucid speaks, event "
            "159: Roxy asks a question; SEND_MESSAGE at events 161, 163, 165, 167, 238, 240, 242, "
            "244) — none of these events appear anywhere in Gemini's evidence list.",
            "recent_conversation_messages is empty despite that visible dialogue — a specific "
            "data-inconsistency Gemini's record never mentions.",
            "Three consecutive daily reports (Days 1-3, events 105, 210, 315) recorded "
            "had_meaningful_activity: true — in direct tension with the 'fundamental breakdown' "
            "framing, and absent from Gemini's record.",
            "The simulation clock advanced all 4 days in roughly 5 minutes of wall-clock time "
            "(07:18-08:24) — a pacing fact Gemini's record does not mention.",
            "The invalid-decision rate is 2.1% of total agent actions (3 of 141) — Hermes computes "
            "and contextualizes this ratio; Gemini reports only the raw count.",
        ],
        "explicit_disagreements": [
            "Severity/framing: Gemini calls it 'a fundamental breakdown in agent autonomy'; Hermes "
            "calls that claim unsupported at this strength, given day 4 of a fresh simulation, a "
            "2.1% error rate, and three daily reports asserting meaningful activity.",
            "Dysfunction vs. artifact: Gemini treats the high passive rate as evidence of "
            "dysfunction; Hermes treats it as potentially normal early-stage behavior and/or a "
            "turn-tracking measurement artifact, and says calling it a problem before ruling out "
            "the measurement hypothesis is premature.",
            "Evidence completeness: Hermes states Gemini's evidence review has 'a significant gap' "
            "— it omits the empty-conversation-messages-despite-visible-dialogue inconsistency and "
            "the Optimisto/Roxy SEND_MESSAGE exchange entirely.",
            "Confidence calibration: Hermes states Gemini's 0.90 confidence 'is too high given that "
            "a key alternative explanation (conversation turn tracking bug) has not been ruled out "
            "and the daily reports contradict the breakdown interpretation.'",
        ],
        "competing_explanations": [
            {
                "source": "director-primary (Gemini)",
                "explanation": "Agent decision-making logic and/or prompt calibration for "
                "conversation initiation is broken — a genuine behavioral/prompt problem.",
            },
            {
                "source": "hermes (Hermes CRITIQUE) — alternative 1",
                "explanation": "Normal early-stage social settling-in behavior for a fresh "
                "simulation, not dysfunction.",
            },
            {
                "source": "hermes (Hermes CRITIQUE) — alternative 2, flagged as the leading candidate",
                "explanation": "A conversation-turn/message-recording bug: real dialogue and "
                "SEND_MESSAGE actions are happening but not being counted into conversation turns "
                "— a measurement problem, not a behavior problem.",
            },
            {
                "source": "hermes (Hermes CRITIQUE) — alternative 3",
                "explanation": "Compressed simulation-clock pacing (4 days in ~5 minutes of "
                "wall-clock time) leaves too little elapsed simulated time for social dynamics to "
                "develop, inflating OBSERVE counts as a pacing artifact rather than agent choice.",
            },
            {
                "source": "hermes (Hermes CRITIQUE) — alternative 4",
                "explanation": "The invalid-decision events (2.1% of actions) are isolated, "
                "specific errors, not a systemic failure.",
            },
        ],
        "evidence_references": {
            "passive_action_rate": ["agent_actions.passive_action_rate = 0.946078431372549 "
                                     "(193/204 actions)"],
            "conversation_endings": ["events 8, 113, 218 — CONVERSATION_ENDED, reason='the room "
                                      "went quiet', turns=0"],
            "invalid_decisions": ["event 131: START_CONVERSATION requires a target_agent_id",
                                   "event 187: no open conversation to join",
                                   "event 220: START_CONVERSATION requires content"],
            "unrecorded_dialogue": ["event 68: Lucid speaks (public dialogue)",
                                     "event 159: Roxy asks a question",
                                     "events 161,163,165,167,238,240,242,244: SEND_MESSAGE",
                                     "recent_conversation_messages: [] (empty, despite the above)"],
            "meaningful_activity_reports": ["events 105, 210, 315: DAILY_REPORT_CREATED, "
                                             "had_meaningful_activity=true (Days 1-3)"],
            "pacing": ["simulation_clock advanced day 1->4 across ~07:18-08:24 wall-clock "
                       "(~5 minutes)"],
        },
        "confidence_by_reviewer": {
            "director-primary (Gemini, PRIMARY)": primary["output"]["confidence"],
            "hermes (Hermes, CRITIQUE)": critique["output"]["confidence"],
        },
        "risks_of_acting_too_early": [
            "Prompt changes aimed at reducing passivity could manufacture forced, low-quality "
            "conversation-initiation — activity inflation without genuine behavioral improvement.",
            "Treating observational/passive behavior itself as the defect risks pathologizing "
            "realistic behavior, producing agents that speak without listening.",
            "Tuning prompts toward founder-defined 'meaningful interaction' risks encoding "
            "founder-directed behavior into agents, reducing emergent autonomy rather than "
            "preserving it.",
            "If the real cause is a turn-tracking/message-recording bug, treating it as an agent "
            "decision problem misdirects investigation effort and delays the actual fix.",
            "Any apparent 'improvement' from a behavioral intervention would be unverifiable as "
            "real vs. manufactured until the measurement-bug hypothesis is resolved first.",
        ],
        "smallest_safe_next_diagnostic_step": (
            "Two read-only checks, adopted from Hermes' proposed smaller/safer intervention as "
            "narrower and lower-risk than Gemini's broader 'review the prompts' recommendation: "
            "(1) verify whether public dialogue / SEND_MESSAGE actions are being correctly "
            "recorded into conversation turn counts — explains the empty recent_conversation_"
            "messages despite visible dialogue, and if confirmed is a wiring/recording bug, not "
            "an agent behavior problem; (2) review the 'the room went quiet' conversation-ending "
            "condition against the simulation's period-advance pace, since all three observed "
            "conversations ended this way with 0 turns. Neither check alters agent behavior, runs "
            "the simulation, or requires a code change to Village logic — both either resolve the "
            "issue directly or narrow the diagnosis before any prompt or behavioral change is "
            "even drafted."
        ),
    }


def build_founder_packet(
    round_id: str,
    *,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
) -> FounderPacket:
    records = load_round_records(round_id, observations_path)
    primary = records["primary"]
    critique = records["critiques"][0]  # exactly one CRITIQUE reviewer exists for this round

    if round_id != "round_b433606f27d04e8a":
        raise SynthesisError(
            f"No authored synthesis exists for round_id={round_id!r}. This function's synthesis "
            "content (_synthesize_round_b433606f27d04e8a) was written by directly reading "
            "round_b433606f27d04e8a's specific stored reviews — a different round needs its own "
            "reviews read and its own synthesis authored the same way, not a blind rerun of this "
            "one against different text."
        )
    synthesis = _synthesize_round_b433606f27d04e8a(primary, critique)

    reviewers = [
        ReviewerIdentity(
            reviewer_id=primary["reviewer_id"], role=primary["reviewer_role"],
            provider=primary["provider"], model=primary.get("model"),
            confidence=primary["output"]["confidence"], status=primary["output"]["status"],
        ),
        ReviewerIdentity(
            reviewer_id=critique["reviewer_id"], role=critique["reviewer_role"],
            provider=critique["provider"], model=critique.get("model"),
            confidence=critique["output"]["confidence"], status=critique["output"]["status"],
        ),
    ]

    packet = FounderPacket(
        round_id=round_id,
        snapshot_id=primary["snapshot_id"],
        snapshot_version=primary["snapshot_version"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        reviewers=reviewers,
        competing_explanations=[CompetingExplanation(**c) for c in synthesis.pop("competing_explanations")],
        recommendation_type=RecommendationType.DIAGNOSTIC_INVESTIGATION,
        recommendation_status=RecommendationStatus.CANDIDATE_FOR_TESTING,
        founder_approval_required=True,
        synthesis_note=(
            "Built entirely from the two already-stored records for this round (observation_ids "
            f"{primary['observation_id']} and {critique['observation_id']}) — no reviewer was "
            "rerun, no snapshot was regenerated, no model was called to produce this packet. "
            "Disagreement is preserved deliberately: confidence_by_reviewer holds both numbers "
            "side by side rather than an average, and explicit_disagreements/competing_"
            "explanations are kept as separate, attributed items rather than collapsed into one "
            "verdict."
        ),
        **synthesis,
    )
    return packet


def save_packet(
    packet: FounderPacket,
    packets_dir: Path = DEFAULT_PACKETS_DIR,
    *,
    observations_path: Path = DEFAULT_OBSERVATIONS_PATH,
) -> Path:
    packets_dir.mkdir(parents=True, exist_ok=True)
    path = packets_dir / f"{packet.round_id}.json"
    path.write_text(packet.model_dump_json(indent=2) + "\n")
    # Bridge auto-update — a saved packet flips has_synthesis for this
    # round and supplies its recommendation_type/status/founder-approval
    # fields to the derived history index (see director_bridge.py).
    rebuild_rounds_history(observations_path=observations_path, packets_dir=packets_dir)
    return path


def render_founder_summary(packet: FounderPacket) -> str:
    lines = [
        "=" * 72,
        "FOUNDER PACKET — Director synthesis (Level 1, observation only)",
        "=" * 72,
        f"Round:     {packet.round_id}",
        f"Snapshot:  {packet.snapshot_id} (schema v{packet.snapshot_version})",
        f"Generated: {packet.generated_at}",
        "",
        "Reviewers:",
    ]
    for r in packet.reviewers:
        lines.append(f"  - {r.reviewer_id} [{r.role}] via {r.provider}"
                      + (f" ({r.model})" if r.model else "")
                      + f" — confidence {r.confidence:.2f}, status {r.status}")
    lines.append("")
    lines.append("Shared factual findings (both reviewers independently confirm):")
    lines += [f"  - {f}" for f in packet.shared_factual_findings]
    lines.append("")
    lines.append("Gemini-only findings:")
    lines += [f"  - {f}" for f in packet.gemini_only_findings]
    lines.append("")
    lines.append("Hermes-only findings:")
    lines += [f"  - {f}" for f in packet.hermes_only_findings]
    lines.append("")
    lines.append("Explicit disagreements (preserved, not averaged):")
    lines += [f"  - {d}" for d in packet.explicit_disagreements]
    lines.append("")
    lines.append("Competing explanations:")
    for c in packet.competing_explanations:
        lines.append(f"  - [{c.source}] {c.explanation}")
    lines.append("")
    lines.append("Confidence by reviewer (not averaged):")
    for name, conf in packet.confidence_by_reviewer.items():
        lines.append(f"  - {name}: {conf:.2f}")
    lines.append("")
    lines.append("Risks of acting too early:")
    lines += [f"  - {r}" for r in packet.risks_of_acting_too_early]
    lines.append("")
    lines.append("Smallest safe next diagnostic step:")
    lines.append(f"  {packet.smallest_safe_next_diagnostic_step}")
    lines.append("")
    lines.append(f"Recommendation type:   {packet.recommendation_type.value}")
    lines.append(f"Recommendation status: {packet.recommendation_status.value}")
    lines.append(f"Founder approval required: {packet.founder_approval_required}")
    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("round_id", type=str)
    parser.add_argument("--observations-path", type=Path, default=DEFAULT_OBSERVATIONS_PATH)
    parser.add_argument("--packets-dir", type=Path, default=DEFAULT_PACKETS_DIR)
    args = parser.parse_args()

    try:
        packet = build_founder_packet(
            args.round_id, observations_path=args.observations_path, packets_dir=args.packets_dir
        )
    except SynthesisError as exc:
        print(f"director_synthesis: FAILED: {exc}", file=sys.stderr)
        return 1

    path = save_packet(packet, args.packets_dir)
    print(render_founder_summary(packet))
    print(f"\nSaved to: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
