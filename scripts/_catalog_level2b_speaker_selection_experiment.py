#!/usr/bin/env python3
"""Founder-authorized, one-time act: catalog the existing, already-run,
already-Founder-accepted speaker_selection_fair_opportunity_ab Level 2B
experiment through the new director_experiments.py state machine.

This does NOT design, re-run-with-new-parameters, or draw any new
conclusion about speaker selection. The experiment itself
(director_level2b_experiment.py) was built, fixture-tested, run, reviewed
(PRIMARY -> CRITIQUE -> deterministic reconciliation -> SYNTHESIS), and its
evidence formally ACCEPTED by the Founder as round_73da274827304dbe
(.director/history/decisions.jsonl, decided_at 2026-09-03T23:05:50Z) BEFORE
director_experiments.py (the generalized Level 2A-shaped state machine) even
existed. That state machine's own docstring identifies registering this one
experiment_type as a "pure Python declaration with zero execution" already
done, and running it once through CANDIDATE_FOR_EXPERIMENT ->
APPROVED_FOR_EXPERIMENT -> EXPERIMENT_COMPLETE as "a separate, later,
explicit step" — this script IS that step, and only that step.

allowed_operations is deliberately {} (no capabilities, no
call_service_functions): speaker_selection_fair_opportunity_ab's
implementation in director_experiments.py never calls anything on the
ExperimentContext it's handed (it delegates entirely to
director_level2b_experiment.run_all(), which manages its own isolated DB
internally) — so granting it zero ExperimentContext capabilities is both
correct (least privilege) and a live demonstration that the capability
gate holds even at zero.

Approved by "Founder" (the default) because this IS the human/Founder act
per director_experiments.approve_experiment's documented two-caller
boundary — not "autonomous_director_loop", which remains unauthorized
(AUTONOMOUS_EXECUTION_ENABLED stays False; this script never imports or
touches director_autonomous_loop.py).

Run once, by hand, under explicit Founder authorization. Not meant to be
re-run — re-running it just creates a second, redundant EXPERIMENT_COMPLETE
spec of the same type, which is harmless but pointless.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from director_experiments import (  # noqa: E402
    approve_experiment,
    create_candidate_experiment,
    load_evidence,
    run_experiment,
)

PARTICIPANT_IDS = [f"agent_{i + 1}" for i in range(8)]

ORIGINATING_RECOMMENDATION = (
    "Founder-accepted round_73da274827304dbe (.director/history/decisions.jsonl, "
    "decided_at 2026-09-03T23:05:50Z): Level 2B isolated, disposable A/B experiment -- "
    "production next_speaker (Candidate A) vs. a minimal fair-opportunity rule "
    "(Candidate B) -> Gemini PRIMARY -> Hermes CRITIQUE -> deterministic reconciliation "
    "-> GPT-5.6 Sol SYNTHESIS (confidence 0.86, recommendation_type "
    "DIAGNOSTIC_INVESTIGATION, recommendation_status CANDIDATE_FOR_TESTING). Preserved "
    "conclusion: Candidate B is mechanically inert under every closure-respecting "
    "scenario tested -- speaker selection is not established as the cause of Village "
    "passivity/zero-turn gatherings. Founder ACCEPTED the evidence as valid Director "
    "history; explicitly NOT approval to implement Candidate B, alter closure, rotate "
    "participants, or change prompts. This script's only purpose is to catalog that "
    "already-accepted result through the new director_experiments.py state machine so "
    "the autonomous loop has a real, human-run template to select among -- it draws no "
    "new conclusion and authorizes no implementation."
)

EVIDENCE_REFS = [
    ".director/level2b/ab_experiment_evidence.json -- original human-run A/B evidence "
    "(6 scenarios: all_silent, first_two_silent_third_willing, "
    "heterogeneous_speak_silence_pattern, reversed_order_third_willing, "
    "extended_all_silent_expose_cycling, repeated_gatherings_same_static_order)",
    ".director/packets/round_73da274827304dbe_final.json -- SYNTHESIS confidence 0.86, "
    "recommendation_status CANDIDATE_FOR_TESTING, recommendation_type "
    "DIAGNOSTIC_INVESTIGATION",
    ".director/history/decisions.jsonl round_73da274827304dbe -- Founder ACCEPTED "
    "(decided_at 2026-09-03T23:05:50Z), evidence-only, not implementation approval",
]


def main() -> int:
    spec = create_candidate_experiment(
        experiment_type="speaker_selection_fair_opportunity_ab",
        originating_round_id="round_73da274827304dbe",
        originating_snapshot_id="snap_f6d2acbb609148d6",
        originating_recommendation=ORIGINATING_RECOMMENDATION,
        evidence_refs=EVIDENCE_REFS,
        allowed_operations={"capabilities": [], "call_service_functions": []},
        scope={"participant_ids": PARTICIPANT_IDS},
        success_criteria=(
            "Candidate B (fair-opportunity next_speaker variant) is proven mechanically "
            "inert relative to Candidate A (real, unmodified production next_speaker) "
            "under every closure-respecting scenario, the run is deterministic across "
            "two independent invocations, and every one of "
            "director_level2b_experiment.REQUIRED_PASSING_CHECKS passes."
        ),
        failure_criteria=(
            "Either invocation raises, the two runs diverge non-deterministically where "
            "the baseline is expected to be deterministic, or any required falsification "
            "check fails."
        ),
        timeout_seconds=120,
    )
    print(f"created  {spec.experiment_id}  state={spec.state.value}")

    spec = approve_experiment(spec.experiment_id, approved_by="Founder")
    print(f"approved {spec.experiment_id}  state={spec.state.value}  approved_by={spec.approved_by}")

    spec = run_experiment(spec.experiment_id)
    print(f"ran      {spec.experiment_id}  state={spec.state.value}  run_status={spec.run_status}")

    evidence = load_evidence(spec.experiment_id)
    print(f"falsification.overall_candidate_b_passes_falsification = "
          f"{evidence['falsification']['overall_candidate_b_passes_falsification']}")
    print(f"determinism_check.run1_equals_run2 = {evidence['determinism_check']['run1_equals_run2']}")
    print(f"\nexperiment_id = {spec.experiment_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
