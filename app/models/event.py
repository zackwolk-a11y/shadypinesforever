"""The append-only event log (§18).

**This table is append-only.** Nothing in the application layer may UPDATE or
DELETE a row in ``events``: the log is the village's audit trail, and a rewritten
history is worse than no history. Phase 1 enforces this by convention only — no
ORM-level immutability, no triggers — so treat every write as an INSERT.
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin
from app.models.agent import AGENT_FK


class EventType(str, enum.Enum):
    """Every kind of thing the village records (§18)."""

    AGENT_WOKE = "AGENT_WOKE"
    AGENT_RESEARCH_STARTED = "AGENT_RESEARCH_STARTED"
    SEARCH_EXECUTED = "SEARCH_EXECUTED"
    SOURCE_DISCOVERED = "SOURCE_DISCOVERED"
    RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
    FINDING_CREATED = "FINDING_CREATED"
    FINDING_SHARED = "FINDING_SHARED"
    RESEARCH_WALL_POSTED = "RESEARCH_WALL_POSTED"
    RABBIT_HOLE_CREATED = "RABBIT_HOLE_CREATED"
    RABBIT_HOLE_JOINED = "RABBIT_HOLE_JOINED"
    RABBIT_HOLE_UPDATED = "RABBIT_HOLE_UPDATED"
    CONVERSATION_STARTED = "CONVERSATION_STARTED"
    CONVERSATION_MESSAGE = "CONVERSATION_MESSAGE"
    CONVERSATION_ENDED = "CONVERSATION_ENDED"
    CLAIM_CHALLENGED = "CLAIM_CHALLENGED"
    FOLLOWUP_QUESTION_CREATED = "FOLLOWUP_QUESTION_CREATED"
    BELIEF_CREATED = "BELIEF_CREATED"
    BELIEF_UPDATED = "BELIEF_UPDATED"
    BELIEF_REJECTED = "BELIEF_REJECTED"
    INTEREST_INCREASED = "INTEREST_INCREASED"
    INTEREST_DECREASED = "INTEREST_DECREASED"
    MEMORY_CREATED = "MEMORY_CREATED"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"
    DAILY_REPORT_CREATED = "DAILY_REPORT_CREATED"


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
