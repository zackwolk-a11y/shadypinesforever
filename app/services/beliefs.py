"""Beliefs: provisional, evidence-linked, and never silently right or wrong.

Two things are always the agent's own judgment: the belief's statement, and
the *direction* new evidence moves it (``STRENGTHENS``/``WEAKENS``/``REJECTS``
— see :class:`~app.domain.enums.BeliefBasisRelation`). Everything downstream
of that judgment — the new confidence number, the new status — is computed by
:func:`_apply_relation`, not proposed by a model. This is the same split the
build bible draws for rabbit-hole heat: an agent should never be asked to
invent a precise number it has no real basis for: the qualitative call
("this weakens what I thought") is a defensible epistemic act; "confidence is
now 61.7%" usually is not.

Every belief starts ``PROVISIONAL`` and stays revisable for its whole life —
even a ``SUPPORTED`` belief can be weakened again by the next piece of
evidence. Nothing here ever marks a belief permanently settled.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models.agents import AgentBelief
from app.db.models.belief import BeliefBasis
from app.db.models.world import SimulationClock
from app.domain.enums import BeliefBasisRelation, BeliefStatus, EventType, ExposureType
from app.services.events import record_event
from app.services.exposure import expose

#: Fixed, documented deltas — mechanism, not model free-association. A belief
#: that keeps getting strengthened approaches confidence asymptotically rather
#: than ever reaching false certainty; one WEAKENS or REJECTS is enough to
#: move it back into doubt regardless of how supported it looked a moment ago.
_STRENGTHEN_DELTA = 12.0
_WEAKEN_DELTA = -15.0
_REJECT_CONFIDENCE_CEILING = 15.0
_MAX_CONFIDENCE = 95.0
_MIN_CONFIDENCE = 5.0
_SUPPORTED_THRESHOLD = 55.0


def form(
    session: Session,
    agent_id: str,
    statement: str,
    research_id: str,
    initial_confidence: float,
    clock: SimulationClock,
    correlation_id: str,
) -> tuple[AgentBelief, int]:
    """Form a new belief, grounded in the agent's own completed research.

    ``initial_confidence`` should come from the research session's own
    assessed confidence, never invented fresh — a belief's starting confidence
    is only as good as the evidence it is founded on.
    """
    belief = AgentBelief(
        agent_id=agent_id,
        statement=statement,
        confidence=max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, initial_confidence)),
        basis=[research_id],
        status=BeliefStatus.PROVISIONAL,
        updated_at=utcnow(),
    )
    session.add(belief)
    session.flush()

    event = record_event(
        session,
        event_type=EventType.BELIEF_CREATED,
        agent_id=agent_id,
        payload={"belief_id": belief.id, "statement": statement, "research_id": research_id},
        entity_type="agent_belief",
        entity_id=str(belief.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    session.add(
        BeliefBasis(
            belief_id=belief.id,
            basis_type="research_session",
            basis_id=research_id,
            relation=BeliefBasisRelation.STRENGTHENS,
        )
    )
    expose(
        session, agent_id=agent_id, entity_type="agent_belief", entity_id=belief.id,
        exposure_type=ExposureType.CREATED, source_event_id=event.id,
    )
    return belief, event.id


def revise(
    session: Session,
    agent_id: str,
    belief: AgentBelief,
    relation: BeliefBasisRelation,
    basis_type: str,
    basis_id: str,
    note: str | None,
    clock: SimulationClock,
    correlation_id: str,
) -> int:
    """Move a belief given new evidence. Returns the event id.

    The confidence and status changes are entirely mechanical — see the module
    docstring. ``note`` is the agent's own explanation, stored on the event for
    the record, never fed back into the arithmetic.
    """
    session.add(
        BeliefBasis(belief_id=belief.id, basis_type=basis_type, basis_id=basis_id, relation=relation)
    )
    belief.basis = [*(belief.basis or []), basis_id]
    _apply_relation(belief, relation)
    belief.updated_at = utcnow()

    event_type = (
        EventType.BELIEF_REJECTED if relation is BeliefBasisRelation.REJECTS
        else EventType.BELIEF_UPDATED
    )
    event = record_event(
        session,
        event_type=event_type,
        agent_id=agent_id,
        payload={
            "belief_id": belief.id,
            "relation": relation.value,
            "new_status": belief.status.value,
            "new_confidence": belief.confidence,
            "basis_type": basis_type,
            "basis_id": basis_id,
            "note": note,
        },
        entity_type="agent_belief",
        entity_id=str(belief.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    return event.id


def retire(
    session: Session,
    agent_id: str,
    belief: AgentBelief,
    reason: str,
    clock: SimulationClock,
    correlation_id: str,
) -> int:
    """The agent simply no longer holds this belief. No new evidence required."""
    belief.status = BeliefStatus.RETIRED
    belief.updated_at = utcnow()
    event = record_event(
        session,
        event_type=EventType.BELIEF_UPDATED,
        agent_id=agent_id,
        payload={"belief_id": belief.id, "new_status": "RETIRED", "reason": reason},
        entity_type="agent_belief",
        entity_id=str(belief.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    return event.id


def _apply_relation(belief: AgentBelief, relation: BeliefBasisRelation) -> None:
    """The mechanical half of a revision: new confidence, new status."""
    if relation is BeliefBasisRelation.REJECTS:
        belief.confidence = min(belief.confidence, _REJECT_CONFIDENCE_CEILING)
        belief.status = BeliefStatus.REJECTED
        return

    if relation is BeliefBasisRelation.WEAKENS:
        belief.confidence = max(_MIN_CONFIDENCE, belief.confidence + _WEAKEN_DELTA)
        belief.status = (
            BeliefStatus.CONTESTED
            if belief.status in (BeliefStatus.SUPPORTED, BeliefStatus.PROVISIONAL)
            else belief.status
        )
        return

    # STRENGTHENS
    belief.confidence = min(_MAX_CONFIDENCE, belief.confidence + _STRENGTHEN_DELTA)
    if belief.status in (BeliefStatus.PROVISIONAL, BeliefStatus.CONTESTED):
        belief.status = (
            BeliefStatus.SUPPORTED if belief.confidence >= _SUPPORTED_THRESHOLD
            else BeliefStatus.PROVISIONAL
        )


def owned_by(session: Session, agent_id: str, belief_id: int) -> AgentBelief | None:
    return session.scalars(
        select(AgentBelief).where(AgentBelief.id == belief_id, AgentBelief.agent_id == agent_id)
    ).first()
