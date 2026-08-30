"""Rabbit holes: shared investigations that outgrow one agent's research.

Content is always the agent's: the title, the description, who joins, what
they contribute. Only two things here are mechanical, never model-decided,
matching the build bible's "mechanism, not content" line for emergence —

- **heat and status** (:func:`recompute`) — a deterministic function of how
  many distinct agents have actually engaged, not a number any agent proposes
- **who counts as a member right now** — ``left_at IS NULL``, an audit trail
  rather than a mutable flag

A rabbit hole a single agent keeps talking to itself in never gets hot; heat
rewards *distinct* contributors over raw event count, which is what keeps one
agent + one topic from posing as a thriving shared investigation.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.events import Event
from app.db.models.rabbit_holes import RabbitHole, RabbitHoleMember, RabbitHoleResearch
from app.db.models.research import ResearchSession
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, EvidenceStrength, ExposureType, RabbitHoleStatus
from app.services.events import record_event
from app.services.exposure import expose, expose_shared_research

#: Heat weights (§ "Rabbit Holes should be socially generated but mechanically
#: heated"): distinct contributors matter more than raw activity, so one agent
#: dominating a hole cannot make it read as hot on its own.
_WEIGHT_RESEARCH = 3
_WEIGHT_DISTINCT_CONTRIBUTORS = 4
_WEIGHT_CHALLENGES = 2
_WEIGHT_WALL_INTERACTIONS = 1

_HOT_THRESHOLD = 12
_COOLING_AFTER_DAYS = 2
_DORMANT_AFTER_DAYS = 4


def create(
    session: Session,
    agent_id: str,
    title: str,
    description: str,
    clock: SimulationClock,
    correlation_id: str,
    *,
    related_research_id: str | None = None,
    related_wall_post_id: int | None = None,
) -> tuple[RabbitHole, int]:
    """Open a new rabbit hole. The creator is automatically its first member."""
    hole = RabbitHole(
        title=title,
        originating_agent_id=agent_id,
        description=description,
        status=RabbitHoleStatus.NEW,
        last_activity=None,
        last_activity_day=clock.current_day,
    )
    session.add(hole)
    session.flush()

    event = record_event(
        session,
        event_type=EventType.RABBIT_HOLE_CREATED,
        agent_id=agent_id,
        payload={
            "title": title,
            "related_research_id": related_research_id,
            "related_wall_post_id": related_wall_post_id,
        },
        entity_type="rabbit_hole",
        entity_id=str(hole.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    session.add(RabbitHoleMember(rabbit_hole_id=hole.id, agent_id=agent_id))
    expose(
        session, agent_id=agent_id, entity_type="rabbit_hole", entity_id=hole.id,
        exposure_type=ExposureType.CREATED, source_event_id=event.id,
    )
    if related_research_id:
        session.add(RabbitHoleResearch(rabbit_hole_id=hole.id, research_session_id=related_research_id))

    recompute(session, hole, clock)
    return hole, event.id


def is_member(session: Session, rabbit_hole_id: int, agent_id: str) -> bool:
    return (
        session.scalars(
            select(RabbitHoleMember.id).where(
                RabbitHoleMember.rabbit_hole_id == rabbit_hole_id,
                RabbitHoleMember.agent_id == agent_id,
                RabbitHoleMember.left_at.is_(None),
            )
        ).first()
        is not None
    )


def current_members(session: Session, rabbit_hole_id: int) -> list[str]:
    return list(
        session.scalars(
            select(RabbitHoleMember.agent_id).where(
                RabbitHoleMember.rabbit_hole_id == rabbit_hole_id,
                RabbitHoleMember.left_at.is_(None),
            )
        )
    )


def join(
    session: Session, rabbit_hole_id: int, agent_id: str, clock: SimulationClock, correlation_id: str
) -> int:
    """Join a rabbit hole, gaining exposure to everything already linked to it."""
    session.add(RabbitHoleMember(rabbit_hole_id=rabbit_hole_id, agent_id=agent_id))
    event = record_event(
        session,
        event_type=EventType.RABBIT_HOLE_JOINED,
        agent_id=agent_id,
        payload={"rabbit_hole_id": rabbit_hole_id},
        entity_type="rabbit_hole",
        entity_id=str(rabbit_hole_id),
        correlation_id=correlation_id,
        clock=clock,
    )
    expose(
        session, agent_id=agent_id, entity_type="rabbit_hole", entity_id=rabbit_hole_id,
        exposure_type=ExposureType.SHARED_FINDING, source_event_id=event.id,
    )
    for research_id in session.scalars(
        select(RabbitHoleResearch.research_session_id).where(
            RabbitHoleResearch.rabbit_hole_id == rabbit_hole_id
        )
    ):
        expose_shared_research(
            session, agent_id=agent_id, research_session_id=research_id, source_event_id=event.id
        )

    hole = session.get(RabbitHole, rabbit_hole_id)
    recompute(session, hole, clock)
    return event.id


def contribute(
    session: Session,
    rabbit_hole_id: int,
    agent_id: str,
    note: str,
    clock: SimulationClock,
    correlation_id: str,
    *,
    research_id: str | None = None,
) -> int:
    """Add a note, and optionally link new research into the hole.

    Linking research is what actually pulls a second agent's independent work
    into a shared investigation — every *current* member becomes exposed to
    it, not just the contributor.
    """
    hole = session.get(RabbitHole, rabbit_hole_id)
    event = record_event(
        session,
        event_type=EventType.RABBIT_HOLE_UPDATED,
        agent_id=agent_id,
        payload={"rabbit_hole_id": rabbit_hole_id, "note": note, "research_id": research_id},
        entity_type="rabbit_hole",
        entity_id=str(rabbit_hole_id),
        correlation_id=correlation_id,
        clock=clock,
    )
    if research_id:
        already_linked = session.scalars(
            select(RabbitHoleResearch.id).where(
                RabbitHoleResearch.rabbit_hole_id == rabbit_hole_id,
                RabbitHoleResearch.research_session_id == research_id,
            )
        ).first()
        if not already_linked:
            session.add(
                RabbitHoleResearch(rabbit_hole_id=rabbit_hole_id, research_session_id=research_id)
            )
        # Every current member — not just the contributor — becomes exposed to
        # this research and its findings: joining a shared investigation means
        # its linked work becomes visible to you.
        for member_id in current_members(session, rabbit_hole_id):
            expose_shared_research(
                session, agent_id=member_id, research_session_id=research_id,
                source_event_id=event.id,
            )

    recompute(session, hole, clock)
    return event.id


def leave(
    session: Session, rabbit_hole_id: int, agent_id: str, clock: SimulationClock, correlation_id: str
) -> int:
    from app.db.base import utcnow

    membership = session.scalars(
        select(RabbitHoleMember).where(
            RabbitHoleMember.rabbit_hole_id == rabbit_hole_id,
            RabbitHoleMember.agent_id == agent_id,
            RabbitHoleMember.left_at.is_(None),
        )
    ).first()
    if membership:
        membership.left_at = utcnow()

    event = record_event(
        session,
        event_type=EventType.RABBIT_HOLE_LEFT,
        agent_id=agent_id,
        payload={"rabbit_hole_id": rabbit_hole_id},
        entity_type="rabbit_hole",
        entity_id=str(rabbit_hole_id),
        correlation_id=correlation_id,
        clock=clock,
    )
    hole = session.get(RabbitHole, rabbit_hole_id)
    recompute(session, hole, clock)
    return event.id


def resolve(
    session: Session,
    rabbit_hole_id: int,
    agent_id: str,
    resolution: str,
    clock: SimulationClock,
    correlation_id: str,
) -> int:
    hole = session.get(RabbitHole, rabbit_hole_id)
    hole.status = RabbitHoleStatus.RESOLVED
    hole.current_hypothesis = resolution or hole.current_hypothesis
    event = record_event(
        session,
        event_type=EventType.RABBIT_HOLE_RESOLVED,
        agent_id=agent_id,
        payload={"rabbit_hole_id": rabbit_hole_id, "resolution": resolution},
        entity_type="rabbit_hole",
        entity_id=str(rabbit_hole_id),
        correlation_id=correlation_id,
        clock=clock,
    )
    return event.id


def has_similar_active_title(session: Session, title: str) -> bool:
    """Anti-repetition guard: don't let a second, identically-named rabbit
    hole open while one is still live. Exact match (case/whitespace
    normalised) — deliberately not fuzzy, so it never blocks two genuinely
    different questions that merely share a few words."""
    normalized = " ".join(title.strip().lower().split())
    active_titles = session.scalars(
        select(RabbitHole.title).where(
            RabbitHole.status.notin_([RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED])
        )
    )
    return any(" ".join(t.strip().lower().split()) == normalized for t in active_titles)


def recompute(session: Session, hole: RabbitHole, clock: SimulationClock) -> None:
    """Recalculate heat and status from what has actually happened.

    Called after every rabbit-hole event. Nothing here is asked of a model —
    it is arithmetic over rows that already exist, which is what keeps a
    hole's liveliness an observation rather than a claim.

    Flushes first: this session runs with ``autoflush=False`` (app/db/session.py),
    so a membership or research link a caller just added would otherwise be
    invisible to the ``select()`` queries below until some later, unrelated
    flush happened to occur — silently undercounting contributors and
    research on the very call meant to count them.
    """
    session.flush()

    research_ids = list(
        session.scalars(
            select(RabbitHoleResearch.research_session_id).where(
                RabbitHoleResearch.rabbit_hole_id == hole.id
            )
        )
    )
    research_count = len(research_ids)

    contributors: set[str] = {hole.originating_agent_id}
    contributors |= set(current_members(session, hole.id))
    if research_ids:
        contributors |= set(
            session.scalars(
                select(ResearchSession.agent_id).where(
                    ResearchSession.research_id.in_(research_ids)
                )
            )
        )

    challenge_count = 0
    if research_ids:
        from app.db.models.research import ResearchFinding
        from app.db.models.research_provenance import Claim

        finding_ids = list(
            session.scalars(
                select(ResearchFinding.id).where(
                    ResearchFinding.research_session_id.in_(research_ids)
                )
            )
        )
        claim_ids = (
            list(session.scalars(select(Claim.id).where(Claim.finding_id.in_(finding_ids))))
            if finding_ids
            else []
        )
        if claim_ids:
            challenge_count = (
                session.query(Event)
                .filter(
                    Event.event_type == EventType.CLAIM_CHALLENGED,
                    Event.entity_type == "claim",
                    Event.entity_id.in_([str(c) for c in claim_ids]),
                )
                .count()
            )

    wall_interactions = (
        session.query(ResearchWallPost)
        .filter(ResearchWallPost.related_rabbit_hole_id == hole.id)
        .count()
    )

    heat = (
        _WEIGHT_RESEARCH * research_count
        + _WEIGHT_DISTINCT_CONTRIBUTORS * len(contributors)
        + _WEIGHT_CHALLENGES * challenge_count
        + _WEIGHT_WALL_INTERACTIONS * wall_interactions
    )
    hole.activity_level = float(heat)
    hole.last_activity_day = clock.current_day
    from app.db.base import utcnow

    hole.last_activity = utcnow()

    if hole.status in (RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED):
        return  # terminal states are never reopened mechanically

    active_now = len(current_members(session, hole.id)) > 0
    if not active_now:
        hole.status = RabbitHoleStatus.ABANDONED
        return

    # recompute() is only ever called in response to a real interaction —
    # someone just joined, contributed, or otherwise touched this hole — so
    # status here is judged purely from heat/contributors, never staleness:
    # this *is* the "returning to a dormant hole revives it" mechanic,
    # falling straight out of a fresh touch recomputing status from current
    # engagement rather than re-affirming however stale it used to be.
    # Staleness from time passing with nobody touching the hole at all is a
    # different question, handled separately by :func:`sweep_dormancy`.
    if heat >= _HOT_THRESHOLD:
        hole.status = RabbitHoleStatus.HOT
    elif heat > 0 or research_count or len(contributors) > 1:
        hole.status = RabbitHoleStatus.ACTIVE
    else:
        hole.status = RabbitHoleStatus.NEW

    # Evidence strength tracks the strongest evidence_strength among linked
    # research, since a rabbit hole is only as well-supported as its best
    # session — never invented independently of that research.
    if research_ids:
        strengths = list(
            session.scalars(
                select(ResearchSession.evidence_strength).where(
                    ResearchSession.research_id.in_(research_ids)
                )
            )
        )
        order = [
            EvidenceStrength.INSUFFICIENT,
            EvidenceStrength.WEAK,
            EvidenceStrength.CONFLICTING,
            EvidenceStrength.DEVELOPING,
            EvidenceStrength.MODERATE,
            EvidenceStrength.STRONG,
        ]
        hole.evidence_strength = max(strengths, key=order.index)


def sweep_dormancy(session: Session, clock: SimulationClock) -> int:
    """Once-per-day-advance maintenance (Packet 7): mark holes COOLING/DORMANT
    purely from elapsed simulated days since anyone touched them — the
    complement to :func:`recompute`, which only ever runs *because* of a
    touch and therefore never itself observes staleness (see its docstring).
    Never touches heat, membership, or research links; only status. Returns
    how many holes changed status this sweep.
    """
    changed = 0
    for hole in session.scalars(
        select(RabbitHole).where(
            RabbitHole.status.notin_([RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED])
        )
    ):
        if not current_members(session, hole.id):
            continue  # ABANDONED is recompute()'s call, not staleness
        days_stale = clock.current_day - (hole.last_activity_day or clock.current_day)
        if days_stale >= _DORMANT_AFTER_DAYS and hole.status is not RabbitHoleStatus.DORMANT:
            hole.status = RabbitHoleStatus.DORMANT
            changed += 1
        elif (
            _COOLING_AFTER_DAYS <= days_stale < _DORMANT_AFTER_DAYS
            and hole.status not in (RabbitHoleStatus.COOLING, RabbitHoleStatus.DORMANT)
        ):
            hole.status = RabbitHoleStatus.COOLING
            changed += 1
    return changed
