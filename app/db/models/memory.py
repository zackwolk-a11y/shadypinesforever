"""Agent memory (§9, §17)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import MemoryType

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK


class Memory(TimestampMixin, Base):
    """One remembered thing.

    ``related_ids`` is a JSON list of loose references (research ids, agent ids,
    conversation ids) — deliberately not foreign-keyed, since a memory may point
    at something that has since been removed.
    """

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType, name="memory_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_recalled: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
