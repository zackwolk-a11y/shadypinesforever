"""Assembling what an agent is allowed to know right now.

The builder owns the token budget. Services do not append whatever they happen
to have: each slot has a cap, and the total is bounded by design.

It is also where partial knowledge is enforced. An agent sees wall *headlines*,
not everyone's findings; unread messages addressed to it, not everyone's mail.
The wall is shared infrastructure, not telepathy.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agents import Agent, AgentInterest
from app.db.models.conversations import Message
from app.db.models.memory import Memory
from app.db.models.wall import ResearchWallPost
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock

SYSTEM_PROMPT = """You are one inhabitant of a small research clubhouse shared with seven friends.

You are a friend, not an employee. Nobody assigns you work. You may follow a
curiosity, talk to someone, listen, or do nothing at all — silence is a normal
and valid choice.

Return one decision. Do not narrate your reasoning. Only use the actions listed
in AVAILABLE ACTIONS; anything else will be rejected."""


@dataclass(frozen=True)
class AgentContext:
    """The rendered prompt for one activation, plus what went into it."""

    system: str
    user: str
    agent_id: str
    present_agent_ids: tuple[str, ...]
    #: Messages actually shown to the agent this turn. The caller marks them
    #: read: putting a message in the context *is* delivering it, and a message
    #: that stays unread would keep boosting this agent's activation score
    #: forever, letting one inbox monopolise the Village.
    delivered_messages: tuple = ()

    @property
    def approx_tokens(self) -> int:
        return (len(self.system) + len(self.user)) // 4


def build_agent_context(
    session: Session,
    agent: Agent,
    clock: SimulationClock,
    settings: Settings,
    *,
    available_actions: tuple[str, ...],
) -> AgentContext:
    """Render the bounded context for one agent's turn."""
    interests = session.scalars(
        select(AgentInterest)
        .where(AgentInterest.agent_id == agent.agent_id)
        .order_by(AgentInterest.strength.desc())
        .limit(6)
    ).all()

    memories = session.scalars(
        select(Memory)
        .where(Memory.agent_id == agent.agent_id)
        .order_by(Memory.created_at.desc())
        .limit(settings.max_context_memories)
    ).all()

    # Headlines only — reading the wall in detail is an action, not a freebie.
    headlines = session.scalars(
        select(ResearchWallPost)
        .order_by(ResearchWallPost.created_at.desc())
        .limit(settings.max_context_wall_headlines)
    ).all()

    unread = session.scalars(
        select(Message)
        .where(Message.recipient_agent_id == agent.agent_id, Message.read_at.is_(None))
        .order_by(Message.created_at.desc())
        .limit(5)
    ).all()

    present = tuple(
        session.scalars(
            select(Agent.agent_id)
            .where(Agent.agent_id != agent.agent_id)
            .order_by(Agent.id)
        )
    )

    lines = [
        f"AGENT_ID: {agent.agent_id}",
        f"IDENTITY: {agent.identity}",
        f"VOICE: {agent.voice}",
        f"DAY: {clock.current_day}  PERIOD: {clock.current_period}",
        f"LOCATION: {agent.current_location or 'unspecified'}",
        f"INTERESTS: {'; '.join(i.interest for i in interests) or 'none recorded'}",
        f"PRESENT: {', '.join(present) or 'nobody else'}",
        f"LOCATIONS: {', '.join(CLUBHOUSE_LOCATIONS)}",
        f"AVAILABLE ACTIONS: {', '.join(available_actions)}",
    ]

    if memories:
        lines.append("RECENT MEMORIES:")
        lines += [f"  - {_clip(m.content, 160)}" for m in memories]
    if headlines:
        lines.append("RESEARCH WALL HEADLINES (you have not read these in full):")
        lines += [
            f"  - [{h.post_type.value}] {h.agent_id}: {_clip(h.content, 120)}" for h in headlines
        ]
    if unread:
        lines.append("UNREAD MESSAGES:")
        lines += [f"  - from {m.sender_agent_id}: {_clip(m.content, 160)}" for m in unread]

    return AgentContext(
        system=SYSTEM_PROMPT,
        user="\n".join(lines),
        agent_id=agent.agent_id,
        present_agent_ids=present,
        delivered_messages=tuple(unread),
    )


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
