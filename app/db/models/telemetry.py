"""What the Village costs to run.

Every model call writes one row. By day seven this answers the question that
matters more than the token count: was the emergent culture worth the spend?

``is_fixture`` is recorded alongside the model so a fixture run can never be
counted as live activity, or its zero cost mistaken for efficiency.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK


class LLMRun(TimestampMixin, Base):
    """One model call: what it was for, what it cost, how long it took."""

    __tablename__ = "llm_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    is_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_creation_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stop_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
