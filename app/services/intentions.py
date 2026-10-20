"""The intention -> action bridge.

The gap this closes: an agent could say "I'll dig into that tonight" inside a
conversation, but conversations only permit SPEAK/LEAVE, nothing carried the
promise out of the room, nothing reminded the speaker later, and nothing could
check whether it ever happened. Talk and action were two disconnected systems.

Here an intention is formed only by the agent's own decision
(``AgentDecision.new_intention``), shown back to it on later activations, gives
it a modest activation pull (opportunity, never obligation — the same
mechanism as a dormant rabbit hole's pull), and is closed only by:

- FULFILLED — a later activation actually *executed* an action of a plannable
  type, linked either explicitly (``fulfills_intention_id``) or matched by the
  engine on ``planned_action``. Which one happened is recorded, so a proof can
  require the explicit link;
- DROPPED — the agent changed its mind (``drops_intention_id``) — always
  legitimate, never penalized;
- EXPIRED — time ran out with no follow-through, recorded honestly.

Fulfillment never trusts the agent's claim alone: it requires an executed
action in the same turn, after validation, and the produced entity (a
research id, a wall post id, a message id) is stored on the intention.

Mechanism, not content: nothing here calls a model or judges whether the work
was *good* — only whether what was said was later done.
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agents import Agent, Relationship
from app.db.models.conversations import Conversation
from app.db.models.intentions import Intention
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, ExposureType, IntentionStatus, MemoryType
from app.schemas.actions import PLANNABLE_ACTIONS, ActionType, IntentionDraft
from app.services import clock as clock_service
from app.services.events import record_event
from app.services.exposure import expose, exposed_entity_ids

#: Most intentions an agent may hold open at once. Small on purpose: a list
#: of twenty open promises is a backlog, not a character.
MAX_OPEN_PER_AGENT = 3

#: How many periods an intention stays OPEN before it EXPIRES (default two
#: simulated days). Read from the environment so a trial profile can shorten
#: it without a code change.
DEFAULT_WINDOW_PERIODS = 10

#: Activation pull for an agent holding an open intention — the same order of
#: magnitude as scheduler.DORMANT_RABBIT_HOLE_PULL. Raises the chance of a
#: turn; never decides what the agent does with it.
OPEN_INTENTION_PULL = 1.5

#: Actions whose effect another agent can see (a message to them, or a shared
#: artifact) — used to decide whether the person an intention was made to
#: learns that it was carried out. Everything else stays private.
_VISIBLE_TO_OTHERS = {
    ActionType.SEND_MESSAGE,
    ActionType.ASK_QUESTION,
    ActionType.START_CONVERSATION,
    ActionType.POST_TO_WALL,
    ActionType.CREATE_RABBIT_HOLE,
    ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
    ActionType.RESOLVE_RABBIT_HOLE,
    ActionType.CHALLENGE_CLAIM,
}

_FOLLOW_THROUGH_TRUST_DELTA = 1.0


class IntentionError(ValueError):
    """An intention reference or draft that can't be honored."""


def window_periods() -> int:
    try:
        return max(1, int(os.getenv("INTENTION_WINDOW_PERIODS", str(DEFAULT_WINDOW_PERIODS))))
    except ValueError:
        return DEFAULT_WINDOW_PERIODS


def period_index(day: int, period: str) -> int:
    """Absolute position in simulated time, so windows can span days."""
    try:
        position = clock_service.PERIODS.index(period)
    except ValueError:
        position = 0
    return day * len(clock_service.PERIODS) + position


def clock_index(clock: SimulationClock) -> int:
    return period_index(clock.current_day, clock.current_period)


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def open_for(session: Session, agent_id: str, *, limit: int = MAX_OPEN_PER_AGENT) -> list[Intention]:
    return list(
        session.scalars(
            select(Intention)
            .where(Intention.agent_id == agent_id, Intention.status == IntentionStatus.OPEN)
            .order_by(Intention.id)
            .limit(limit)
        )
    )


def has_open(session: Session, agent_id: str) -> bool:
    return (
        session.scalars(
            select(Intention.id)
            .where(Intention.agent_id == agent_id, Intention.status == IntentionStatus.OPEN)
            .limit(1)
        ).first()
        is not None
    )


def involving(session: Session, agent_id: str, *, limit: int = 3) -> list[Intention]:
    """Open intentions *other* agents made that name this agent — only the
    ones this agent actually heard (an exposure row), never ones it wasn't
    there for. Partial knowledge holds for promises too."""
    heard = exposed_entity_ids(session, agent_id, "intention")
    if not heard:
        return []
    return list(
        session.scalars(
            select(Intention)
            .where(
                Intention.with_agent_id == agent_id,
                Intention.agent_id != agent_id,
                Intention.status == IntentionStatus.OPEN,
                Intention.id.in_([int(i) for i in heard]),
            )
            .order_by(Intention.id.desc())
            .limit(limit)
        )
    )


# --------------------------------------------------------------------------
# Validation (called from orchestrator.validate_decision)
# --------------------------------------------------------------------------


def validate_draft(
    session: Session, agent_id: str, draft: IntentionDraft, known_agent_ids: tuple[str, ...]
) -> None:
    if not (draft.what or "").strip():
        raise IntentionError("new_intention requires `what`")
    planned = (draft.planned_action or "").strip().upper()
    if planned not in {a.value for a in PLANNABLE_ACTIONS}:
        raise IntentionError(
            f"new_intention.planned_action {draft.planned_action!r} is not something that can be "
            f"followed through on later; use one of: {', '.join(sorted(a.value for a in PLANNABLE_ACTIONS))}"
        )
    if draft.with_agent_id:
        if draft.with_agent_id == agent_id:
            raise IntentionError("new_intention.with_agent_id cannot be yourself")
        if draft.with_agent_id not in known_agent_ids:
            raise IntentionError(f"unknown new_intention.with_agent_id {draft.with_agent_id!r}")
    if len(open_for(session, agent_id, limit=MAX_OPEN_PER_AGENT + 1)) >= MAX_OPEN_PER_AGENT:
        raise IntentionError(
            f"you already hold {MAX_OPEN_PER_AGENT} open intentions — follow through on one, "
            "drop one (drops_intention_id), or don't add another"
        )
    for existing in open_for(session, agent_id):
        if " ".join(existing.description.lower().split()) == " ".join(draft.what.lower().split()):
            raise IntentionError(f"that is already your open intention [I{existing.id}]")


def own_open(session: Session, agent_id: str, intention_id: int) -> Intention:
    intention = session.get(Intention, intention_id)
    if intention is None or intention.agent_id != agent_id:
        raise IntentionError(f"no intention [I{intention_id}] of yours")
    if intention.status is not IntentionStatus.OPEN:
        raise IntentionError(f"intention [I{intention_id}] is already {intention.status.value.lower()}")
    return intention


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------


def form(
    session: Session,
    agent_id: str,
    draft: IntentionDraft,
    clock: SimulationClock,
    correlation_id: str | None,
    *,
    conversation: Conversation | None = None,
) -> Intention:
    intention = Intention(
        agent_id=agent_id,
        description=draft.what.strip()[:400],
        planned_action=draft.planned_action.strip().upper(),
        with_agent_id=draft.with_agent_id or None,
        status=IntentionStatus.OPEN,
        source_conversation_id=conversation.id if conversation is not None else None,
        created_sim_day=clock.current_day,
        created_sim_period=clock.current_period,
        created_period_index=clock_index(clock),
    )
    session.add(intention)
    session.flush()
    event = record_event(
        session,
        event_type=EventType.INTENTION_FORMED,
        agent_id=agent_id,
        payload={
            "intention_id": intention.id,
            "what": intention.description,
            "planned_action": intention.planned_action,
            "with_agent_id": intention.with_agent_id,
            "conversation_id": intention.source_conversation_id,
        },
        entity_type="intention",
        entity_id=str(intention.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    intention.source_event_id = event.id
    # Everyone in the room heard it said; nobody else did.
    hearers = {agent_id}
    if conversation is not None:
        hearers |= set(conversation.participant_ids or [])
    for hearer in sorted(hearers):
        expose(
            session, agent_id=hearer, entity_type="intention", entity_id=intention.id,
            exposure_type=ExposureType.CREATED if hearer == agent_id else ExposureType.CONVERSATION,
            source_event_id=event.id,
        )
    return intention


def _close(
    session: Session,
    intention: Intention,
    status: IntentionStatus,
    event_type: EventType,
    clock: SimulationClock,
    correlation_id: str | None,
    payload: dict,
    note: str | None,
) -> int:
    intention.status = status
    intention.closed_sim_day = clock.current_day
    intention.closed_sim_period = clock.current_period
    intention.close_note = note
    event = record_event(
        session,
        event_type=event_type,
        agent_id=intention.agent_id,
        payload={"intention_id": intention.id, "what": intention.description,
                 "conversation_id": intention.source_conversation_id, **payload},
        entity_type="intention",
        entity_id=str(intention.id),
        correlation_id=correlation_id,
        causation_id=intention.source_event_id,
        clock=clock,
    )
    intention.closed_event_id = event.id
    return event.id


def fulfill(
    session: Session,
    intention: Intention,
    *,
    action_type: ActionType,
    explicit: bool,
    entity: dict | None,
    clock: SimulationClock,
    correlation_id: str | None,
) -> int:
    from app.services import memory

    intention.fulfilled_by_action = action_type.value
    intention.fulfilled_explicitly = explicit
    intention.fulfilled_entity = entity
    event_id = _close(
        session, intention, IntentionStatus.FULFILLED, EventType.INTENTION_FULFILLED, clock, correlation_id,
        {
            "planned_action": intention.planned_action,
            "fulfilled_by_action": action_type.value,
            "explicit": explicit,
            "type_match": action_type.value == intention.planned_action,
            "entity": entity,
            "with_agent_id": intention.with_agent_id,
            "formed_sim_day": intention.created_sim_day,
            "formed_sim_period": intention.created_sim_period,
        },
        None,
    )
    told = f" (I'd told {intention.with_agent_id})" if intention.with_agent_id else ""
    memory.remember(
        session, agent_id=intention.agent_id, memory_type=MemoryType.EPISODIC,
        content=f"I followed through on what I said I'd do{told}: \"{intention.description}\" — "
                f"{action_type.value.replace('_', ' ').lower()}.",
        importance=55.0, confidence=95.0, clock=clock, correlation_id=correlation_id,
        source_event_ids=[event_id],
        related_agent_ids=[intention.with_agent_id] if intention.with_agent_id else [],
        related_conversation_ids=[intention.source_conversation_id] if intention.source_conversation_id else [],
    )
    other = intention.with_agent_id
    if other and action_type in _VISIBLE_TO_OTHERS:
        memory.remember(
            session, agent_id=other, memory_type=MemoryType.SOCIAL,
            content=f"{intention.agent_id} followed through on what they told me: \"{intention.description}\".",
            importance=48.0, confidence=90.0, clock=clock, correlation_id=correlation_id,
            source_event_ids=[event_id], related_agent_ids=[intention.agent_id],
            related_conversation_ids=[intention.source_conversation_id] if intention.source_conversation_id else [],
        )
        _bump_trust(session, intention.agent_id, other)
    return event_id


def drop(
    session: Session, intention: Intention, clock: SimulationClock, correlation_id: str | None, note: str | None
) -> int:
    return _close(
        session, intention, IntentionStatus.DROPPED, EventType.INTENTION_DROPPED, clock, correlation_id,
        {}, (note or "")[:300] or None,
    )


def expire_stale(session: Session, clock: SimulationClock, *, window: int | None = None) -> list[int]:
    """Called on every period advance. Honest bookkeeping only: the agent
    gets a private memory that it didn't get to it, and a feedback note."""
    from app.services import memory, turn_feedback

    window = window or window_periods()
    now = clock_index(clock)
    expired: list[int] = []
    for intention in session.scalars(
        select(Intention).where(Intention.status == IntentionStatus.OPEN).order_by(Intention.id)
    ):
        if now - (intention.created_period_index or 0) < window:
            continue
        event_id = _close(
            session, intention, IntentionStatus.EXPIRED, EventType.INTENTION_EXPIRED, clock, None,
            {"window_periods": window}, None,
        )
        memory.remember(
            session, agent_id=intention.agent_id, memory_type=MemoryType.EPISODIC,
            content=f"I never got to something I said I'd do: \"{intention.description}\".",
            importance=35.0, confidence=95.0, clock=clock, source_event_ids=[event_id],
            related_agent_ids=[intention.with_agent_id] if intention.with_agent_id else [],
        )
        turn_feedback.record(
            session, intention.agent_id, "intention_expired",
            f"Your intention [I{intention.id}] (\"{intention.description[:120]}\") lapsed without "
            "being carried out or dropped.",
            clock, source_event_id=event_id, detail={"intention_id": intention.id},
        )
        expired.append(intention.id)
    return expired


def resolve_turn(
    session: Session,
    agent: Agent,
    decision,
    executed: list[tuple[ActionType, dict | None]],
    clock: SimulationClock,
    correlation_id: str,
    *,
    conversation: Conversation | None,
) -> dict:
    """Apply a validated, executed decision's intention fields.

    ``executed`` is (action type, produced entity) for every action that
    actually ran this turn. Returns a small summary for the AGENT_ACTED
    payload. Order: drop, then fulfill (explicit, then inferred), then form —
    so "I did X, and next I'll do Y" in one turn closes X before opening Y.
    """
    summary: dict = {"formed": None, "fulfilled": [], "dropped": None}

    if decision.drops_intention_id:
        intention = own_open(session, agent.agent_id, decision.drops_intention_id)
        drop(session, intention, clock, correlation_id, decision.summary)
        summary["dropped"] = intention.id

    # Only actions that really produced something count: a START_RESEARCH the
    # research provider couldn't run (no research id) is not follow-through.
    plannable = [
        (t, e) for t, e in executed
        if t in PLANNABLE_ACTIONS and not (e is not None and e.get("id") is None)
    ]
    used: set[int] = set()
    if decision.fulfills_intention_id and plannable:
        intention = own_open(session, agent.agent_id, decision.fulfills_intention_id)
        match = next((p for p in plannable if p[0].value == intention.planned_action), plannable[0])
        fulfill(session, intention, action_type=match[0], explicit=True, entity=match[1],
                clock=clock, correlation_id=correlation_id)
        summary["fulfilled"].append(intention.id)
        used.add(plannable.index(match))
    for i, (action_type, entity) in enumerate(plannable):
        if i in used:
            continue
        for intention in open_for(session, agent.agent_id):
            if intention.planned_action == action_type.value and intention.id not in summary["fulfilled"]:
                fulfill(session, intention, action_type=action_type, explicit=False, entity=entity,
                        clock=clock, correlation_id=correlation_id)
                summary["fulfilled"].append(intention.id)
                break

    if decision.new_intention is not None:
        intention = form(session, agent.agent_id, decision.new_intention, clock, correlation_id,
                         conversation=conversation)
        summary["formed"] = intention.id
    return summary


def _bump_trust(session: Session, a: str, b: str) -> None:
    x, y = sorted((a, b))
    rel = session.scalars(
        select(Relationship).where(Relationship.agent_a_id == x, Relationship.agent_b_id == y)
    ).first()
    if rel is None:
        rel = Relationship(agent_a_id=x, agent_b_id=y, trust_score=60.0, interaction_count=0)
        session.add(rel)
    rel.trust_score = min(100.0, (rel.trust_score or 60.0) + _FOLLOW_THROUGH_TRUST_DELTA)
