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


def expose_shared_research(
    session: Session,
    *,
    agent_id: str,
    research_session_id: str,
    source_event_id: int | None = None,
) -> list[AgentExposure]:
    """Grant one agent real exposure to *another agent's* completed research.

    This is the cross-pollination mechanism made concrete: reading a wall post
    that cites research, or joining a rabbit hole research has been linked
    into, is what lets an agent go from "I glimpsed a headline" to "I can cite
    QuestAuthor's actual finding" — grounded in something it was genuinely
    shown, never in omniscience. Idempotent in effect (repeat exposure rows are
    harmless and cheap; `has_been_exposed` is what callers check).

    Exposes the session, every one of its findings, and every claim inside
    those findings — a shared finding without its constituent claims would
    leave nothing for CHALLENGE_CLAIM or a claim-based REVISE_BELIEF to
    actually target, since claims (not findings) are the atomic unit both
    operate on.
    """
    from app.db.models.research import ResearchFinding
    from app.db.models.research_provenance import Claim

    rows = [
        expose(
            session,
            agent_id=agent_id,
            entity_type="research_session",
            entity_id=research_session_id,
            exposure_type=ExposureType.SHARED_FINDING,
            source_event_id=source_event_id,
        )
    ]
    finding_ids = list(
        session.scalars(
            select(ResearchFinding.id).where(
                ResearchFinding.research_session_id == research_session_id
            )
        )
    )
    for finding_id in finding_ids:
        rows.append(
            expose(
                session,
                agent_id=agent_id,
                entity_type="research_finding",
                entity_id=finding_id,
                exposure_type=ExposureType.SHARED_FINDING,
                source_event_id=source_event_id,
            )
        )
    if finding_ids:
        claim_ids = session.scalars(
            select(Claim.id).where(Claim.finding_id.in_(finding_ids))
        )
        for claim_id in claim_ids:
            rows.append(
                expose(
                    session,
                    agent_id=agent_id,
                    entity_type="claim",
                    entity_id=claim_id,
                    exposure_type=ExposureType.SHARED_FINDING,
                    source_event_id=source_event_id,
                )
            )
    return rows


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
