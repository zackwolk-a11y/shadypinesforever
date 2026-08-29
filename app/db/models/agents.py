"""Agents, their interests, their beliefs and their relationships (§17, §3).

Foreign keys across the whole schema reference *stable business keys* rather
than surrogate integer primary keys: ``agents.agent_id`` (e.g. ``agent_optimisto``)
and ``research_sessions.research_id``. Phase 1 stores agent and research
references inside JSON columns too (``conversations.participant_ids``,
``research_sessions.related_research``), and pointing the real foreign keys at
the same value space means an ``agent_id`` means exactly one thing everywhere.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import BeliefStatus

from app.db.base import Base, TimestampMixin

AGENT_FK = "agents.agent_id"


class Agent(TimestampMixin, Base):
    """One resident of the clubhouse.

    Rows are seeded by ``scripts/seed_agents.py`` (the Founding Eight of §3),
    never by a migration.
    """

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    identity: Mapped[str] = mapped_column(Text, nullable=False)
    voice: Mapped[str] = mapped_column(Text, nullable=False)
    current_location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_activity: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction_target: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AgentInterest(Base):
    """A topic an agent is drawn to, and how strongly (§9)."""

    __tablename__ = "agent_interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    interest: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_engaged: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentBelief(TimestampMixin, Base):
    """Something an agent currently holds to be true, and why (§2, §9).

    ``basis`` is a JSON list of the ``research_id`` / conversation ids the belief
    rests on; ``confidence`` is a 0-100 percentage.
    """

    __tablename__ = "agent_beliefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    basis: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[BeliefStatus] = mapped_column(
        Enum(BeliefStatus, name="belief_status"),
        nullable=False,
        default=BeliefStatus.PROVISIONAL,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Relationship(Base):
    """How two agents stand with one another (§12)."""

    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_a_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    agent_b_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_interaction: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
