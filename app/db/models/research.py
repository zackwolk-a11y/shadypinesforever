"""Research sessions and everything a session produces (§6, §17).

§6 is emphatic that *when a source was published* and *when the village
retrieved it* are different facts, so ``ResearchSource`` keeps ``pub_date`` and
``retrieved_at`` as separate columns and never derives one from the other.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import EvidenceStrength, FindingClassification, ResearchStatus

from app.db.base import Base, TimestampMixin, utcnow
from app.db.models.agents import AGENT_FK

RESEARCH_FK = "research_sessions.research_id"


class ResearchSession(Base):
    """One agent's investigation of one question."""

    __tablename__ = "research_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    status: Mapped[ResearchStatus] = mapped_column(
        Enum(ResearchStatus, name="research_status"),
        nullable=False,
        default=ResearchStatus.IN_PROGRESS,
    )
    evidence_strength: Mapped[EvidenceStrength] = mapped_column(
        Enum(EvidenceStrength, name="evidence_strength"),
        nullable=False,
        default=EvidenceStrength.INSUFFICIENT,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    follow_ups: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_research: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Beyond §17: whether this session ran against the fixture research
    #: provider rather than a live search. A session's sources already say
    #: ``provider="fixture"``, but this makes the whole session unmistakable
    #: at a glance — "live research must never be confused with fixture
    #: research" is a hard requirement, not a nice-to-have.
    is_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ResearchQuery(Base):
    """A single search issued during a session, in the order it was issued."""

    __tablename__ = "research_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ResearchSource(Base):
    """A source a session actually looked at.

    ``pub_date`` is when the source was published; ``retrieved_at`` is when the
    village fetched it. Per §6 these are never conflated — a 1998 article read
    today is both, and reporting either as the other is a citation error.
    """

    __tablename__ = "research_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publication: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pub_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    #: The short relevance snippet the search call itself returned — what the
    #: village saw *before* deciding whether to fetch this source at all. The
    #: exact bounded text actually shown to the interpreting model lives on
    #: ResearchSourcePassage instead, with its own sha256; the two are kept
    #: separate because they answer different questions ("did this look worth
    #: reading" vs. "what did the model actually see").
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Beyond §17: which search vendor produced this result, and that vendor's
    #: own id for it, plus the bare domain — needed to detect when several
    #: sources ultimately trace back to one press release (§6).
    provider: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    provider_result_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ResearchFinding(TimestampMixin, Base):
    """One statement a session produced, tagged with its epistemic status."""

    __tablename__ = "research_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, nullable=False
    )
    finding_text: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[FindingClassification] = mapped_column(
        Enum(FindingClassification, name="finding_classification"), nullable=False
    )
