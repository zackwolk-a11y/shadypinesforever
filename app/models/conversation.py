"""Conversations, their turns, and direct agent-to-agent messages (§12, §17)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, utcnow
from app.models.agent import AGENT_FK


class ConversationTrigger(str, enum.Enum):
    """Why a conversation started at all (§12)."""

    RESEARCH_SHARING = "RESEARCH_SHARING"
    WALL_ACTIVITY = "WALL_ACTIVITY"
    DISAGREEMENT = "DISAGREEMENT"
    SIMILAR_DISCOVERY = "SIMILAR_DISCOVERY"
    MORNING_GATHERING = "MORNING_GATHERING"
    RANDOM_SOCIAL = "RANDOM_SOCIAL"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"


class ConversationStatus(str, enum.Enum):
    """Whether a conversation is still running."""

    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class Conversation(Base):
    """A multi-agent exchange. ``participant_ids`` is a JSON list of ``agent_id``."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_type: Mapped[ConversationTrigger] = mapped_column(
        Enum(ConversationTrigger, name="conversation_trigger"), nullable=False
    )
    participant_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status"),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )


class ConversationMessage(TimestampMixin, Base):
    """One turn inside a conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True, nullable=False
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Message(TimestampMixin, Base):
    """A direct ``send_message`` from one agent to another.

    Distinct from :class:`ConversationMessage`: this is point-to-point (or a
    broadcast when ``recipient_agent_id`` is NULL) and is not a turn in any
    conversation.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    recipient_agent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
