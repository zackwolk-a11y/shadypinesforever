"""Assembling what an agent is allowed to know right now.

The builder owns the token budget. Services do not append whatever they happen
to have: each slot has a cap, and the total is bounded by design.

It is also where partial knowledge is enforced. An agent sees wall *headlines*,
not everyone's findings; unread messages addressed to it, not everyone's mail.
The wall is shared infrastructure, not telepathy.

Packet 6 adds one more enforcement point: every id an agent might act on —
a wall post, a rabbit hole, a claim, a belief — is rendered with its real
database id inline (``[12]``), the same convention Packet 5 established for
research passages. An agent can only ever reference something it was actually
shown here; it can't invent an id and have the action succeed.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agents import Agent, AgentBelief, AgentInterest
from app.db.models.conversations import Conversation, ConversationMessage, Message
from app.db.models.events import Event
from app.db.models.memory import Memory
from app.db.models.rabbit_holes import RabbitHole, RabbitHoleMember
from app.db.models.research import ResearchFinding, ResearchSession
from app.db.models.research_provenance import Claim
from app.db.models.wall import ResearchWallPost
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock
from app.domain.enums import EventType, RabbitHoleStatus
from app.services import founder, wall
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

The Research Wall, Rabbit Holes, and your beliefs work the same way: POST_TO_WALL,
CREATE_RABBIT_HOLE, JOIN_RABBIT_HOLE, CONTRIBUTE_TO_RABBIT_HOLE,
CHALLENGE_CLAIM, FORM_BELIEF, REVISE_BELIEF and friends only work against real
ids shown to you below (in [brackets]) — never invent one. Disagreement is
welcome and normal between friends: challenge a claim because you have a real
reason to doubt it, not to create conflict. Agreement should be as easy to
reach as disagreement — don't manufacture either one.

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
        .order_by(AgentInterest.strength.desc(), AgentInterest.id.desc())
        .limit(6)
    ).all()

    memories = session.scalars(
        select(Memory)
        .where(Memory.agent_id == agent.agent_id)
        .order_by(Memory.created_at.desc(), Memory.id.desc())
        .limit(settings.max_context_memories)
    ).all()

    # Headlines only — reading the wall in detail is an action, not a freebie.
    # A stable id tiebreaker matters here specifically: two posts created in
    # the same wall-clock instant (routine at fixture speed) would otherwise
    # tie on created_at, and which one survives the LIMIT would depend on
    # SQLite's arbitrary tie-break rather than being reproducible run to run.
    headlines = session.scalars(
        select(ResearchWallPost)
        .order_by(ResearchWallPost.created_at.desc(), ResearchWallPost.id.desc())
        .limit(settings.max_context_wall_headlines)
    ).all()

    read_post_ids = exposed_entity_ids(session, agent.agent_id, "research_wall")
    read_posts = [h for h in headlines if str(h.id) in read_post_ids]

    cross_pollination = wall.find_cross_pollination_candidate(session, agent.agent_id)

    unread = session.scalars(
        select(Message)
        .where(Message.recipient_agent_id == agent.agent_id, Message.read_at.is_(None))
        .order_by(Message.created_at.desc(), Message.id.desc())
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
        .order_by(ResearchFinding.created_at.desc(), ResearchFinding.id.desc())
        .limit(settings.max_context_recent_findings)
    ).all()
    own_sessions = session.scalars(
        select(ResearchSession)
        .where(ResearchSession.agent_id == agent.agent_id)
        .order_by(ResearchSession.created_at.desc(), ResearchSession.id.desc())
        .limit(settings.max_context_recent_findings)
    ).all()
    recent_questions = [rs.question for rs in own_sessions]
    own_research_ids = [rs.research_id for rs in own_sessions]
    own_claims: list[Claim] = (
        session.scalars(
            select(Claim)
            .where(Claim.research_session_id.in_(own_research_ids))
            .order_by(Claim.created_at.desc(), Claim.id.desc())
            .limit(settings.max_context_recent_findings)
        ).all()
        if own_research_ids
        else []
    )

    # Challenges to this agent's own claims — the concrete hook for revising a
    # belief in response to someone else's disagreement (§ cross-pollination).
    own_claim_ids = [str(c.id) for c in own_claims]
    challenges = (
        session.scalars(
            select(Event)
            .where(Event.event_type == EventType.CLAIM_CHALLENGED, Event.entity_id.in_(own_claim_ids))
            .order_by(Event.id.desc())
            .limit(5)
        ).all()
        if own_claim_ids
        else []
    )

    # Other agents' claims this agent has real exposure to (via reading a wall
    # post or joining a rabbit hole whose research got shared) — the only
    # legitimate source of a claim id for CHALLENGE_CLAIM or a claim-grounded
    # REVISE_BELIEF. Never another agent's claim the agent hasn't earned.
    exposed_claim_ids = exposed_entity_ids(session, agent.agent_id, "claim") - set(own_claim_ids)
    others_claims: list[Claim] = (
        session.scalars(
            select(Claim)
            .where(Claim.id.in_([int(i) for i in exposed_claim_ids]))
            .order_by(Claim.created_at.desc(), Claim.id.desc())
            .limit(6)
        ).all()
        if exposed_claim_ids
        else []
    )
    others_claim_owners = {
        rs.research_id: rs.agent_id
        for rs in session.scalars(
            select(ResearchSession).where(
                ResearchSession.research_id.in_({c.research_session_id for c in others_claims})
            )
        )
    } if others_claims else {}

    own_beliefs = session.scalars(
        select(AgentBelief)
        .where(AgentBelief.agent_id == agent.agent_id)
        .order_by(AgentBelief.updated_at.desc().nulls_last(), AgentBelief.created_at.desc())
        .limit(6)
    ).all()

    member_hole_ids = set(
        session.scalars(
            select(RabbitHoleMember.rabbit_hole_id).where(
                RabbitHoleMember.agent_id == agent.agent_id, RabbitHoleMember.left_at.is_(None)
            )
        )
    )
    open_holes = session.scalars(
        select(RabbitHole)
        .where(RabbitHole.status.notin_([RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED]))
        .order_by(RabbitHole.last_activity.desc().nulls_last(), RabbitHole.id.desc())
        .limit(6)
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
            f"  [{h.id}] [{h.post_type.value}] {h.agent_id}: {_clip(h.content, 120)}"
            for h in headlines
        ]
    if read_posts:
        lines.append("WALL POSTS YOU HAVE READ IN FULL:")
        lines += [
            f"  [{h.id}] [{h.post_type.value}] {h.agent_id}: {_clip(h.content, 220)}"
            + (f" (research: {h.related_research_id})" if h.related_research_id else "")
            for h in read_posts
        ]
    if cross_pollination is not None:
        post, overlap = cross_pollination
        lines.append(
            f"YOU MAY FIND THIS RELEVANT — [{post.id}] {post.agent_id} posted "
            f"({', '.join(sorted(overlap))}): {_clip(post.content, 160)}"
        )
    if unread:
        lines.append("UNREAD MESSAGES:")
        lines += [f"  - from {m.sender_agent_id}: {_clip(m.content, 160)}" for m in unread]
    if own_sessions:
        lines.append(
            "YOUR RESEARCH SESSIONS (research_id — usable as target_research_id "
            "for FORM_BELIEF, CREATE_RABBIT_HOLE, POST_TO_WALL, CONTRIBUTE_TO_RABBIT_HOLE):"
        )
        lines += [
            f"  {rs.research_id} ({rs.status.value}): {_clip(rs.question, 120)}"
            for rs in own_sessions
        ]
    if own_findings:
        lines.append("YOUR PREVIOUS FINDINGS:")
        lines += [
            f"  - [{f.classification.value}] {_clip(f.finding_text, 160)}" for f in own_findings
        ]
    if recent_questions:
        lines.append("QUESTIONS YOU HAVE ALREADY RESEARCHED:")
        lines += [f"  - {_clip(q, 140)}" for q in recent_questions]
    if own_claims:
        lines.append("YOUR RECENT CLAIMS (usable as basis for FORM_BELIEF/REVISE_BELIEF):")
        lines += [
            f"  [{c.id}] [{c.classification.value}] {_clip(c.claim_text, 140)}" for c in own_claims
        ]
    if others_claims:
        lines.append("CLAIMS FROM OTHERS' RESEARCH YOU'VE SEEN (usable for CHALLENGE_CLAIM):")
        lines += [
            f"  [{c.id}] [{c.classification.value}] "
            f"{others_claim_owners.get(c.research_session_id, '?')}: {_clip(c.claim_text, 140)}"
            for c in others_claims
        ]
    if challenges:
        lines.append("CHALLENGES TO YOUR CLAIMS:")
        lines += [
            f"  - {c.agent_id} challenged claim [{c.payload.get('claim_id')}]: "
            f"{_clip(c.payload.get('argument', ''), 160)}"
            for c in challenges
        ]
    if own_beliefs:
        lines.append("YOUR BELIEFS:")
        lines += [
            f"  [{b.id}] ({b.status.value}, confidence={b.confidence:.0f}) {_clip(b.statement, 140)}"
            for b in own_beliefs
        ]
    if open_holes:
        lines.append("OPEN RABBIT HOLES:")
        lines += [
            f"  [{h.id}] {'(you are in this one) ' if h.id in member_hole_ids else ''}"
            f"\"{h.title}\" status={h.status.value} heat={h.activity_level:.0f}"
            for h in open_holes
        ]

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
