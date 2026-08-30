"""The founder's channel into the village, and what comes back out (§17, §23)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK


class FounderMessage(TimestampMixin, Base):
    """A message from the founder. ``target_agent_id`` NULL means broadcast."""

    __tablename__ = "founder_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DailyReport(TimestampMixin, Base):
    """The end-of-day Founder Field Report (Packet 9).

    Two representations of the same report are kept side by side, on
    purpose, per the packet's own "do not store only final prose" — a later
    multi-day/weekly synthesis needs to read real structured facts back out,
    not re-parse rendered prose:

    - ``summary_text`` is the full rendered report exactly as a human reads
      it — the ten §-numbered sections under the "DAILY FIELD REPORT" banner.
    - ``structured`` is the machine-queryable backing data behind it: the
      deterministically-gathered, ranked facts (app/services/daily_synthesis.py's
      ``DailyFacts``) plus the model's synthesis, each item still carrying
      its real database id and epistemic classification. This is also what
      makes report provenance checkable after the fact without re-deriving
      it from the prose.

    ``had_meaningful_activity`` is set mechanically from whether
    ``gather_facts`` actually found anything — the report never invents
    significance on a quiet day, it says so instead (§ Part C/K).
    """

    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("day_number", name="uq_daily_reports_day_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    day_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    had_meaningful_activity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Same fixture-flagging convention as every other generated row in this
    #: schema — a fixture-day report must never be mistaken for a live one.
    is_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
