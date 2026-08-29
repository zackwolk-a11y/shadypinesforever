"""Recording and querying what each agent has been exposed to.

Every context the builder assembles must go through here rather than reading
tables directly. That is the only thing standing between a Village of eight
people with different knowledge and a Village of eight people who all know
everything.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.exposure import AgentExposure
from app.domain.enums import ExposureType


def expose(
    session: Session,
    *,
    agent_id: str,
    entity_type: str,
    entity_id: str | int,
    exposure_type: ExposureType,
    source_event_id: int | None = None,
) -> AgentExposure:
    """Record that one agent encountered one thing."""
    exposure = AgentExposure(
        agent_id=agent_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        exposure_type=exposure_type,
        source_event_id=source_event_id,
    )
    session.add(exposure)
    return exposure


def expose_many(
    session: Session,
    *,
    agent_ids: Iterable[str],
    entity_type: str,
    entity_id: str | int,
    exposure_type: ExposureType,
    source_event_id: int | None = None,
) -> list[AgentExposure]:
    """Record the same encounter for several agents — conversation participants,
    typically. Note that this is every *participant*, never every agent."""
    return [
        expose(
            session,
            agent_id=agent_id,
            entity_type=entity_type,
            entity_id=entity_id,
            exposure_type=exposure_type,
            source_event_id=source_event_id,
        )
        for agent_id in agent_ids
    ]


def exposed_entity_ids(
    session: Session, agent_id: str, entity_type: str
) -> set[str]:
    """Every id of ``entity_type`` this agent has encountered."""
    return set(
        session.scalars(
            select(AgentExposure.entity_id).where(
                AgentExposure.agent_id == agent_id,
                AgentExposure.entity_type == entity_type,
            )
        )
    )


def has_been_exposed(
    session: Session, agent_id: str, entity_type: str, entity_id: str | int
) -> bool:
    """Whether this agent may be shown this thing at all."""
    return (
        session.scalars(
            select(AgentExposure.id)
            .where(
                AgentExposure.agent_id == agent_id,
                AgentExposure.entity_type == entity_type,
                AgentExposure.entity_id == str(entity_id),
            )
            .limit(1)
        ).first()
        is not None
    )
