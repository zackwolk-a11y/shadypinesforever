"""Search-provider usage telemetry (Packet 10, Part G).

Distinct from ``LLMRun`` (``app/db/models/telemetry.py``), which tracks what
an *LLM* call cost — this tracks what a *search provider* call cost, a
completely separate vendor relationship. One row per research session,
aggregating every query/fetch that session actually made, so "how many live
searches happened, by which provider, triggered by which agent" is a direct
query rather than a log re-derivation.

Never stores an API key, a raw request/response body, or anything else that
could leak a secret (Part R) — only counts, a provider name, and timing.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK
from app.db.models.research import RESEARCH_FK


class ResearchProviderUsage(TimestampMixin, Base):
    """One research session's aggregate search-provider usage."""

    __tablename__ = "research_provider_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    research_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, unique=True, nullable=False
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    is_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    queries_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetch_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: A search() call that failed and was retried once (Part H: "track
    #: retry count and stop safely") — never an unbounded retry loop.
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Whether the session ultimately failed (RESEARCH_UNAVAILABLE) despite
    #: whatever partial usage happened before that — a failed session can
    #: still have spent real provider quota.
    failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Only populated when the provider's response itself reports usage/
    #: credits (Part G: "do not invent cost numbers when the provider does
    #: not supply them") — left null otherwise, never defaulted to 0 as if
    #: that were a real reading.
    provider_reported_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
