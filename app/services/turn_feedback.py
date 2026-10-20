"""Turn feedback — the engine's quality signals, carried into the next turn.

Before this module, the engine noticed quality problems and then forgot them:
a rejected decision got at most one same-turn correction attempt, a promise
said aloud but never recorded vanished, and nothing told the agent. A report
could describe the problem; no later turn could use it.

Here each signal becomes one short, *factual* note about the agent's own
record, shown once on that agent's next activation under "NOTES ON YOUR
RECENT TURNS", and the decision that follows is judged — did the same problem
recur? That judgement (``addressed``) is what makes "the Village learns from
feedback" measurable instead of asserted: the cycle-proof report counts how
often a note was followed by the problem not recurring.

Autonomy guard (Director constitution §3): notes state what happened. They
never ask an agent to be more active, speak more, or research more. A note
about silence or passivity is deliberately not one of the kinds below.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models.intentions import AgentFeedback
from app.db.models.world import SimulationClock
from app.domain.enums import EventType
from app.schemas.actions import ActionType
from app.services.events import record_event

#: Every kind of note, and what "addressed" means for it on the next turn.
KINDS = {
    "unrecorded_commitment": "the next decision did not again promise something aloud without recording it",
    "rejected_decision": "the next decision passed validation on its first attempt",
    "corrected_decision": "the next decision passed validation on its first attempt",
    "unknown_memory_citation": "the next decision cited only memories it was actually shown",
    "intention_expired": "informational — not judged",
}

_JUDGED = {"unrecorded_commitment", "rejected_decision", "corrected_decision", "unknown_memory_citation"}

MAX_NOTES_SHOWN = 3

#: First-person future commitments. Deliberately narrow: "I'll" / "I will" /
#: "I'm going to" / "let me <verb>" — the phrasing that, in a real live day,
#: preceded actions that were then never taken.
_COMMITMENT = re.compile(
    r"\b(i['’]ll|i will|i['’]m going to|i am going to|"
    r"let me (?:look|dig|check|pull|write|draft|put|find|research|post|ask|send|map|sketch|try)|"
    r"i can (?:look|dig|pull|write|draft|research|post|send|map|sketch))\b",
    re.IGNORECASE,
)


def record(
    session: Session,
    agent_id: str,
    kind: str,
    note: str,
    clock: SimulationClock | None,
    *,
    source_event_id: int | None = None,
    detail: dict | None = None,
) -> AgentFeedback:
    row = AgentFeedback(
        agent_id=agent_id, kind=kind, note=note[:400], source_event_id=source_event_id,
        detail=detail or {}, created_sim_day=clock.current_day if clock else None,
    )
    session.add(row)
    session.flush()
    record_event(
        session,
        event_type=EventType.TURN_FEEDBACK_RECORDED,
        agent_id=agent_id,
        payload={"feedback_id": row.id, "kind": kind, "note": row.note},
        entity_type="agent_feedback",
        entity_id=str(row.id),
        causation_id=source_event_id,
        clock=clock,
    )
    return row


def pending_for(session: Session, agent_id: str, *, limit: int = MAX_NOTES_SHOWN) -> list[AgentFeedback]:
    """Notes not yet shown, newest first."""
    return list(
        session.scalars(
            select(AgentFeedback)
            .where(AgentFeedback.agent_id == agent_id, AgentFeedback.shown_at.is_(None))
            .order_by(AgentFeedback.id.desc())
            .limit(limit)
        )
    )


def mark_shown(rows: list[AgentFeedback]) -> None:
    now = utcnow()
    for row in rows:
        row.shown_at = now


def find_unrecorded_commitment(decision) -> str | None:
    """The first commitment phrase said aloud this turn, if the same decision
    did not also record an intention (or close one)."""
    if decision.new_intention is not None or decision.fulfills_intention_id:
        return None
    texts = [decision.public_dialogue or ""]
    texts += [
        a.content or "" for a in decision.actions
        if a.type in (ActionType.SPEAK, ActionType.START_CONVERSATION)
    ]
    for text in texts:
        match = _COMMITMENT.search(text)
        if match:
            start = max(0, match.start() - 10)
            return " ".join(text[start: match.end() + 60].split())
    return None


def judge_unshown(session: Session, agent_id: str) -> None:
    """Control arm (FEEDBACK_NOTES=off): notes are never shown, so they are
    judged against the next decision exactly as if they had been — marking
    them shown-equivalent here keeps the two arms' numbers comparable."""
    mark_shown(pending_for(session, agent_id, limit=50))


def judge_next_decision(
    session: Session,
    agent_id: str,
    *,
    first_attempt_ok: bool,
    unrecorded_commitment: bool,
    unknown_memory_ids: list[int],
    clock: SimulationClock,
    event_id: int | None,
) -> list[int]:
    """Judge every note this agent was shown but that hasn't been judged yet,
    against the decision it just made. Returns ids judged addressed."""
    rows = list(
        session.scalars(
            select(AgentFeedback).where(
                AgentFeedback.agent_id == agent_id,
                AgentFeedback.shown_at.is_not(None),
                AgentFeedback.addressed.is_(None),
                AgentFeedback.kind.in_(_JUDGED),
            )
        )
    )
    addressed: list[int] = []
    for row in rows:
        if row.kind == "unrecorded_commitment":
            ok = not unrecorded_commitment
        elif row.kind in ("rejected_decision", "corrected_decision"):
            ok = first_attempt_ok
        elif row.kind == "unknown_memory_citation":
            ok = not unknown_memory_ids
        else:  # pragma: no cover - _JUDGED filters
            continue
        row.addressed = ok
        row.judged_event_id = event_id
        if ok:
            addressed.append(row.id)
            record_event(
                session,
                event_type=EventType.TURN_FEEDBACK_ADDRESSED,
                agent_id=agent_id,
                payload={"feedback_id": row.id, "kind": row.kind},
                entity_type="agent_feedback",
                entity_id=str(row.id),
                causation_id=event_id,
                clock=clock,
            )
    return addressed
