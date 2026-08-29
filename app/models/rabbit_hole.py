"""Rabbit holes — shared investigations several agents pile into (§13, §17)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, utcnow
from app.models.agent import AGENT_FK
from app.models.research import RESEARCH_FK, EvidenceStrength

RABBIT_HOLE_FK = "rabbit_holes.id"


class RabbitHoleStatus(str, enum.Enum):
    """How alive a rabbit hole currently is."""

    NEW = "NEW"
    ACTIVE = "ACTIVE"
    HOT = "HOT"
    COOLING = "COOLING"
    DORMANT = "DORMANT"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class RabbitHole(TimestampMixin, Base):
    """A topic that grew past one agent's single research session.

    ``evidence_strength`` deliberately reuses :class:`~app.models.research.EvidenceStrength`
    so a rabbit hole and the sessions feeding it are graded on one scale.
    """

    __tablename__ = "rabbit_holes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    originating_agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_strength: Mapped[EvidenceStrength] = mapped_column(
        Enum(EvidenceStrength, name="evidence_strength"),
        nullable=False,
        default=EvidenceStrength.INSUFFICIENT,
    )
    current_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterarguments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    open_questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    activity_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[RabbitHoleStatus] = mapped_column(
        Enum(RabbitHoleStatus, name="rabbit_hole_status"),
        nullable=False,
        default=RabbitHoleStatus.NEW,
    )
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RabbitHoleMember(Base):
    """An agent's membership in a rabbit hole."""

    __tablename__ = "rabbit_hole_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    rabbit_hole_id: Mapped[int] = mapped_column(
        ForeignKey(RABBIT_HOLE_FK), index=True, nullable=False
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class RabbitHoleResearch(Base):
    """Join row attaching a research session to a rabbit hole."""

    __tablename__ = "rabbit_hole_research"

    id: Mapped[int] = mapped_column(primary_key=True)
    rabbit_hole_id: Mapped[int] = mapped_column(
        ForeignKey(RABBIT_HOLE_FK), index=True, nullable=False
    )
    research_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, nullable=False
    )
