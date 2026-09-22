"""Source provenance: the exact evidence a model saw, and how it used it.

This is the spine the build bible calls the most important provenance
improvement over the bare §17 schema: a claim is never just "URL + summary".
It points at a passage — the exact bounded text a model was shown — and the
passage points at the source and the query that produced it. The chain reads
back as::

    claim  --evidence-->  passage  -->  source  -->  query  -->  session

which is what makes it possible to tell "the source says this" apart from
"the agent thinks the source implies this" after the fact, not just at the
moment of interpretation.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow
from app.domain.enums import EvidenceRelation, FindingClassification
from app.db.models.research import RESEARCH_FK


class ResearchSourcePassage(Base):
    """The exact bounded text retrieved for one source, in service of one query.

    ``excerpt_sha256`` is what makes this provenance rather than just another
    text column: it is a hash of exactly what the interpreting model was shown,
    independent of whatever the live page says an hour, a day, or a year later.
    """

    __tablename__ = "research_source_passages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("research_sources.id"), index=True, nullable=False
    )
    research_query_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_queries.id"), index=True, nullable=True
    )
    locator: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Where in the source this excerpt came from, if known."
    )
    excerpt_text: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    provider_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class Claim(TimestampMixin, Base):
    """One atomic, independently-classified statement inside a finding.

    Classification lives here too, not only on the parent finding: a single
    finding can bundle a REAL_WORLD_FACT alongside the AGENT_INFERENCE drawn
    from it, and collapsing them to the finding's one classification would
    erase exactly the distinction §2 exists to preserve.
    """

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, nullable=False
    )
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("research_findings.id"), index=True, nullable=False
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[FindingClassification] = mapped_column(
        Enum(FindingClassification, name="finding_classification"), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class ClaimEvidence(Base):
    """One claim's relationship to one passage: supports, contradicts, or context."""

    __tablename__ = "claim_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True, nullable=False)
    passage_id: Mapped[int] = mapped_column(
        ForeignKey("research_source_passages.id"), index=True, nullable=False
    )
    relation: Mapped[EvidenceRelation] = mapped_column(
        Enum(EvidenceRelation, name="evidence_relation"), nullable=False
    )
