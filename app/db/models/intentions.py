"""Intentions and turn feedback — the two tables that connect talk to action.

``Intention`` is the missing bridge between "a character said it would do
something" and "the Village did it". Before it existed, a line like "I'll dig
into that tonight" lived only inside a ConversationMessage: nothing carried it
out of the room, nothing reminded the speaker later, and nothing could check
whether it ever happened. An intention is a first-class, agent-owned row with
its own lifecycle (app.domain.enums.IntentionStatus), formed only by an
agent's own decision and closed only by a later, separately validated and
executed action — never by the agent merely claiming it is done.

``AgentFeedback`` is the self-improvement channel. The engine already knew,
turn by turn, when something went wrong (a rejected decision, a promise said
aloud but never recorded, a cited memory that was never shown) — but it threw
that knowledge away after at most one same-turn correction attempt. A
feedback row persists it as a short *factual* note about the agent's own
record, shown on that agent's next activation, and records whether the next
decision actually addressed it. Notes describe what happened; they never tell
an agent to be more active (Director constitution §3).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK
from app.domain.enums import IntentionStatus


class Intention(TimestampMixin, Base):
    """Something one agent said it would do."""

    __tablename__ = "intentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    #: The agent's own words for what it means to do.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: The concrete ActionType value that would carry this out
    #: (START_RESEARCH, POST_TO_WALL, SEND_MESSAGE, ...). Plain string, like
    #: every other lifecycle column here — SQLite never enforces enum members.
    planned_action: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Who it was said to / who it involves, if anyone.
    with_agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(AGENT_FK), nullable=True
    )
    status: Mapped[IntentionStatus] = mapped_column(
        Enum(IntentionStatus, name="intention_status"),
        nullable=False,
        default=IntentionStatus.OPEN,
    )

    #: Where it came from — the conversation it was said in, if any.
    source_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    source_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_sim_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: Absolute period index (day * periods_per_day + period position) — what
    #: expiry is measured against, so a window can span day boundaries.
    created_period_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: How it ended.
    closed_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_sim_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: For FULFILLED: the ActionType actually executed, and whether the agent
    #: linked it explicitly (fulfills_intention_id) or the engine matched it
    #: by planned_action. Both are recorded so a proof can tell them apart.
    fulfilled_by_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fulfilled_explicitly: Mapped[bool | None] = mapped_column(nullable=True)
    #: The entity the fulfilling action produced or touched, as
    #: {"type": ..., "id": ...} — e.g. a research_id or wall post id.
    fulfilled_entity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentFeedback(TimestampMixin, Base):
    """One factual note about an agent's own recent turn."""

    __tablename__ = "agent_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    #: A stable machine label (see app.services.turn_feedback.KINDS).
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    source_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Extra machine-readable detail (e.g. the intention id, the rejected
    #: reason) — used to judge whether a later turn addressed this note.
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Set once the agent's next decision after seeing this note is judged.
    #: True = the issue did not recur / was acted on; False = it recurred.
    addressed: Mapped[bool | None] = mapped_column(nullable=True)
    judged_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
