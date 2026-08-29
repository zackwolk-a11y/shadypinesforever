"""The append-only event log (§18).

**This table is append-only.** Nothing in the application layer may UPDATE or
DELETE a row in ``events``: the log is the village's audit trail, and a rewritten
history is worse than no history. Phase 1 enforces this by convention only — no
ORM-level immutability, no triggers — so treat every write as an INSERT.
"""

from __future__ import annotations


from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import EventType

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK


class Event(TimestampMixin, Base):
    """One immutable log line.

    Append-only: insert, never update or delete. ``agent_id`` is NULL for events
    that belong to the world rather than to any one agent.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type"), index=True, nullable=False
    )
    agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
