"""Delivering the Founder's messages into the Village.

A founder message is not ambient. It reaches an agent by being delivered to
them — an exposure row — exactly like anything else. A broadcast reaches
everyone; a targeted message reaches one person and nobody else learns of it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agents import Agent
from app.db.models.reports import FounderMessage
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, ExposureType
from app.services.events import record_event
from app.services.exposure import expose_many


def deliver_pending(session: Session, clock: SimulationClock) -> list[FounderMessage]:
    """Deliver every undelivered founder message and expose its recipients."""
    pending = session.scalars(
        select(FounderMessage).where(FounderMessage.delivered.is_(False))
    ).all()
    if not pending:
        return []

    everyone = list(session.scalars(select(Agent.agent_id).order_by(Agent.id)))
    for message in pending:
        recipients = [message.target_agent_id] if message.target_agent_id else everyone
        event = record_event(
            session,
            event_type=EventType.FOUNDER_MESSAGE_DELIVERED,
            agent_id=message.target_agent_id,
            payload={
                "founder_message_id": message.id,
                "broadcast": message.target_agent_id is None,
                "recipients": recipients,
            },
            entity_type="founder_message",
            entity_id=str(message.id),
            clock=clock,
        )
        expose_many(
            session,
            agent_ids=recipients,
            entity_type="founder_message",
            entity_id=message.id,
            exposure_type=ExposureType.FOUNDER_MESSAGE,
            source_event_id=event.id,
        )
        message.delivered = True
    return list(pending)


def messages_for(session: Session, agent_id: str, limit: int = 3) -> list[FounderMessage]:
    """Founder messages this agent has actually been exposed to."""
    from app.db.models.exposure import AgentExposure

    ids = session.scalars(
        select(AgentExposure.entity_id)
        .where(
            AgentExposure.agent_id == agent_id,
            AgentExposure.entity_type == "founder_message",
        )
        .order_by(AgentExposure.id.desc())
        .limit(limit)
    ).all()
    if not ids:
        return []
    return list(
        session.scalars(
            select(FounderMessage)
            .where(FounderMessage.id.in_([int(i) for i in ids]))
            .order_by(FounderMessage.id.desc())
        )
    )
