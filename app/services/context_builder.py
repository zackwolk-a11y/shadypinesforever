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
from app.db.models.conversations import Conversation, ConversationMessage
from app.db.models.research import ResearchFinding, ResearchSession
from app.db.models.wall import ResearchWallPost
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock
from app.services import founder
from app.services.exposure import exposed_entity_ids

SYSTEM_PROMPT = """You are one inhabitant of a small research clubhouse shared with seven friends.

You are a friend, not an employee. Nobody assigns you work. You may follow a
curiosity, talk to someone, listen, or do nothing at all — silence is a normal
and valid choice.

If you choose START_RESEARCH, put your own question in `content` — something
that actually follows from your interests, your memories, what's been said
around you, or what you've found before, not a generic prompt. The village
will search for real sources and show you what it finds; you will interpret
them in a separate step. You will never be asked to pretend you searched.

Return one decision. Do not narrate your reasoning. Only use the actions listed
in AVAILABLE ACTIONS; anything else will be rejected."""


@dataclass(frozen=True)
class AgentContext:
    """The rendered prompt for one activation, plus what went into it."""

    system: str
    user: str
    agent_id: str
    present_agent_ids: tuple[str, ...]
    #: The open conversation this agent is a participant in, if any.
    conversation_id: int | None = None
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
    conversation: Conversation | None = None,
) -> AgentContext:
    """Render the bounded context for one agent's turn.

    Everything social in here is filtered through exposure: conversation turns
    the agent was present for, founder messages delivered to it, its own unread
    mail. The wall contributes headlines only — enough to make something
    discoverable, never enough to make it known.
    """
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

    # An agent's own past findings and questions — the fourth input the build
    # bible asks a research question to be grounded in, alongside interests,
    # memories, and wall activity. Only this agent's own research: findings
    # are not automatically shared, so nothing here comes from anyone else.
    own_findings = session.scalars(
        select(ResearchFinding)
        .join(ResearchSession, ResearchFinding.research_session_id == ResearchSession.research_id)
        .where(ResearchSession.agent_id == agent.agent_id)
        .order_by(ResearchFinding.created_at.desc())
        .limit(settings.max_context_recent_findings)
    ).all()
    recent_questions = session.scalars(
        select(ResearchSession.question)
        .where(ResearchSession.agent_id == agent.agent_id)
        .order_by(ResearchSession.created_at.desc())
        .limit(settings.max_context_recent_findings)
    ).all()

    present = tuple(
        session.scalars(
            select(Agent.agent_id)
            .where(Agent.agent_id != agent.agent_id)
            .order_by(Agent.id)
        )
    )

    founder_messages = founder.messages_for(session, agent.agent_id)

    conversation_turns: list[ConversationMessage] = []
    if conversation is not None:
        visible = exposed_entity_ids(session, agent.agent_id, "conversation_message")
        conversation_turns = [
            turn
            for turn in session.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.turn_number.desc())
                .limit(settings.max_conversation_turns)
            )
            if str(turn.id) in visible
        ][::-1]

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

    if conversation is not None:
        others = [p for p in (conversation.participant_ids or []) if p != agent.agent_id]
        lines.append(
            f"YOU ARE IN A CONVERSATION ({conversation.trigger_type.value}) with: "
            f"{', '.join(others) or 'nobody left'}"
        )
        if conversation_turns:
            lines.append("WHAT HAS BEEN SAID:")
            lines += [
                f"  {t.turn_number}. {t.agent_id}: {_clip(t.content, 200)}"
                for t in conversation_turns
            ]
        else:
            lines.append("Nothing has been said yet.")
        lines.append(
            "You may SPEAK, LEAVE_CONVERSATION, or say nothing at all. "
            "Saying nothing is a normal choice."
        )

    if founder_messages:
        lines.append("FROM THE FOUNDER:")
        lines += [f"  - {_clip(m.content, 200)}" for m in founder_messages]

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
    if own_findings:
        lines.append("YOUR PREVIOUS FINDINGS:")
        lines += [
            f"  - [{f.classification.value}] {_clip(f.finding_text, 160)}" for f in own_findings
        ]
    if recent_questions:
        lines.append("QUESTIONS YOU HAVE ALREADY RESEARCHED:")
        lines += [f"  - {_clip(q, 140)}" for q in recent_questions]

    return AgentContext(
        system=SYSTEM_PROMPT,
        user="\n".join(lines),
        agent_id=agent.agent_id,
        present_agent_ids=present,
        conversation_id=conversation.id if conversation is not None else None,
        delivered_messages=tuple(unread),
    )


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
