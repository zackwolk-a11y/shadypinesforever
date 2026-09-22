"""Who has been exposed to what.

The single most destroyable requirement in the Village is partial knowledge. If
a context builder ever does ``get_all_wall_entries()``, all eight inhabitants
become omniscient and the experiment is over — cross-pollination becomes
meaningless because nobody had anything to learn.

An exposure row is the record that a particular agent actually encountered a
particular thing, and by what route. Nothing may be shown to an agent that it
has no exposure to.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.models.agents import AGENT_FK
from app.domain.enums import ExposureType


class AgentExposure(Base):
    """One agent, one thing it has encountered, one route by which it did."""

    __tablename__ = "agent_exposures"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exposure_type: Mapped[ExposureType] = mapped_column(
        Enum(ExposureType, name="exposure_type"), nullable=False
    )
    exposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    source_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
