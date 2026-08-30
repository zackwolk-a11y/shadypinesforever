"""Rabbit holes — shared investigations several agents pile into (§13, §17)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import EvidenceStrength, RabbitHoleStatus

from app.db.base import Base, TimestampMixin, utcnow
from app.db.models.agents import AGENT_FK
from app.db.models.research import RESEARCH_FK

RABBIT_HOLE_FK = "rabbit_holes.id"


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
    #: The simulated day of the most recent activity — what staleness and
    #: cooling are actually judged against. ``last_activity`` is a wall-clock
    #: timestamp (useful for ordering); heat decays in *simulated* days, which
    #: real time cannot answer on its own.
    last_activity_day: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RabbitHoleMember(Base):
    """An agent's membership in a rabbit hole.

    A row is never deleted on LEAVE_RABBIT_HOLE — ``left_at`` is stamped
    instead, the same pattern conversations use for
    ``departed_agent_ids``: the audit trail of who was ever in this hole
    matters as much as who is in it now, and "currently a member" is simply
    ``left_at IS NULL``.
    """

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
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
