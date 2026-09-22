"""Memory selection, retrieval, reinforcement and decay (Packet 7).

The whole point of this module is the gap between "something happened" and
"something worth remembering": the event log already records everything
(§18), and this module is deliberately choosier. An event becomes a memory
only when a handler here judges it likely to matter later — surprising,
repeated, socially meaningful, belief- or interest-moving, a rabbit hole
resolving or complicating, a founder message, a meaningful disagreement, or
real uncertainty. Nothing here calls a model to make that judgment: every
signal is a fact already sitting in the database (an evidence_strength, a
repeat count, a status transition), the same "mechanism, not content" split
the rest of this codebase draws for belief and rabbit-hole arithmetic.

Two places hook in:

- :func:`consider_turn_events` — called once per activation, right after
  ``execute_decision`` runs, over every event that activation's correlation_id
  produced. This is what turns research, wall, rabbit-hole, claim, and belief
  events into memories for the agent(s) they concern.
- :func:`consider_founder_delivery` — called separately, right after
  ``founder.deliver_pending``, since a founder message reaches its recipients
  before anyone is activated, outside any one agent's turn.
- :func:`consider_conversation_ended` (Packet 8) — called once, right after a
  conversation closes, but only when ``dialogue.conversation_worthy`` says
  this exchange cleared the bar — most conversations produce no memory at
  all, matching "do NOT store every utterance".

Retrieval (:func:`retrieve_relevant`) is the other half: an agent's context
never gets the whole memory table, only a small, scored slice — see the
module docstring there for the scoring itself.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models.agents import AgentBelief
from app.db.models.memory import Memory
from app.db.models.rabbit_holes import RabbitHole
from app.db.models.research import ResearchFinding, ResearchSession
from app.db.models.research_provenance import Claim
from app.db.models.reports import FounderMessage
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, EvidenceStrength, InterestOrigin, MemoryType
from app.services import interests
from app.services import rabbit_holes as rh
from app.services.events import record_event
from app.services.wall import keywords as _wall_keywords

#: Importance by evidence_strength when a research session completes — a
#: strong or genuinely conflicting result is more worth remembering than a
#: thin one. Sessions that come back both weak *and* empty of findings are
#: not memory-worthy at all (see the RESEARCH_COMPLETED handler) — avoiding
#: memory spam from routine, unremarkable research.
_RESEARCH_IMPORTANCE = {
    EvidenceStrength.STRONG: 70.0,
    EvidenceStrength.MODERATE: 58.0,
    EvidenceStrength.DEVELOPING: 45.0,
    EvidenceStrength.CONFLICTING: 55.0,  # "major uncertainty" is its own signal
    EvidenceStrength.WEAK: 35.0,
    EvidenceStrength.INSUFFICIENT: 38.0,
}
_UNRESOLVED_EVIDENCE = {EvidenceStrength.CONFLICTING, EvidenceStrength.INSUFFICIENT}

#: A memory that has been surfaced this recently was not really "recalled" —
#: it is just what is already fresh in mind. Only a genuine gap (§ "old
#: memory is retrieved") is worth a MEMORY_RECALLED event, so routine display
#: in context does not spam the log.
_RECALL_LOG_GAP_DAYS = 2

#: How many recent memories of the same type count as candidates for
#: reinforcement-matching (§5). Cheap at this scale (dozens per agent over a
#: week), and avoids any JSON-containment query, which SQLite handles poorly
#: through the ORM's cross-backend JSON type.
_REINFORCE_CANDIDATE_WINDOW = 50

#: Retrieval scoring weights (§4) — importance and recency dominate, with a
#: reinforcement and a decay term, plus flat bonuses for genuinely relevant
#: entities/keywords. None of this touches a memory's importance/confidence;
#: it only decides what gets shown this turn.
_IMPORTANCE_WEIGHT = 0.4
_RECENCY_WEIGHT = 0.25
_REINFORCEMENT_WEIGHT = 0.15
_DECAY_WEIGHT = 0.1
_RELATION_BONUS = 0.5
_KEYWORD_BONUS_PER_WORD = 0.12
_REINFORCEMENT_CAP = 5.0

#: Always-eligible regardless of age — "old important memories can still be
#: recalled" (§6) rather than aging out of the retrieval window.
_HIGH_IMPORTANCE_FLOOR = 70.0
#: Otherwise, only the most recent N are even considered — keeps retrieval
#: itself bounded as an agent's memory count grows over a long run.
_RECENT_CANDIDATE_WINDOW = 150


# --------------------------------------------------------------------------
# Creation and reinforcement
# --------------------------------------------------------------------------


def _find_reinforceable(
    session: Session,
    agent_id: str,
    memory_type: MemoryType,
    *,
    rabbit_hole_id: int | None = None,
    belief_id: int | None = None,
    other_agent_id: str | None = None,
) -> Memory | None:
    """A recent memory of the same type this event should strengthen instead
    of duplicating — matched by whichever typed relation the caller cares
    about, never by comparing prose."""
    candidates = session.scalars(
        select(Memory)
        .where(Memory.agent_id == agent_id, Memory.memory_type == memory_type)
        .order_by(Memory.id.desc())
        .limit(_REINFORCE_CANDIDATE_WINDOW)
    )
    for m in candidates:
        if rabbit_hole_id is not None and rabbit_hole_id in (m.related_rabbit_hole_ids or []):
            return m
        if belief_id is not None and belief_id in (m.related_belief_ids or []):
            return m
        if other_agent_id is not None and other_agent_id in (m.related_agent_ids or []):
            return m
    return None


def _upsert(
    session: Session,
    *,
    agent_id: str,
    memory_type: MemoryType,
    content: str,
    importance: float,
    confidence: float,
    clock: SimulationClock,
    correlation_id: str | None = None,
    source_event_ids: list[int] = (),
    related_research_ids: list[str] = (),
    related_agent_ids: list[str] = (),
    related_rabbit_hole_ids: list[int] = (),
    related_belief_ids: list[int] = (),
    related_conversation_ids: list[int] = (),
    reinforce: Memory | None = None,
    replace_content: bool = False,
) -> Memory:
    """Create a new memory, or strengthen an existing one (§5).

    Reinforcement bumps ``reinforcement_count`` and nudges ``importance`` up
    (capped), refreshes the "just happened" fields, and unions in any new
    related ids/source events — it never fabricates truth: confidence is set
    fresh from what the caller observed *this time*, not inflated by streak.
    ``replace_content`` is for the rabbit-hole "running summary" memory,
    which is meant to reflect current state, not a growing log; every other
    caller leaves the original wording of what happened alone.
    """
    if reinforce is not None:
        reinforce.reinforcement_count += 1
        reinforce.importance = min(95.0, max(reinforce.importance, importance) + 3.0)
        reinforce.confidence = confidence
        reinforce.decay_score = 1.0
        reinforce.last_accessed = utcnow()
        reinforce.last_accessed_sim_day = clock.current_day
        if replace_content:
            reinforce.content = content
        reinforce.source_event_ids = sorted(set(reinforce.source_event_ids or []) | set(source_event_ids))
        reinforce.related_research_ids = sorted(set(reinforce.related_research_ids or []) | set(related_research_ids))
        reinforce.related_agent_ids = sorted(set(reinforce.related_agent_ids or []) | set(related_agent_ids))
        reinforce.related_rabbit_hole_ids = sorted(set(reinforce.related_rabbit_hole_ids or []) | set(related_rabbit_hole_ids))
        reinforce.related_belief_ids = sorted(set(reinforce.related_belief_ids or []) | set(related_belief_ids))
        reinforce.related_conversation_ids = sorted(
            set(reinforce.related_conversation_ids or []) | set(related_conversation_ids)
        )
        record_event(
            session,
            event_type=EventType.MEMORY_REINFORCED,
            agent_id=agent_id,
            payload={"memory_id": reinforce.id, "memory_type": memory_type.value,
                     "reinforcement_count": reinforce.reinforcement_count},
            entity_type="memory",
            entity_id=str(reinforce.id),
            correlation_id=correlation_id,
            clock=clock,
        )
        _nudge_reflection_pressure(session, agent_id, reinforce.importance, clock)
        return reinforce

    memory = Memory(
        agent_id=agent_id,
        memory_type=memory_type,
        content=content,
        importance=max(0.0, min(100.0, importance)),
        confidence=max(0.0, min(100.0, confidence)),
        created_sim_day=clock.current_day,
        source_event_ids=list(source_event_ids),
        related_research_ids=list(related_research_ids),
        related_agent_ids=list(related_agent_ids),
        related_rabbit_hole_ids=list(related_rabbit_hole_ids),
        related_belief_ids=list(related_belief_ids),
        related_conversation_ids=list(related_conversation_ids),
    )
    session.add(memory)
    session.flush()
    record_event(
        session,
        event_type=EventType.MEMORY_CREATED,
        agent_id=agent_id,
        payload={"memory_id": memory.id, "memory_type": memory_type.value, "importance": memory.importance},
        entity_type="memory",
        entity_id=str(memory.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    _nudge_reflection_pressure(session, agent_id, memory.importance, clock)
    return memory


def _nudge_reflection_pressure(
    session: Session, agent_id: str, importance: float, clock: SimulationClock
) -> None:
    """Every memory formed or reinforced is a candidate reflection-trigger
    signal (Packet 9, §15) — nearly every signal the spec lists ("several
    related memories accumulate", "a belief changes substantially", "a major
    Founder message arrives", ...) already flows through a memory being
    created here with an importance that reflects exactly that significance.
    Local import: app.services.reflection reads Memory/Agent rows directly
    rather than importing this module back, so this stays a one-way
    dependency despite the local import looking circular at a glance."""
    from app.services import reflection

    reflection.accumulate_pressure(session, agent_id, importance, clock)


def write_note(
    session: Session,
    agent_id: str,
    content: str,
    clock: SimulationClock,
    correlation_id: str,
    *,
    memory_type: MemoryType = MemoryType.EPISODIC,
) -> Memory:
    """WRITE_NOTE: the agent explicitly decided this is worth remembering.

    No worthiness judgment applies here — the agent's own choice to write it
    down *is* the signal, the same way a founder message needs no scoring.
    """
    return _upsert(
        session, agent_id=agent_id, memory_type=memory_type, content=content,
        importance=45.0, confidence=90.0, clock=clock, correlation_id=correlation_id,
    )


def _rabbit_hole_summary(session: Session, hole: RabbitHole) -> str:
    """A compact, current snapshot of a rabbit hole — regenerated fresh each
    time an agent's PROJECT memory of it is touched, rather than an
    append-only log. This is what lets returning to a dormant hole recall
    "why it started, what evidence exists, ... their own previous stance"
    (§13) without replaying its full history: the summary already reflects
    everything that has happened to it, because it is computed from current
    state, not narrated."""
    members = rh.current_members(session, hole.id)
    parts = [
        f"Rabbit hole \"{hole.title}\" (started by {hole.originating_agent_id}): "
        f"{hole.description}"[:220],
        f"status={hole.status.value} evidence={hole.evidence_strength.value} "
        f"members={len(members)}",
    ]
    if hole.current_hypothesis:
        parts.append(f"current thinking: {hole.current_hypothesis}"[:160])
    return " | ".join(parts)


# --------------------------------------------------------------------------
# Per-event handlers
# --------------------------------------------------------------------------


def _handle_research_completed(session: Session, event, clock: SimulationClock) -> None:
    research_id = event.payload.get("research_id")
    rs = session.scalars(
        select(ResearchSession).where(ResearchSession.research_id == research_id)
    ).first()
    if rs is None:
        return
    strength = rs.evidence_strength
    finding_count = event.payload.get("finding_count", 0)
    if finding_count == 0 and strength in (EvidenceStrength.WEAK, EvidenceStrength.INSUFFICIENT):
        return  # a thin, empty result is not memory-worthy on its own

    importance = _RESEARCH_IMPORTANCE.get(strength, 45.0) if strength else 45.0
    content = f"Researched \"{rs.question}\": {rs.interpretation or 'no clear interpretation'}"
    _upsert(
        session, agent_id=rs.agent_id, memory_type=MemoryType.SEMANTIC, content=content[:400],
        importance=importance, confidence=rs.confidence or 50.0, clock=clock,
        correlation_id=event.correlation_id, source_event_ids=[event.id],
        related_research_ids=[research_id],
    )

    delta = interests.RESEARCH_DELTA
    origin = InterestOrigin.RESEARCH_DISCOVERY.value
    if strength in _UNRESOLVED_EVIDENCE:
        delta += interests.UNRESOLVED_BONUS
        origin = InterestOrigin.UNRESOLVED_QUESTION.value
    interests.bump(
        session, rs.agent_id, rs.question, delta=delta, origin=origin, clock=clock,
        correlation_id=event.correlation_id, research_id=research_id, event_id=event.id,
    )


def _handle_claim_challenged(session: Session, event, clock: SimulationClock) -> None:
    challenger = event.agent_id
    payload = event.payload
    claim_text = payload.get("claim_text", "")
    research_session_id = payload.get("research_session_id")
    owner = session.scalars(
        select(ResearchSession.agent_id).where(ResearchSession.research_id == research_session_id)
    ).first()

    _upsert(
        session, agent_id=challenger, memory_type=MemoryType.EPISODIC,
        content=f"I challenged a claim: \"{claim_text}\""[:300],
        importance=40.0, confidence=95.0, clock=clock, correlation_id=event.correlation_id,
        source_event_ids=[event.id], related_research_ids=[research_session_id] if research_session_id else [],
        related_agent_ids=[owner] if owner else [],
    )
    if not owner or owner == challenger:
        return

    _upsert(
        session, agent_id=owner, memory_type=MemoryType.EPISODIC,
        content=f"{challenger} challenged my claim: \"{claim_text}\""[:300],
        importance=55.0, confidence=95.0, clock=clock, correlation_id=event.correlation_id,
        source_event_ids=[event.id], related_research_ids=[research_session_id] if research_session_id else [],
        related_agent_ids=[challenger],
    )

    prior_challenges = _count_prior_challenges(session, challenger, owner)
    if prior_challenges >= 2:
        existing = _find_reinforceable(
            session, owner, MemoryType.SOCIAL, other_agent_id=challenger
        )
        _upsert(
            session, agent_id=owner, memory_type=MemoryType.SOCIAL,
            content=f"{challenger} tends to challenge my claims — worth having them test the weak ones.",
            importance=50.0, confidence=70.0, clock=clock, correlation_id=event.correlation_id,
            source_event_ids=[event.id], related_agent_ids=[challenger],
            reinforce=existing, replace_content=False,
        )


def _count_prior_challenges(session: Session, challenger: str, owner: str) -> int:
    from app.db.models.events import Event as EventModel

    finding_ids = session.scalars(
        select(ResearchFinding.id)
        .join(ResearchSession, ResearchFinding.research_session_id == ResearchSession.research_id)
        .where(ResearchSession.agent_id == owner)
    ).all()
    if not finding_ids:
        return 0
    claim_ids = list(session.scalars(select(Claim.id).where(Claim.finding_id.in_(finding_ids))))
    if not claim_ids:
        return 0
    return (
        session.query(EventModel)
        .filter(
            EventModel.event_type == EventType.CLAIM_CHALLENGED,
            EventModel.agent_id == challenger,
            EventModel.entity_type == "claim",
            EventModel.entity_id.in_([str(c) for c in claim_ids]),
        )
        .count()
    )


def _handle_belief_updated(session: Session, event, clock: SimulationClock) -> None:
    payload = event.payload
    belief_id = payload.get("belief_id")
    belief = session.get(AgentBelief, belief_id) if belief_id else None
    if belief is None:
        return

    if "relation" in payload:
        importance = {"REJECTS": 65.0, "WEAKENS": 50.0, "STRENGTHENS": 42.0}.get(payload["relation"], 45.0)
        note = payload.get("note")
        detail = f" ({note})" if note else ""
        content = (
            f"My belief \"{belief.statement}\" is now {belief.status.value} "
            f"(confidence {belief.confidence:.0f}){detail}"
        )
    else:
        importance = 40.0
        content = f"I retired my belief \"{belief.statement}\": {payload.get('reason', '')}"

    existing = _find_reinforceable(session, belief.agent_id, MemoryType.SEMANTIC, belief_id=belief.id)
    _upsert(
        session, agent_id=belief.agent_id, memory_type=MemoryType.SEMANTIC, content=content[:400],
        importance=importance, confidence=belief.confidence, clock=clock,
        correlation_id=event.correlation_id, source_event_ids=[event.id],
        related_belief_ids=[belief.id], reinforce=existing, replace_content=True,
    )


def _handle_rabbit_hole_touch(session: Session, event, clock: SimulationClock, *, kind: str) -> None:
    hole_id = event.payload.get("rabbit_hole_id")
    hole = session.get(RabbitHole, hole_id) if hole_id else None
    if hole is None:
        return
    agent_id = event.agent_id

    if kind == "left":
        _upsert(
            session, agent_id=agent_id, memory_type=MemoryType.EPISODIC,
            content=f"I left the rabbit hole \"{hole.title}\".", importance=25.0, confidence=95.0,
            clock=clock, correlation_id=event.correlation_id, source_event_ids=[event.id],
            related_rabbit_hole_ids=[hole.id],
        )
        interests.bump(
            session, agent_id, hole.title, delta=interests.RABBIT_HOLE_LEAVE_DELTA,
            origin=InterestOrigin.RABBIT_HOLE.value, clock=clock, correlation_id=event.correlation_id,
            event_id=event.id,
        )
        return

    existing = _find_reinforceable(session, agent_id, MemoryType.PROJECT, rabbit_hole_id=hole.id)
    importance = {"created": 40.0, "joined": 38.0, "contributed": 50.0, "resolved": 62.0}[kind]
    _upsert(
        session, agent_id=agent_id, memory_type=MemoryType.PROJECT,
        content=_rabbit_hole_summary(session, hole), importance=importance, confidence=80.0,
        clock=clock, correlation_id=event.correlation_id, source_event_ids=[event.id],
        related_rabbit_hole_ids=[hole.id], reinforce=existing, replace_content=True,
    )

    delta = {
        "created": 0.0, "joined": interests.RABBIT_HOLE_JOIN_DELTA,
        "contributed": interests.RABBIT_HOLE_CONTRIBUTE_DELTA, "resolved": 0.02,
    }[kind]
    if delta:
        origin = (
            InterestOrigin.RABBIT_HOLE.value if hole.originating_agent_id == agent_id
            else InterestOrigin.AGENT_INFLUENCE.value
        )
        interests.bump(
            session, agent_id, hole.title, delta=delta, origin=origin, clock=clock,
            correlation_id=event.correlation_id, event_id=event.id,
        )

    if kind == "contributed":
        _bump_collaboration_trust(session, agent_id, hole, clock)


def _bump_collaboration_trust(session: Session, agent_id: str, hole: RabbitHole, clock: SimulationClock) -> None:
    """Bringing new research into a shared hole is useful collaboration
    (§10) — a small, slow trust nudge for the other current members, never a
    hostility signal in the other direction (disagreement stays neutral)."""
    from app.db.models.agents import Relationship

    for other in rh.current_members(session, hole.id):
        if other == agent_id:
            continue
        pair = sorted((agent_id, other))
        relationship = session.scalars(
            select(Relationship).where(
                Relationship.agent_a_id == pair[0], Relationship.agent_b_id == pair[1]
            )
        ).first()
        if relationship is None:
            # Explicit values, not just the column defaults: those only apply
            # once SQLAlchemy flushes this row, but the increments just below
            # read trust_score/interaction_count back immediately.
            relationship = Relationship(
                agent_a_id=pair[0], agent_b_id=pair[1], trust_score=60.0, interaction_count=0,
            )
            session.add(relationship)
        relationship.trust_score = min(100.0, relationship.trust_score + 1.5)
        relationship.interaction_count += 1
        relationship.last_interaction = utcnow()


def _handle_wall_post_read(session: Session, event, clock: SimulationClock) -> None:
    post_id = event.payload.get("wall_post_id")
    post = session.get(ResearchWallPost, post_id) if post_id else None
    if post is None:
        return
    agent_id = event.agent_id
    author = post.agent_id
    salient_types = {"DISAGREEMENT", "CONNECTION", "MYSTERY"}
    importance = 32.0 if post.post_type.value in salient_types else 22.0

    _upsert(
        session, agent_id=agent_id, memory_type=MemoryType.EPISODIC,
        content=f"{author} posted ({post.post_type.value}): {post.content}"[:300],
        importance=importance, confidence=90.0, clock=clock, correlation_id=event.correlation_id,
        source_event_ids=[event.id], related_agent_ids=[author],
        related_research_ids=[post.related_research_id] if post.related_research_id else [],
    )

    if post.related_research_id:
        rs = session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == post.related_research_id)
        ).first()
        if rs is not None:
            interests.bump(
                session, agent_id, rs.question, delta=interests.WALL_EXPOSURE_DELTA,
                origin=InterestOrigin.REPEATED_EXPOSURE.value, clock=clock, correlation_id=event.correlation_id,
                research_id=rs.research_id, event_id=event.id,
            )


_EVENT_HANDLERS = {
    EventType.RESEARCH_COMPLETED: _handle_research_completed,
    EventType.CLAIM_CHALLENGED: _handle_claim_challenged,
    EventType.BELIEF_UPDATED: _handle_belief_updated,
    EventType.BELIEF_REJECTED: _handle_belief_updated,
    EventType.RABBIT_HOLE_CREATED: lambda s, e, c: _handle_rabbit_hole_touch(s, e, c, kind="created"),
    EventType.RABBIT_HOLE_JOINED: lambda s, e, c: _handle_rabbit_hole_touch(s, e, c, kind="joined"),
    EventType.RABBIT_HOLE_UPDATED: lambda s, e, c: _handle_rabbit_hole_touch(s, e, c, kind="contributed"),
    EventType.RABBIT_HOLE_RESOLVED: lambda s, e, c: _handle_rabbit_hole_touch(s, e, c, kind="resolved"),
    EventType.RABBIT_HOLE_LEFT: lambda s, e, c: _handle_rabbit_hole_touch(s, e, c, kind="left"),
    EventType.WALL_POST_READ: _handle_wall_post_read,
}


def consider_turn_events(
    session: Session, event_ids: list[int], clock: SimulationClock
) -> None:
    """Run every event this activation produced through memory selection.

    Deliberately re-queries by id rather than accepting Event objects: the
    caller (``orchestrator.run_next_event``) already has a correlation_id
    scoping exactly this activation's events, and re-querying keeps this
    function decoupled from the dozen call sites across wall/rabbit_holes/
    beliefs/research that record those events — none of them need to know
    memory consolidation exists.
    """
    if not event_ids:
        return
    from app.db.models.events import Event as EventModel

    events = session.scalars(
        select(EventModel).where(EventModel.id.in_(event_ids)).order_by(EventModel.id)
    ).all()
    for event in events:
        handler = _EVENT_HANDLERS.get(event.event_type)
        if handler is not None:
            handler(session, event, clock)


def consider_founder_delivery(
    session: Session, messages: list[FounderMessage], clock: SimulationClock
) -> None:
    """Founder messages are always memory-worthy (§ signal list) — delivered
    ambiently before any agent's turn, so handled separately from
    :func:`consider_turn_events`."""
    for message in messages:
        recipients = [message.target_agent_id] if message.target_agent_id else _all_agent_ids(session)
        for agent_id in recipients:
            _upsert(
                session, agent_id=agent_id, memory_type=MemoryType.EPISODIC,
                content=f"The Founder said: {message.content}"[:300],
                importance=80.0, confidence=100.0, clock=clock,
            )


def _all_agent_ids(session: Session) -> list[str]:
    from app.db.models.agents import Agent

    return list(session.scalars(select(Agent.agent_id)))


#: Conversations triggered for one of these reasons are memory-worthy at a
#: higher baseline importance than a plain shared-interest or social chat —
#: mirrors dialogue.conversation_worthy's own priority ordering.
_HIGH_IMPORTANCE_TRIGGERS = {"DISAGREEMENT", "RABBIT_HOLE", "MEMORY_PROMPTED"}


def consider_conversation_ended(session: Session, conversation, reason: str, clock: SimulationClock) -> None:
    """One EPISODIC memory per participant, for a conversation that actually
    cleared :func:`app.services.dialogue.conversation_worthy`'s bar.

    Content is the *fact* of the exchange — who, roughly what about, why it
    mattered — never a fabricated quote: nothing here invents what was said,
    only that it happened and who else was there, which is exactly what
    "you remember that thing you said about X" (§ conversational memory)
    needs to be honestly reconstructable from later.
    """
    from app.services.conversations import everyone_who_was_present

    participants = everyone_who_was_present(conversation)
    if len(participants) < 2:
        return

    importance = 65.0 if conversation.trigger_type.value in _HIGH_IMPORTANCE_TRIGGERS else 45.0
    subject = conversation.current_subject or "something"

    for agent_id in participants:
        others = sorted(participants - {agent_id})
        content = f"Talked with {', '.join(others)} about \"{subject}\" — {reason}."
        _upsert(
            session, agent_id=agent_id, memory_type=MemoryType.EPISODIC, content=content[:300],
            importance=importance, confidence=85.0, clock=clock,
            correlation_id=conversation.correlation_id,
            related_agent_ids=others,
            related_conversation_ids=[conversation.id],
            related_research_ids=list(conversation.related_research_ids or []),
            related_rabbit_hole_ids=list(conversation.related_rabbit_hole_ids or []),
        )


def consider_reflection(
    session: Session,
    agent_id: str,
    reflection,
    clock: SimulationClock,
    correlation_id: str,
) -> Memory | None:
    """Store a model's own short structured reflection (§15) as one memory.

    Only concise conclusions are ever requested (see
    ``app.schemas.actions.Reflection``) — no chain-of-thought, and nothing
    here re-derives or second-guesses what the agent reported; a reflection
    is itself the kind of thing worth remembering; provenance is limited to
    "the agent said so this turn", the same as any other content action.
    """
    parts = [
        p for p in (reflection.what_changed, reflection.what_matters_now, reflection.what_i_want_to_revisit)
        if p
    ]
    if not parts:
        return None
    return _upsert(
        session, agent_id=agent_id, memory_type=MemoryType.EPISODIC,
        content=" | ".join(parts)[:400], importance=55.0, confidence=85.0,
        clock=clock, correlation_id=correlation_id,
    )


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------


def retrieve_relevant(
    session: Session,
    agent_id: str,
    *,
    clock: SimulationClock,
    limit: int = 5,
    only_types: set[MemoryType] | None = None,
    exclude_types: set[MemoryType] | None = None,
    related_agent_ids: tuple[str, ...] = (),
    related_research_ids: tuple[str, ...] = (),
    related_rabbit_hole_ids: tuple[int, ...] = (),
    keywords: set[str] | None = None,
    require_related_agent: bool = False,
    require_related_rabbit_hole: bool = False,
    mark_recalled: bool = True,
) -> list[Memory]:
    """The bounded, scored slice of an agent's memory shown this turn (§4).

    Never the whole table: a high-importance floor keeps old-but-important
    memories eligible regardless of age (§6 — decay lowers *priority*, never
    deletes), and everything else is bounded to a recent window. Scoring
    combines importance, simulated-day recency, reinforcement, decay, and a
    flat bonus for actually matching the current topic/agent/rabbit hole/
    research in play — see the module-level weights.
    """
    query = select(Memory).where(Memory.agent_id == agent_id)
    if only_types:
        query = query.where(Memory.memory_type.in_(only_types))
    if exclude_types:
        query = query.where(Memory.memory_type.notin_(exclude_types))

    important = session.scalars(
        query.where(Memory.importance >= _HIGH_IMPORTANCE_FLOOR).order_by(Memory.id.desc())
    ).all()
    recent = session.scalars(
        query.order_by(Memory.created_at.desc(), Memory.id.desc()).limit(_RECENT_CANDIDATE_WINDOW)
    ).all()

    by_id: dict[int, Memory] = {m.id: m for m in (*important, *recent)}
    candidates = list(by_id.values())

    if require_related_agent:
        wanted = set(related_agent_ids)
        candidates = [m for m in candidates if wanted & set(m.related_agent_ids or [])]
    if require_related_rabbit_hole:
        wanted_holes = set(related_rabbit_hole_ids)
        candidates = [m for m in candidates if wanted_holes & set(m.related_rabbit_hole_ids or [])]

    keywords = keywords or set()
    scored: list[tuple[float, Memory]] = []
    for m in candidates:
        days_old = (clock.current_day - m.created_sim_day) if m.created_sim_day is not None else 9999
        recency = 1.0 / (1.0 + max(0, days_old))
        reinforcement = min(m.reinforcement_count, _REINFORCEMENT_CAP) / _REINFORCEMENT_CAP

        score = (
            (m.importance / 100.0) * _IMPORTANCE_WEIGHT
            + recency * _RECENCY_WEIGHT
            + reinforcement * _REINFORCEMENT_WEIGHT
            + m.decay_score * _DECAY_WEIGHT
        )
        if set(related_agent_ids) & set(m.related_agent_ids or []):
            score += _RELATION_BONUS
        if set(related_research_ids) & set(m.related_research_ids or []):
            score += _RELATION_BONUS
        if set(related_rabbit_hole_ids) & set(m.related_rabbit_hole_ids or []):
            score += _RELATION_BONUS
        if keywords:
            overlap = len(keywords & _wall_keywords(m.content))
            score += overlap * _KEYWORD_BONUS_PER_WORD
        scored.append((score, m))

    scored.sort(key=lambda pair: (-pair[0], -pair[1].id))
    chosen = [m for _, m in scored[:limit]]

    if mark_recalled and chosen:
        _mark_recalled(session, agent_id, chosen, clock)
    return chosen


def _mark_recalled(session: Session, agent_id: str, memories: list[Memory], clock: SimulationClock) -> None:
    """Refresh last-accessed bookkeeping, and log MEMORY_RECALLED only when at
    least one surfaced memory is a genuine recall — not fresh, not routinely
    re-shown — keeping the event log free of per-context-build noise."""
    genuinely_recalled = []
    for m in memories:
        last_day = m.last_accessed_sim_day
        is_stale = last_day is None or (clock.current_day - last_day) >= _RECALL_LOG_GAP_DAYS
        if is_stale and (m.created_sim_day is None or (clock.current_day - m.created_sim_day) >= _RECALL_LOG_GAP_DAYS):
            genuinely_recalled.append(m.id)
        m.last_accessed = utcnow()
        m.last_accessed_sim_day = clock.current_day

    if genuinely_recalled:
        record_event(
            session,
            event_type=EventType.MEMORY_RECALLED,
            agent_id=agent_id,
            payload={"memory_ids": genuinely_recalled},
            clock=clock,
        )


# --------------------------------------------------------------------------
# Decay
# --------------------------------------------------------------------------

DECAY_IMPORTANCE_CEILING = 50.0
DECAY_STEP = 0.05
MIN_DECAY_SCORE = 0.2
STALE_AFTER_DAYS = 3


def apply_daily_decay(session: Session, clock: SimulationClock) -> int:
    """Once-per-day-advance maintenance (§6): lower retrieval priority for
    low-importance memories nobody has needed in a while. Never deletes, and
    never touches memories at or above the importance ceiling — an important
    memory does not fade just because time passed."""
    count = 0
    for m in session.scalars(select(Memory).where(Memory.importance < DECAY_IMPORTANCE_CEILING)):
        last_touch = m.last_accessed_sim_day if m.last_accessed_sim_day is not None else m.created_sim_day
        if last_touch is None or (clock.current_day - last_touch) < STALE_AFTER_DAYS:
            continue
        if m.decay_score <= MIN_DECAY_SCORE:
            continue
        m.decay_score = max(MIN_DECAY_SCORE, m.decay_score - DECAY_STEP)
        count += 1
    return count
