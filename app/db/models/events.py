"""The append-only event log (§18).

**This table is append-only.** Nothing in the application layer may UPDATE or
DELETE a row in ``events``: the log is the village's audit trail, and a rewritten
history is worse than no history. Phase 1 enforces this by convention only — no
ORM-level immutability, no triggers — so treat every write as an INSERT.
"""

from __future__ import annotations


from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
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

    # Where in simulated time this happened. The bible calls this sim_time; it is
    # split into day and period because every activation query filters on both.
    sim_day: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    sim_period: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # What the event is about, when it is about something.
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # correlation_id ties one causal chain together (a research session and every
    # share, challenge and follow-up it provokes); causation_id points at the
    # single event that directly caused this one. Together they let the history of
    # an idea be reconstructed without full event replay.
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    causation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
