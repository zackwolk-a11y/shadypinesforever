"""Conversations: who is talking, whose turn it is, and when it stops.

Conversations are short on purpose. A believable exchange is Roxy sharing
something, Vince asking a question, Dex challenging one implication, Sol making
a joke, and everyone drifting off — not eight agents each contributing a
paragraph. The engine never decides that everyone must respond: silence is a
legal, common move, and two consecutive silences wind a conversation down.

Knowledge from a conversation reaches its participants and nobody else. Every
turn writes exposure rows for the people in the room; an agent who was not
there has no record of it and will never be shown it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import utcnow
from app.db.models.agents import Agent, Relationship
from app.db.models.conversations import Conversation, ConversationMessage
from app.db.models.events import Event
from app.db.models.world import SimulationClock
from app.domain.enums import (
    ConversationStatus,
    ConversationTrigger,
    EventType,
    ExposureType,
)
from app.services.events import record_event
from app.services.exposure import expose_many

#: Consecutive silences that move a conversation toward the door.
SILENCES_TO_WIND_DOWN = 2

#: A spontaneous conversation stays small; only a gathering takes everyone.
MAX_SPONTANEOUS_PARTICIPANTS = 5


@dataclass(frozen=True)
class Turn:
    """Whose turn it is in an open conversation."""

    conversation: Conversation
    agent_id: str
    turn_number: int


def active_conversation(session: Session) -> Conversation | None:
    """The one conversation currently open, if any.

    Phase 1 runs a single clubhouse with one authoritative writer, so at most
    one conversation is open at a time. That keeps turn-taking legible.
    """
    return session.scalars(
        select(Conversation)
        .where(Conversation.status != ConversationStatus.ENDED)
        .order_by(desc(Conversation.id))
        .limit(1)
    ).first()


def start_conversation(
    session: Session,
    *,
    trigger: ConversationTrigger,
    participant_ids: list[str],
    clock: SimulationClock,
    correlation_id: str | None = None,
) -> Conversation:
    """Open a conversation and expose it to the people in it."""
    conversation = Conversation(
        trigger_type=trigger,
        participant_ids=list(participant_ids),
        status=ConversationStatus.ACTIVE,
        started_sim_day=clock.current_day,
        started_sim_period=clock.current_period,
    )
    session.add(conversation)
    session.flush()

    event = record_event(
        session,
        event_type=EventType.CONVERSATION_STARTED,
        payload={"trigger": trigger.value, "participants": list(participant_ids)},
        entity_type="conversation",
        entity_id=str(conversation.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    expose_many(
        session,
        agent_ids=participant_ids,
        entity_type="conversation",
        entity_id=conversation.id,
        exposure_type=ExposureType.CONVERSATION,
        source_event_id=event.id,
    )
    return conversation


def turn_count(session: Session, conversation: Conversation) -> int:
    """How many things have been said so far."""
    return session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
    ) or 0


def next_speaker(session: Session, conversation: Conversation) -> str | None:
    """Whoever has spoken least, breaking ties by the participant order.

    Turn-taking is mechanism. What the speaker says — or whether they say
    anything — is theirs.
    """
    participants: list[str] = list(conversation.participant_ids or [])
    if not participants:
        return None

    spoken = dict(
        session.execute(
            select(ConversationMessage.agent_id, func.count())
            .where(ConversationMessage.conversation_id == conversation.id)
            .group_by(ConversationMessage.agent_id)
        ).all()
    )
    last = session.scalars(
        select(ConversationMessage.agent_id)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(desc(ConversationMessage.turn_number))
        .limit(1)
    ).first()

    ranked = sorted(
        (a for a in participants if a != last or len(participants) == 1),
        key=lambda a: (spoken.get(a, 0), participants.index(a)),
    )
    return ranked[0] if ranked else None


def record_utterance(
    session: Session,
    conversation: Conversation,
    agent_id: str,
    content: str,
    clock: SimulationClock,
    *,
    correlation_id: str | None = None,
    causation_id: int | None = None,
    move: str | None = None,
) -> ConversationMessage:
    """Add one turn, and expose it to everyone in the room.

    ``move`` (Packet 8, ``app.services.dialogue.MOVE_*``) is stored on the
    event, not the message row — it's ephemeral tagging metadata for
    anti-repetition/memory-worthiness detection, not a permanent property of
    what was said.
    """
    message = ConversationMessage(
        conversation_id=conversation.id,
        agent_id=agent_id,
        content=content,
        turn_number=turn_count(session, conversation) + 1,
    )
    session.add(message)
    session.flush()

    event = record_event(
        session,
        event_type=EventType.CONVERSATION_MESSAGE,
        agent_id=agent_id,
        payload={"conversation_id": conversation.id, "turn": message.turn_number, "move": move},
        entity_type="conversation_message",
        entity_id=str(message.id),
        correlation_id=correlation_id,
        causation_id=causation_id,
        clock=clock,
    )
    # Participants only. This is the line that keeps knowledge partial.
    expose_many(
        session,
        agent_ids=conversation.participant_ids or [],
        entity_type="conversation_message",
        entity_id=message.id,
        exposure_type=ExposureType.CONVERSATION,
        source_event_id=event.id,
    )
    _touch_relationships(session, conversation.participant_ids or [], agent_id)
    return message


def leave(
    session: Session,
    conversation: Conversation,
    agent_id: str,
    clock: SimulationClock,
    *,
    correlation_id: str | None = None,
) -> None:
    """Walk someone out of the room.

    ``participant_ids`` is who is here now; ``departed_agent_ids`` remembers who
    was here earlier. Both matter: turn-taking needs the first, and knowing who
    legitimately heard what needs the second.
    """
    conversation.participant_ids = [
        a for a in (conversation.participant_ids or []) if a != agent_id
    ]
    if agent_id not in (conversation.departed_agent_ids or []):
        conversation.departed_agent_ids = [*(conversation.departed_agent_ids or []), agent_id]
    record_event(
        session,
        event_type=EventType.CONVERSATION_LEFT,
        agent_id=agent_id,
        payload={"conversation_id": conversation.id},
        entity_type="conversation",
        entity_id=str(conversation.id),
        correlation_id=correlation_id,
        clock=clock,
    )


def join(
    session: Session,
    conversation: Conversation,
    agent_id: str,
    clock: SimulationClock,
    *,
    correlation_id: str | None = None,
) -> None:
    """Bring an outsider into an open conversation (Packet 8).

    Exposes them to every turn already said — joining mid-conversation means
    hearing what's already been said, the same as being there from the
    start, not a redacted view forward-only from here.
    """
    if agent_id not in (conversation.participant_ids or []):
        conversation.participant_ids = [*(conversation.participant_ids or []), agent_id]
    conversation.departed_agent_ids = [
        a for a in (conversation.departed_agent_ids or []) if a != agent_id
    ]
    event = record_event(
        session,
        event_type=EventType.CONVERSATION_JOINED,
        agent_id=agent_id,
        payload={"conversation_id": conversation.id},
        entity_type="conversation",
        entity_id=str(conversation.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    expose_many(
        session,
        agent_ids=[agent_id],
        entity_type="conversation",
        entity_id=conversation.id,
        exposure_type=ExposureType.CONVERSATION,
        source_event_id=event.id,
    )
    existing_turns = session.scalars(
        select(ConversationMessage.id).where(ConversationMessage.conversation_id == conversation.id)
    ).all()
    for message_id in existing_turns:
        from app.services.exposure import expose

        expose(
            session, agent_id=agent_id, entity_type="conversation_message", entity_id=message_id,
            exposure_type=ExposureType.CONVERSATION, source_event_id=event.id,
        )
    _touch_relationships(session, conversation.participant_ids or [], agent_id)


def everyone_who_was_present(conversation: Conversation) -> set[str]:
    """Everyone entitled to know what was said here — current and departed."""
    return set(conversation.participant_ids or []) | set(conversation.departed_agent_ids or [])


def should_close(
    session: Session,
    conversation: Conversation,
    settings: Settings,
    consecutive_silences: int,
) -> bool:
    """Whether this conversation has run its course."""
    if len(conversation.participant_ids or []) < 2:
        return True
    if turn_count(session, conversation) >= settings.max_conversation_turns:
        return True
    return consecutive_silences >= SILENCES_TO_WIND_DOWN and (
        conversation.status is ConversationStatus.WINDING_DOWN
    )


def close(
    session: Session,
    conversation: Conversation,
    clock: SimulationClock,
    reason: str,
    *,
    correlation_id: str | None = None,
) -> None:
    """End a conversation and log why."""
    conversation.status = ConversationStatus.ENDED
    conversation.ended_at = utcnow()
    conversation.ending_reason = reason
    record_event(
        session,
        event_type=EventType.CONVERSATION_ENDED,
        payload={
            "conversation_id": conversation.id,
            "reason": reason,
            "turns": turn_count(session, conversation),
        },
        entity_type="conversation",
        entity_id=str(conversation.id),
        correlation_id=correlation_id,
        clock=clock,
    )


def morning_gathering_held_today(session: Session, clock: SimulationClock) -> bool:
    """Whether the day's gathering has already happened."""
    return (
        session.scalars(
            select(Event.id)
            .where(
                Event.event_type == EventType.CONVERSATION_STARTED,
                Event.sim_day == clock.current_day,
            )
            .limit(50)
        ).all()
        and session.scalars(
            select(Event.id)
            .where(
                Event.event_type == EventType.CONVERSATION_STARTED,
                Event.sim_day == clock.current_day,
                Event.payload["trigger"].as_string() == ConversationTrigger.MORNING_GATHERING.value,
            )
            .limit(1)
        ).first()
        is not None
    )


def start_morning_gathering(
    session: Session, clock: SimulationClock, *, correlation_id: str | None = None
) -> Conversation:
    """Everyone in the room, no agenda.

    Deliberately not "generate one research topic each": that produces exactly
    the eight-silo behaviour the experiment is trying to avoid. Agents are asked
    to participate naturally; whatever curiosity emerges is theirs.
    """
    participants = list(session.scalars(select(Agent.agent_id).order_by(Agent.id)))
    return start_conversation(
        session,
        trigger=ConversationTrigger.MORNING_GATHERING,
        participant_ids=participants,
        clock=clock,
        correlation_id=correlation_id,
    )


#: Packet 7 (§10): friends talking is baseline positive collaboration, so
#: every exchange nudges trust up a little — small and capped, so it takes
#: many conversations to move, never one.
_CONVERSATION_TRUST_DELTA = 0.5
_MAX_TRUST_SCORE = 100.0


def _touch_relationships(session: Session, participants: list[str], speaker: str) -> None:
    """Record that these people were in the room together."""
    now = utcnow()
    for other in participants:
        if other == speaker:
            continue
        pair = sorted((speaker, other))
        relationship = session.scalars(
            select(Relationship)
            .where(
                Relationship.agent_a_id == pair[0],
                Relationship.agent_b_id == pair[1],
            )
            .limit(1)
        ).first()
        if relationship is None:
            # Explicit values, not just the column defaults: those only apply
            # once SQLAlchemy flushes this row, but the increments just below
            # read trust_score/interaction_count back immediately.
            relationship = Relationship(
                agent_a_id=pair[0], agent_b_id=pair[1], trust_score=60.0, interaction_count=0,
            )
            session.add(relationship)
        relationship.last_interaction = now
        relationship.interaction_count += 1
        relationship.trust_score = min(_MAX_TRUST_SCORE, relationship.trust_score + _CONVERSATION_TRUST_DELTA)
