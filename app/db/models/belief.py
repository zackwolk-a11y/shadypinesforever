"""Belief provenance: what moved a belief, and which direction (Packet 6).

This resolves the §17 / build-bible disagreement over the belief schema, by
giving each side's idea its correct home rather than picking one over the
other:

- §17 already shipped ``agent_beliefs.status`` as
  ``PROVISIONAL/SUPPORTED/CONTESTED/REJECTED/RETIRED`` — the belief's current
  standing. That stays exactly as migrated; renaming it now would be pure
  churn with nothing to show for it.
- The build bible's real point was that a belief needs a queryable,
  typed evidence trail — a ``belief_basis`` table, not just the JSON list
  ``agent_beliefs.basis`` already carries. That's what this file adds:
  ``basis_type``/``basis_id`` name the research session, wall post, or
  conversation that moved the belief, and ``relation`` — a distinct
  three-value vocabulary from claims' ``EvidenceRelation`` — records the
  *epistemic direction* of that move (see :class:`BeliefBasisRelation`).

``agent_beliefs.basis`` (JSON) keeps being written as a flat, denormalized
list for quick display; this table is the authoritative, directional record
behind it. Both are populated together by ``app/services/beliefs.py``, never
in disagreement, since a client should be able to trust either.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.domain.enums import BeliefBasisRelation


class BeliefBasis(Base):
    """One piece of evidence, and how it moved one belief."""

    __tablename__ = "belief_basis"

    id: Mapped[int] = mapped_column(primary_key=True)
    belief_id: Mapped[int] = mapped_column(
        ForeignKey("agent_beliefs.id"), index=True, nullable=False
    )
    basis_type: Mapped[str] = mapped_column(
        String(32), nullable=False, doc="'research_session' | 'wall_post' | 'conversation'"
    )
    basis_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relation: Mapped[BeliefBasisRelation] = mapped_column(
        Enum(BeliefBasisRelation, name="belief_basis_relation"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
