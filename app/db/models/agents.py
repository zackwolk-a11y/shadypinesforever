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

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
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


class AgentInterest(TimestampMixin, Base):
    """A topic an agent is drawn to, and how strongly (§9, Packet 7).

    ``strength`` lives on a 0.0-1.0 scale (the Founding Eight seed at 0.5,
    "moderately interested" — see ``scripts/seed_agents.py``). Every change is
    a small, mechanical delta (:mod:`app.services.interests`), never a single
    conversation jumping a topic to obsession — see the module docstring
    there for the deltas themselves.

    ``dormant`` is a flag the interest-evolution service flips, not something
    derived on read: a genuinely emerging interest needs somewhere to record
    "this went quiet" that survives until something revives it, the same
    reasoning that gave rabbit holes a real ``status`` column instead of
    computing liveliness fresh on every query.
    """

    __tablename__ = "agent_interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    interest: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_engaged: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_engaged_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dormant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supporting_research_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    supporting_event_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


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
    """How two agents stand with one another (§12, Packet 7).

    ``trust_score`` starts at a friendly baseline (60/100, not a neutral 50)
    because friendship is the Village's default, not something earned from
    zero (§10). It moves in small, slow steps — repeated good collaboration
    nudges it up, repeated poor collaboration nudges it down a little — and
    is a fact about how the two agents have gotten on, entirely separate from
    any SOCIAL memory either of them holds about the other (a memory can
    fade in retrieval priority; this number is the running total it fed).

    Packet 8 adds two more dimensions deliberately kept distinct from
    ``trust_score`` rather than folded into one like/dislike meter (§ "do not
    turn relationships into simplistic like/dislike meters"): ``familiarity``
    (how much interaction history exists at all — grows with every exchange,
    trust-neutral) and ``intellectual_affinity`` (how much these two enjoy
    engaging each other's ideas specifically — moves from productive
    disagreement and shared-interest conversations, not from small talk).
    ``productive_disagreement_count`` is the mechanical record behind the
    second: a real disagreement that ran its course, not a proxy for
    conflict. "Shared interests" is deliberately not a stored column — it is
    computed on demand from the current ``agent_interests`` rows
    (``dialogue.shared_interest_overlap``), since a stored snapshot would go
    stale the moment either agent's interests moved.
    """

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
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    familiarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    intellectual_affinity: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    productive_disagreement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
