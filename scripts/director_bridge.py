"""The Director bridge: persistent context/history layer.

The continuity layer that eliminates the manual copy/paste workflow
between the Fishbowl, Claude Code, and every reviewer (Gemini, Hermes, and
whatever comes next). Two kinds of content, kept deliberately distinct:

- **Static**: the Village's goals, Founder authority, autonomy principles,
  safety rules, evaluation criteria, and architecture —
  `.director/context/constitution.md`, hand-curated, rarely changes.
- **Dynamic**: what actually happened — `.director/history/rounds.jsonl`
  (every past round: reviewers, recommendations, confidence — derived and
  rebuilt from the authoritative sources, `.director/observations.jsonl`
  and `.director/packets/`, never hand-edited) and
  `.director/history/decisions.jsonl` (Founder decisions on those rounds —
  append-only, and the one piece of history that is NOT derivable from
  anything else, since nothing else records what the Founder decided).

`get_relevant_history()` is the one function anything downstream (director
reviewers, a future synthesis reviewer) should call — it returns a bounded
package (the constitution plus a capped number of round summaries plus any
still-pending rounds plus recorded decisions), never the raw contents of
every stored snapshot, reviewer record, or packet.

Entirely outside the Village database — every path here is under
`.director/`, the same rule every other Director component follows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
DIRECTOR_DIR = REPO_ROOT / ".director"

CONSTITUTION_PATH = DIRECTOR_DIR / "context" / "constitution.md"
ROUNDS_HISTORY_PATH = DIRECTOR_DIR / "history" / "rounds.jsonl"
DECISIONS_PATH = DIRECTOR_DIR / "history" / "decisions.jsonl"
OBSERVATIONS_PATH = DIRECTOR_DIR / "observations.jsonl"
PACKETS_DIR = DIRECTOR_DIR / "packets"

#: How many decision states a Founder decision may record. Kept separate
#: from RecommendationStatus (director_reviewers.py) on purpose: a
#: reviewer's status is what it proposes; a decision is what the Founder
#: did about it — two different vocabularies for two different actors.
DECISION_VALUES = ("APPROVED", "REJECTED", "DEFERRED")


class BridgeError(RuntimeError):
    """The bridge could not read or write its own state."""


class ReviewerBrief(BaseModel):
    reviewer_id: str
    role: str
    provider: str
    model: str | None
    confidence: float
    status: str


class RoundSummary(BaseModel):
    """A compact, bounded record of one round — never the full reviewer
    text. Derived entirely from observations.jsonl + packets/; rebuilt
    fresh each time, never hand-edited."""

    round_id: str
    snapshot_id: str
    snapshot_version: int
    first_recorded_at: str
    reviewers: list[ReviewerBrief]
    has_synthesis: bool
    recommendation_type: str | None
    recommendation_status: str | None
    founder_approval_required: bool | None
    summary: str


class FounderDecision(BaseModel):
    round_id: str
    decision: str  # one of DECISION_VALUES
    rationale: str
    decided_at: str
    decided_by: str = "Founder"


def load_constitution(path: Path = CONSTITUTION_PATH) -> str:
    if not path.exists():
        raise BridgeError(f"no constitution found at {path}.")
    return path.read_text()


def _load_all_observations(observations_path: Path) -> list[dict[str, Any]]:
    if not observations_path.exists():
        return []
    records = []
    with observations_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def rebuild_rounds_history(
    *,
    observations_path: Path = OBSERVATIONS_PATH,
    packets_dir: Path = PACKETS_DIR,
    history_path: Path = ROUNDS_HISTORY_PATH,
) -> list[RoundSummary]:
    """Regenerate .director/history/rounds.jsonl from the authoritative
    sources. Deterministic and idempotent — safe to call after every round
    (director_loop.py and director_synthesis.py both do, automatically) or
    by hand at any time. Never trust a hand edit to this file; it will be
    silently overwritten on the next call."""
    records = _load_all_observations(observations_path)
    by_round: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_round.setdefault(rec["round_id"], []).append(rec)

    summaries: list[RoundSummary] = []
    for round_id, recs in by_round.items():
        successful = [r for r in recs if "output" in r]
        if not successful:
            continue  # every attempt for this round failed; nothing to summarize
        reviewers = [
            ReviewerBrief(
                reviewer_id=r["reviewer_id"], role=r["reviewer_role"], provider=r["provider"],
                model=r.get("model"), confidence=r["output"]["confidence"], status=r["output"]["status"],
            )
            for r in successful
        ]
        primary = next((r for r in successful if r["reviewer_role"] == "PRIMARY"), successful[0])
        first_recorded_at = min(r["recorded_at"] for r in recs)

        packet_path = packets_dir / f"{round_id}.json"
        has_synthesis = packet_path.exists()
        recommendation_type = recommendation_status = None
        founder_approval_required = None
        summary_text = primary["output"].get("interpretation", "")[:280]
        if has_synthesis:
            packet = json.loads(packet_path.read_text())
            recommendation_type = packet.get("recommendation_type")
            recommendation_status = packet.get("recommendation_status")
            founder_approval_required = packet.get("founder_approval_required")
            summary_text = packet.get("smallest_safe_next_diagnostic_step", summary_text)[:280]
        else:
            recommendation_type = primary["output"].get("recommendation_type")
            recommendation_status = primary["output"].get("status")

        summaries.append(
            RoundSummary(
                round_id=round_id,
                snapshot_id=primary["snapshot_id"],
                snapshot_version=primary["snapshot_version"],
                first_recorded_at=first_recorded_at,
                reviewers=reviewers,
                has_synthesis=has_synthesis,
                recommendation_type=recommendation_type,
                recommendation_status=recommendation_status,
                founder_approval_required=founder_approval_required,
                summary=summary_text,
            )
        )

    summaries.sort(key=lambda s: s.first_recorded_at)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w") as f:
        for s in summaries:
            f.write(s.model_dump_json() + "\n")
    return summaries


def record_founder_decision(
    round_id: str,
    decision: str,
    rationale: str,
    *,
    decided_by: str = "Founder",
    decisions_path: Path = DECISIONS_PATH,
) -> FounderDecision:
    """Append one Founder decision. The only history component here that
    is NOT derived/rebuildable — nothing else records what the Founder
    actually decided, so this is a real, authoritative, append-only
    ledger. Never called automatically; a decision is a human act."""
    if decision not in DECISION_VALUES:
        raise BridgeError(f"decision must be one of {DECISION_VALUES}, got {decision!r}.")
    record = FounderDecision(
        round_id=round_id, decision=decision, rationale=rationale,
        decided_at=datetime.now(timezone.utc).isoformat(), decided_by=decided_by,
    )
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    with decisions_path.open("a") as f:
        f.write(record.model_dump_json() + "\n")
    return record


def _load_decisions(decisions_path: Path) -> list[FounderDecision]:
    if not decisions_path.exists():
        return []
    out = []
    with decisions_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(FounderDecision.model_validate_json(line))
    return out


def get_relevant_history(
    *,
    max_recent_rounds: int = 5,
    max_pending_rounds: int = 10,
    constitution_path: Path = CONSTITUTION_PATH,
    history_path: Path = ROUNDS_HISTORY_PATH,
    decisions_path: Path = DECISIONS_PATH,
) -> dict[str, Any]:
    """The one bounded package any downstream reviewer should be given —
    never the raw contents of every snapshot/observation/packet ever
    produced. Three parts:

    - constitution: the full (short, hand-curated) static document.
    - recent_rounds: the last `max_recent_rounds` rounds, most recent
      first — bounded recency window.
    - pending_rounds: any round whose recommendation_status is not
      OBSERVATION_ONLY and has no recorded Founder decision yet, capped at
      `max_pending_rounds` — bounded by relevance (still awaiting a
      decision) rather than by recency, so an old undecided round is never
      silently dropped just because newer rounds pushed it out of the
      recency window. De-duplicated against recent_rounds.
    - decisions: every recorded Founder decision — inherently small and
      high-value, kept unbounded (there will never be many).
    """
    if not history_path.exists():
        rebuild_rounds_history(history_path=history_path)

    constitution = load_constitution(constitution_path)

    rounds: list[RoundSummary] = []
    if history_path.exists():
        with history_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rounds.append(RoundSummary.model_validate_json(line))
    rounds.sort(key=lambda s: s.first_recorded_at, reverse=True)

    decisions = _load_decisions(decisions_path)
    decided_round_ids = {d.round_id for d in decisions}

    recent = rounds[:max_recent_rounds]
    recent_ids = {r.round_id for r in recent}

    pending = [
        r for r in rounds
        if r.round_id not in recent_ids
        and r.round_id not in decided_round_ids
        and r.recommendation_status not in (None, "OBSERVATION_ONLY")
    ][:max_pending_rounds]

    return {
        "constitution": constitution,
        "recent_rounds": [r.model_dump() for r in recent],
        "pending_rounds": [r.model_dump() for r in pending],
        "decisions": [d.model_dump() for d in decisions],
    }
