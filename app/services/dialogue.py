"""Dialogue mechanics: why a conversation starts, who else might join, what
makes one worth remembering, and how it moves a relationship (Packet 8).

Everything here follows the same split the rest of the codebase draws
everywhere else: the *content* of what an agent says is always the model's
(fixture or live) — never generated here — but *why* a conversation started,
*whether* an outsider has a real reason to join, *whether* this exchange was
significant enough to remember, and *how much* it moved a relationship are
all computed from real database state, the same "mechanism, not content"
discipline as rabbit-hole heat or belief-revision arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agents import Agent, AgentInterest, Relationship
from app.db.models.conversations import Conversation, ConversationMessage
from app.db.models.events import Event
from app.db.models.rabbit_holes import RabbitHoleMember
from app.db.models.research import ResearchSession
from app.db.models.world import SimulationClock
from app.domain.enums import ConversationTrigger, EventType
from app.domain.moves import (  # noqa: F401 — re-exported for callers that used to get these from here
    MOVE_ADMIT_UNCERTAINTY,
    MOVE_ANECDOTE,
    MOVE_ANSWER,
    MOVE_CHALLENGE,
    MOVE_CHANGE_SUBJECT,
    MOVE_CLARIFY,
    MOVE_CONNECT,
    MOVE_EXTEND,
    MOVE_JOKE,
    MOVE_OPEN,
    MOVE_PROPOSE_RESEARCH,
    MOVE_QUESTION,
    SALIENT_MOVES as _SALIENT_MOVES,
)
from app.services.exposure import exposed_entity_ids
from app.services.wall import keywords

#: A spontaneous conversation stays small — mirrors
#: conversations.MAX_SPONTANEOUS_PARTICIPANTS; a joiner is only offered a
#: turn while there's room.
MAX_SPONTANEOUS_PARTICIPANTS = 5


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def relationship_between(session: Session, a: str, b: str) -> Relationship | None:
    x, y = pair_key(a, b)
    return session.scalars(
        select(Relationship).where(Relationship.agent_a_id == x, Relationship.agent_b_id == y)
    ).first()


def shared_interest_overlap(session: Session, a: str, b: str) -> set[str]:
    """Keyword overlap between two agents' current interests — computed
    fresh every time (never stored), so it can never go stale the way a
    snapshot column would the moment either agent's interests move."""
    a_words: set[str] = set()
    b_words: set[str] = set()
    for row in session.scalars(select(AgentInterest).where(AgentInterest.agent_id == a)):
        a_words |= keywords(row.interest)
    for row in session.scalars(select(AgentInterest).where(AgentInterest.agent_id == b)):
        b_words |= keywords(row.interest)
    return a_words & b_words


@dataclass(frozen=True)
class InitiationReason:
    trigger: ConversationTrigger
    reason: str
    subject: str
    related_research_id: str | None = None
    related_wall_post_id: int | None = None
    related_rabbit_hole_id: int | None = None
    related_memory_id: int | None = None


def pick_trigger(session: Session, initiator_id: str, target_id: str, clock: SimulationClock) -> InitiationReason:
    """Why ``initiator_id`` has a real reason to start talking to
    ``target_id`` right now, checked in priority order against actual
    database state — never a hardcoded default. Falls all the way through to
    RANDOM_SOCIAL only when nothing more specific is true, which is itself a
    legitimate, common reason (§ "they simply have a social reason to talk").
    """
    # 1. A live disagreement between them — the strongest, most specific
    # reason two people would seek each other out.
    challenge = _recent_challenge_between(session, initiator_id, target_id)
    if challenge is not None:
        return InitiationReason(
            trigger=ConversationTrigger.DISAGREEMENT,
            reason=f"a claim was challenged between {initiator_id} and {target_id}",
            subject=challenge,
        )

    # 2. A rabbit hole they're both currently in.
    shared_hole = _shared_active_rabbit_hole(session, initiator_id, target_id)
    if shared_hole is not None:
        hole_id, title = shared_hole
        return InitiationReason(
            trigger=ConversationTrigger.RABBIT_HOLE,
            reason=f"both following the rabbit hole \"{title}\"",
            subject=title,
            related_rabbit_hole_id=hole_id,
        )

    # 3. The initiator has completed research it hasn't shared with anyone.
    own_research = _unshared_completed_research(session, initiator_id)
    if own_research is not None:
        research_id, question = own_research
        return InitiationReason(
            trigger=ConversationTrigger.RESEARCH_SHARING,
            reason=f"{initiator_id} has research on \"{question}\" to share",
            subject=question,
            related_research_id=research_id,
        )

    # 4. A memory that specifically concerns the target — "remember a
    # previous conversation".
    memory_hit = _memory_about(session, initiator_id, target_id, clock)
    if memory_hit is not None:
        memory_id, content = memory_hit
        return InitiationReason(
            trigger=ConversationTrigger.MEMORY_PROMPTED,
            reason=f"{initiator_id} remembered something involving {target_id}",
            subject=content[:80],
            related_memory_id=memory_id,
        )

    # 5. A wall post the initiator read that cites the target's research.
    wall_hit = _wall_connection(session, initiator_id, target_id)
    if wall_hit is not None:
        post_id, subject = wall_hit
        return InitiationReason(
            trigger=ConversationTrigger.WALL_ACTIVITY,
            reason=f"{initiator_id} read {target_id}'s wall post",
            subject=subject,
            related_wall_post_id=post_id,
        )

    # 6. Genuine, real overlap in what they're each curious about.
    overlap = shared_interest_overlap(session, initiator_id, target_id)
    if overlap:
        subject = sorted(overlap)[0]
        return InitiationReason(
            trigger=ConversationTrigger.SIMILAR_DISCOVERY,
            reason=f"{initiator_id} and {target_id} share an interest in {subject}",
            subject=subject,
        )

    # 7. Nothing specific — still a legitimate reason to talk.
    return InitiationReason(
        trigger=ConversationTrigger.RANDOM_SOCIAL,
        reason=f"{initiator_id} ran into {target_id} in the clubhouse",
        subject="the day so far",
    )


def _recent_challenge_between(session: Session, a: str, b: str) -> str | None:
    events = session.scalars(
        select(Event)
        .where(Event.event_type == EventType.CLAIM_CHALLENGED)
        .order_by(Event.id.desc())
        .limit(30)
    ).all()
    for event in events:
        challenger = event.agent_id
        research_id = event.payload.get("research_session_id")
        owner = session.scalars(
            select(ResearchSession.agent_id).where(ResearchSession.research_id == research_id)
        ).first()
        if {challenger, owner} == {a, b}:
            return event.payload.get("claim_text", "a claim")
    return None


def _shared_active_rabbit_hole(session: Session, a: str, b: str) -> tuple[int, str] | None:
    from app.db.models.rabbit_holes import RabbitHole
    from app.domain.enums import RabbitHoleStatus

    a_holes = set(
        session.scalars(
            select(RabbitHoleMember.rabbit_hole_id).where(
                RabbitHoleMember.agent_id == a, RabbitHoleMember.left_at.is_(None)
            )
        )
    )
    b_holes = set(
        session.scalars(
            select(RabbitHoleMember.rabbit_hole_id).where(
                RabbitHoleMember.agent_id == b, RabbitHoleMember.left_at.is_(None)
            )
        )
    )
    for hole_id in sorted(a_holes & b_holes):
        hole = session.get(RabbitHole, hole_id)
        if hole is not None and hole.status not in (RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED):
            return hole_id, hole.title
    return None


def _unshared_completed_research(session: Session, agent_id: str) -> tuple[str, str] | None:
    from app.domain.enums import ResearchStatus
    from app.db.models.wall import ResearchWallPost

    shared_ids = set(
        session.scalars(
            select(ResearchWallPost.related_research_id).where(
                ResearchWallPost.agent_id == agent_id, ResearchWallPost.related_research_id.isnot(None)
            )
        )
    )
    session_row = session.scalars(
        select(ResearchSession)
        .where(
            ResearchSession.agent_id == agent_id,
            ResearchSession.status == ResearchStatus.COMPLETED,
        )
        .order_by(ResearchSession.created_at.desc(), ResearchSession.id.desc())
        .limit(5)
    ).first()
    if session_row is None or session_row.research_id in shared_ids:
        return None
    return session_row.research_id, session_row.question


def _memory_about(session: Session, agent_id: str, other_id: str, clock: SimulationClock) -> tuple[int, str] | None:
    from app.services import memory as memory_service
    from app.domain.enums import MemoryType

    hits = memory_service.retrieve_relevant(
        session, agent_id, clock=clock, limit=1, exclude_types={MemoryType.PROJECT},
        related_agent_ids=(other_id,), require_related_agent=True, mark_recalled=False,
    )
    if not hits:
        return None
    return hits[0].id, hits[0].content


def _wall_connection(session: Session, agent_id: str, other_id: str) -> tuple[int, str] | None:
    from app.db.models.wall import ResearchWallPost

    read_ids = exposed_entity_ids(session, agent_id, "research_wall")
    if not read_ids:
        return None
    posts = session.scalars(
        select(ResearchWallPost)
        .where(ResearchWallPost.agent_id == other_id, ResearchWallPost.id.in_([int(i) for i in read_ids]))
        .order_by(ResearchWallPost.id.desc())
        .limit(1)
    ).first()
    if posts is None:
        return None
    return posts.id, posts.content[:80]


@dataclass(frozen=True)
class JoinCandidate:
    agent_id: str
    reason: str


def find_joiner(
    session: Session,
    conversation: Conversation,
    clock: SimulationClock,
    settings: Settings,
    *,
    seed: str = "",
) -> JoinCandidate | None:
    """The best real reason an outsider currently in the clubhouse has to
    join this conversation, if any clears a minimal bar. Never returns
    someone without a concrete reason (§ "joining requires a reason") —
    proximity alone is not one."""
    import hashlib
    import random

    if conversation.trigger_type == ConversationTrigger.MORNING_GATHERING:
        return None  # already everyone
    if len(conversation.participant_ids or []) >= MAX_SPONTANEOUS_PARTICIPANTS:
        return None

    in_room = set(conversation.participant_ids or [])
    already_departed = set(conversation.departed_agent_ids or [])
    subject_words = keywords(conversation.current_subject or "")

    best: JoinCandidate | None = None
    best_score = 0.0
    for agent_id in session.scalars(select(Agent.agent_id).order_by(Agent.id)):
        if agent_id in in_room or agent_id in already_departed:
            continue
        score = 0.0
        reasons: list[str] = []

        interest_words: set[str] = set()
        for row in session.scalars(select(AgentInterest).where(AgentInterest.agent_id == agent_id)):
            interest_words |= keywords(row.interest)
        overlap = interest_words & subject_words
        if overlap:
            score += 2.0 * len(overlap)
            reasons.append(f"interested in {sorted(overlap)[0]}")

        for participant in in_room:
            rel = relationship_between(session, agent_id, participant)
            if rel is not None and rel.trust_score >= 65.0:
                score += 1.0
                reasons.append(f"close with {participant}")
                break

        if score <= 0:
            continue

        rng = random.Random(
            hashlib.sha256(f"{seed}|joiner|{conversation.id}|{agent_id}|{clock.current_day}".encode()).hexdigest()[:16]
        )
        score += rng.random()  # deterministic tie-break jitter, not the deciding factor
        if score > best_score:
            best_score = score
            best = JoinCandidate(agent_id=agent_id, reason=reasons[0])

    return best if best_score >= 2.0 else None


def is_repetitive(session: Session, agent_id: str, content: str, *, window: int = 3) -> bool:
    """Guards against an agent repeating its own recent phrasing verbatim —
    not a topic ban (returning to a topic is fine, see the module docs),
    just exact near-duplicate wording."""
    normalized = _normalize(content)
    if not normalized:
        return False
    recent = session.scalars(
        select(ConversationMessage.content)
        .where(ConversationMessage.agent_id == agent_id)
        .order_by(ConversationMessage.id.desc())
        .limit(window)
    ).all()
    return any(_normalize(r) == normalized for r in recent)


_BANNED_OPENERS = (
    "that's fascinating",
    "great point",
    "i completely agree",
    "let's explore that",
    "this raises an interesting question",
)


def has_generic_filler_opener(content: str) -> bool:
    normalized = _normalize(content)
    return any(normalized.startswith(opener) for opener in _BANNED_OPENERS)


def recent_pairing_count(session: Session, participant_ids: list[str], clock: SimulationClock, *, days: int = 1) -> int:
    """How many conversations this exact set of people has already had very
    recently — a soft signal (used by the scheduler's activation score), not
    a hard block, since two friends legitimately do talk more than once."""
    pair = frozenset(participant_ids)
    count = 0
    for convo_row in session.scalars(
        select(Conversation).where(Conversation.started_sim_day >= clock.current_day - days)
    ):
        if frozenset(convo_row.participant_ids or []) == pair:
            count += 1
    return count


def conversation_worthy(session: Session, conversation: Conversation) -> tuple[bool, str]:
    """Whether this conversation clears the bar for a memory (§ "meaningful
    conversations should be candidates ... do NOT store every utterance").
    Returns the reason too, so the memory content can say *why* it mattered
    rather than just that it happened.
    """
    n_turns = len(
        session.execute(
            select(ConversationMessage.id).where(ConversationMessage.conversation_id == conversation.id)
        ).all()
    )

    if conversation.trigger_type in (
        ConversationTrigger.DISAGREEMENT, ConversationTrigger.RABBIT_HOLE, ConversationTrigger.MEMORY_PROMPTED,
    ):
        return True, f"conversation triggered by {conversation.trigger_type.value.lower()}"
    if (
        conversation.related_research_ids or conversation.related_wall_post_ids
        or conversation.related_rabbit_hole_ids
    ):
        return True, "conversation connected to real research/wall/rabbit-hole activity"

    moves = _moves_used(session, conversation)
    if moves & _SALIENT_MOVES:
        return True, f"a salient moment occurred ({', '.join(sorted(moves & _SALIENT_MOVES))})"

    if n_turns >= 5:
        return True, "an unusually long conversation"

    return False, ""


def _moves_used(session: Session, conversation: Conversation) -> set[str]:
    events = session.scalars(
        select(Event).where(
            Event.event_type == EventType.CONVERSATION_MESSAGE,
            Event.correlation_id == conversation.correlation_id,
        )
    ).all()
    return {e.payload.get("move") for e in events if e.payload.get("move")}


#: Relationship deltas — small and capped, matching every other mechanical
#: delta in this codebase (beliefs.py, interests.py).
_FAMILIARITY_DELTA = 2.0
_INTELLECTUAL_AFFINITY_DELTA = 3.0
_MAX_DIMENSION = 100.0


def update_relationship_dimensions(session: Session, conversation: Conversation, clock: SimulationClock) -> None:
    """Called once, at conversation end: every pair of participants who
    actually spoke gets a small familiarity bump; a real disagreement that
    ran its course (§ "productive disagreement") or a shared-interest thread
    additionally nudges intellectual_affinity — never trust_score, which
    Packet 7's conversation-touch path already handles per-exchange.
    """
    everyone = list(dict.fromkeys(
        [*(conversation.participant_ids or []), *(conversation.departed_agent_ids or [])]
    ))
    n_turns = len(
        session.execute(
            select(ConversationMessage.id).where(ConversationMessage.conversation_id == conversation.id)
        ).all()
    )
    is_disagreement = conversation.trigger_type is ConversationTrigger.DISAGREEMENT
    is_intellectual = conversation.trigger_type in (
        ConversationTrigger.DISAGREEMENT, ConversationTrigger.SIMILAR_DISCOVERY,
        ConversationTrigger.RESEARCH_SHARING, ConversationTrigger.RABBIT_HOLE,
    )

    for i, a in enumerate(everyone):
        for b in everyone[i + 1:]:
            x, y = pair_key(a, b)
            rel = session.scalars(
                select(Relationship).where(Relationship.agent_a_id == x, Relationship.agent_b_id == y)
            ).first()
            if rel is None:
                # Explicit values, not just the column defaults: those only
                # apply once SQLAlchemy flushes this row, but the increments
                # just below read familiarity/intellectual_affinity back
                # immediately (the same gotcha Packet 7 hit for trust_score).
                rel = Relationship(
                    agent_a_id=x, agent_b_id=y, trust_score=60.0, interaction_count=0,
                    familiarity=0.0, intellectual_affinity=50.0, productive_disagreement_count=0,
                )
                session.add(rel)
            rel.familiarity = min(_MAX_DIMENSION, rel.familiarity + _FAMILIARITY_DELTA)
            if is_intellectual and n_turns >= 2:
                rel.intellectual_affinity = min(
                    _MAX_DIMENSION, rel.intellectual_affinity + _INTELLECTUAL_AFFINITY_DELTA
                )
            if is_disagreement and n_turns >= 2:
                rel.productive_disagreement_count += 1
