"""The founder's channel into the village, and what comes back out (§17, §23)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
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
    """The end-of-day report. ``content`` is JSON structured per §23's sections."""

    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    day_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
