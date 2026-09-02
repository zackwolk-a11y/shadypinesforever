"""Persistent, personal unresolved curiosity.

A question is not a task. Nothing here ever scores, requires, or rewards
having one — see the module-level guardrails called out at each function
below and app/services/context_builder.py's OPEN QUESTIONS section, which
is exactly as optional to act on as RECENT REFLECTIONS or INTERESTS
already are.

Salience is deliberately simple in this first version — no semantic
similarity, no embeddings, no automatic reinforcement from merely being
displayed. It moves in exactly three ways:

- created at a moderate default (matches memory.write_note's own default
  importance of 45.0 — one more precedent for "worth remembering/pursuing,
  not urgent");
- explicit engagement (a revisit, a research link, a reflection's own
  judgment about it) bumps it by a fixed amount, mirroring
  app.services.interests.bump's fixed-delta convention;
- daily non-engagement decays it, mirroring app.services.memory's
  apply_daily_decay, until it falls below a floor and is swept to DORMANT —
  never deleted, always revivable by a later genuine engagement.

Creation is organic, wired from the two places that already produce
question-shaped LLM output and previously threw it away
(AgentReflection.open_question, ResearchSession.open_questions/follow_ups)
— see app.services.reflection and app.services.research. Nothing here ever
manufactures a question from a plain interest.

Rabbit Holes remain the only collaborative/shared structure — this module
never re-implements membership or multi-agent contribution. A question may
carry a ``rabbit_hole_id`` once it graduates into one, set by ordinary
application code alongside the existing CREATE_RABBIT_HOLE handling, not by
anything in this file.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agent_questions import AgentQuestion
from app.db.models.world import SimulationClock
from app.domain.enums import AgentQuestionStatus, EventType
from app.services.events import record_event

#: Matches memory.write_note's default importance (45.0 on the same 0-100
#: scale) — "worth remembering/pursuing," not "urgent."
DEFAULT_SALIENCE = 45.0
MIN_SALIENCE = 0.0
MAX_SALIENCE = 100.0

#: A single explicit engagement (revisit, research link, or a reflection
#: judging it) — one fixed delta, the same "repetition, not magnitude, is
#: what makes it real" shape as app.services.interests' deltas, just a
#: single flat amount since v1 deliberately does not distinguish kinds of
#: engagement by size.
ENGAGEMENT_BONUS = 15.0

#: Untouched for this many simulated days before decay starts eating into
#: salience — mirrors AgentInterest.DORMANT_AFTER_DAYS.
DORMANT_AFTER_DAYS = 4
#: How much salience one day's neglect removes, once stale.
DAILY_DECAY_STEP = 6.0
#: Below this floor, once stale, a question is swept to DORMANT.
DORMANT_SALIENCE_FLOOR = 20.0

#: How many new questions one completed research session may organically
#: seed — small and capped, so a single session's open_questions/follow_ups
#: list can never flood an agent with a dozen new "curiosities" at once.
MAX_QUESTIONS_PER_RESEARCH_SESSION = 2

#: Statuses a model's own judgment (via reflection) may set directly.
#: DORMANT is deliberately excluded — that transition is decay-only, never
#: something a model chooses on an agent's behalf.
MODEL_SETTABLE_STATUSES = {
    AgentQuestionStatus.OPEN,
    AgentQuestionStatus.RESEARCHING,
    AgentQuestionStatus.RESOLVED,
    AgentQuestionStatus.ABANDONED,
}

#: Statuses that still count as this agent's "active" curiosity — what
#: context_builder's OPEN QUESTIONS section and retrieve_relevant() show.
#: RESOLVED/DORMANT/ABANDONED questions disappear from context, but are
#: never deleted.
_ACTIVE_STATUSES = (AgentQuestionStatus.OPEN, AgentQuestionStatus.RESEARCHING)

#: A fixture-only artifact, same reasoning as interests._FIXTURE_PREFIX:
#: strip it only for de-duplication matching, never from stored content.
_FIXTURE_PREFIX = "[fixture] "


def _normalize(text: str) -> str:
    stripped = text[len(_FIXTURE_PREFIX):] if text.startswith(_FIXTURE_PREFIX) else text
    return " ".join(stripped.strip().lower().split())


def _find_live_duplicate(session: Session, agent_id: str, text: str) -> AgentQuestion | None:
    """A question this agent already has open/researching/dormant with the
    same normalized text — creation is a no-op against it rather than a
    near-identical duplicate row. RESOLVED/ABANDONED questions are not
    checked: asking the same thing again after it was actually resolved or
    deliberately dropped is legitimate, not a duplicate."""
    normalized = _normalize(text)
    if not normalized:
        return None
    candidates = session.scalars(
        select(AgentQuestion).where(
            AgentQuestion.agent_id == agent_id,
            AgentQuestion.status.in_(
                (AgentQuestionStatus.OPEN, AgentQuestionStatus.RESEARCHING, AgentQuestionStatus.DORMANT)
            ),
        )
    )
    for row in candidates:
        if _normalize(row.question) == normalized:
            return row
    return None


def create(
    session: Session,
    agent_id: str,
    question_text: str,
    clock: SimulationClock,
    *,
    origin_memory_id: int | None = None,
    origin_reflection_id: int | None = None,
    origin_conversation_id: int | None = None,
    origin_research_session_id: str | None = None,
    salience: float = DEFAULT_SALIENCE,
    correlation_id: str | None = None,
) -> AgentQuestion | None:
    """Organically create one question from a real originating signal.

    Returns ``None`` (a no-op, not an error) for empty text or a live
    duplicate already on file — this is never a place that must succeed;
    every caller is expected to treat ``None`` as "nothing to do."
    """
    text = (question_text or "").strip()
    if not text:
        return None
    if _find_live_duplicate(session, agent_id, text) is not None:
        return None

    question = AgentQuestion(
        agent_id=agent_id,
        question=text[:500],
        status=AgentQuestionStatus.OPEN,
        salience=max(MIN_SALIENCE, min(MAX_SALIENCE, salience)),
        last_engaged_sim_day=clock.current_day,
        origin_memory_id=origin_memory_id,
        origin_reflection_id=origin_reflection_id,
        origin_conversation_id=origin_conversation_id,
        origin_research_session_id=origin_research_session_id,
    )
    session.add(question)
    session.flush()

    record_event(
        session,
        event_type=EventType.QUESTION_CREATED,
        agent_id=agent_id,
        payload={
            "question_id": question.id,
            "question": question.question,
            "salience": question.salience,
            "origin": (
                "reflection" if origin_reflection_id is not None
                else "research" if origin_research_session_id is not None
                else "memory" if origin_memory_id is not None
                else "unspecified"
            ),
        },
        entity_type="agent_question",
        entity_id=str(question.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    return question


def _engage(session: Session, question: AgentQuestion, clock: SimulationClock) -> bool:
    """Shared bump-and-revive step behind every explicit engagement.
    Returns whether this revived a DORMANT question."""
    was_dormant = question.status is AgentQuestionStatus.DORMANT
    question.salience = max(MIN_SALIENCE, min(MAX_SALIENCE, question.salience + ENGAGEMENT_BONUS))
    question.last_engaged_sim_day = clock.current_day
    if was_dormant:
        question.status = AgentQuestionStatus.OPEN
    return was_dormant


def revisit(
    session: Session, question: AgentQuestion, clock: SimulationClock, *, correlation_id: str | None = None
) -> None:
    """An agent explicitly returned to this question without changing its
    status or linking research — e.g. a reflection re-affirms it is still
    open. The only way salience rises other than at creation."""
    revived = _engage(session, question, clock)
    record_event(
        session,
        event_type=EventType.QUESTION_REVISITED,
        agent_id=question.agent_id,
        payload={"question_id": question.id, "salience": question.salience, "revived_from_dormant": revived},
        entity_type="agent_question",
        entity_id=str(question.id),
        correlation_id=correlation_id,
        clock=clock,
    )


def link_to_research(
    session: Session,
    question: AgentQuestion,
    research_session_id: str,
    clock: SimulationClock,
    *,
    correlation_id: str | None = None,
) -> None:
    """An agent's START_RESEARCH explicitly named this question
    (``AgentAction.target_question_id``) — the only way ``status`` becomes
    RESEARCHING. Completing that research does NOT itself resolve the
    question; see app.services.research and app.services.reflection for why."""
    _engage(session, question, clock)
    question.status = AgentQuestionStatus.RESEARCHING
    question.research_session_id = research_session_id
    record_event(
        session,
        event_type=EventType.QUESTION_LINKED_TO_RESEARCH,
        agent_id=question.agent_id,
        payload={"question_id": question.id, "research_session_id": research_session_id},
        entity_type="agent_question",
        entity_id=str(question.id),
        correlation_id=correlation_id,
        clock=clock,
    )


def apply_status_update(
    session: Session,
    question: AgentQuestion,
    new_status: AgentQuestionStatus,
    clock: SimulationClock,
    *,
    note: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """A reflection's own judgment about an existing question of this
    agent's — the only path to RESOLVED or ABANDONED, and the only path
    back to OPEN/RESEARCHING other than an explicit research link. Never
    called with DORMANT — that is decay's transition alone, see
    :func:`sweep_decay`."""
    if new_status not in MODEL_SETTABLE_STATUSES:
        raise ValueError(f"{new_status} is not a model-settable status")
    old_status = question.status
    _engage(session, question, clock)
    question.status = new_status
    record_event(
        session,
        event_type=EventType.QUESTION_STATUS_CHANGED,
        agent_id=question.agent_id,
        payload={
            "question_id": question.id,
            "from": old_status.value,
            "to": new_status.value,
            "note": (note or "")[:300] or None,
        },
        entity_type="agent_question",
        entity_id=str(question.id),
        correlation_id=correlation_id,
        clock=clock,
    )


def reformulate(
    session: Session,
    question: AgentQuestion,
    new_text: str,
    clock: SimulationClock,
    *,
    correlation_id: str | None = None,
) -> AgentQuestion | None:
    """This question evolved into a better one, rather than being answered
    outright. The old row is marked RESOLVED — its own specific phrasing
    reached a real intellectual outcome by being superseded, which is
    exactly as legitimate a resolution as an answer — and points forward;
    the new row carries the old one's provenance and current salience
    forward rather than starting cold. Returns ``None`` (no-op) if
    ``new_text`` is empty or already an identical live duplicate."""
    text = (new_text or "").strip()
    if not text:
        return None

    new_question = create(
        session,
        question.agent_id,
        text,
        clock,
        origin_memory_id=question.origin_memory_id,
        origin_reflection_id=question.origin_reflection_id,
        origin_conversation_id=question.origin_conversation_id,
        origin_research_session_id=question.origin_research_session_id,
        salience=question.salience,
        correlation_id=correlation_id,
    )
    if new_question is None:
        return None
    new_question.reformulated_from_id = question.id

    question.status = AgentQuestionStatus.RESOLVED
    question.reformulated_into_id = new_question.id
    question.last_engaged_sim_day = clock.current_day

    record_event(
        session,
        event_type=EventType.QUESTION_REFORMULATED,
        agent_id=question.agent_id,
        payload={"from_question_id": question.id, "to_question_id": new_question.id},
        entity_type="agent_question",
        entity_id=str(question.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    return new_question


def sweep_decay(session: Session, clock: SimulationClock) -> int:
    """Once-per-day-advance maintenance (called from app.services.clock):
    active questions nobody has touched in a while lose salience, and once
    both stale and below the floor, are swept to DORMANT. Never deletes,
    never touches RESOLVED/ABANDONED/already-DORMANT rows, and never raises
    salience — only :func:`revisit`/:func:`link_to_research`/
    :func:`apply_status_update` (all explicit) ever do that.

    Returns how many questions were newly marked DORMANT this sweep.
    """
    newly_dormant = 0
    active = session.scalars(
        select(AgentQuestion).where(AgentQuestion.status.in_(_ACTIVE_STATUSES))
    )
    for row in active:
        last_touch = row.last_engaged_sim_day
        stale = last_touch is None or (clock.current_day - last_touch) >= DORMANT_AFTER_DAYS
        if not stale:
            continue
        row.salience = max(MIN_SALIENCE, row.salience - DAILY_DECAY_STEP)
        if row.salience >= DORMANT_SALIENCE_FLOOR:
            continue
        row.status = AgentQuestionStatus.DORMANT
        newly_dormant += 1
        record_event(
            session,
            event_type=EventType.QUESTION_DORMANT,
            agent_id=row.agent_id,
            payload={"question_id": row.id, "salience": row.salience},
            entity_type="agent_question",
            entity_id=str(row.id),
            clock=clock,
        )
    return newly_dormant


def retrieve_relevant(session: Session, agent_id: str, *, limit: int = 3) -> list[AgentQuestion]:
    """The small, bounded slice of an agent's own active questions shown in
    context this turn — sorted only by salience, no recency/keyword scoring
    trickery, and never the whole table. Read-only: unlike memory/reflection
    retrieval, this never marks anything "recalled" or bumps salience —
    being shown is not itself an engagement (§ constraint: no hidden
    behavioral pressure from mere display)."""
    active = session.scalars(
        select(AgentQuestion)
        .where(AgentQuestion.agent_id == agent_id, AgentQuestion.status.in_(_ACTIVE_STATUSES))
        .order_by(AgentQuestion.salience.desc(), AgentQuestion.id.desc())
        .limit(limit)
    ).all()
    return list(active)
