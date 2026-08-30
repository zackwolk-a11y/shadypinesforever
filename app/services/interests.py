"""Interest evolution: how an agent's curiosity actually moves (Packet 7).

The eight founding interests (§3) are starting conditions, not a ceiling.
Everything here is a small, mechanical delta applied to
``AgentInterest.strength`` — never a single conversation or research session
jumping a topic straight to obsession. A topic becomes a *real* secondary
interest only after several genuine, independent signals accumulate, which
falls out naturally from the deltas being small and the matching being
stable: the same phrase has to keep coming back for its strength to climb.

Strength lives on 0.0-1.0 (the founding interests seed at 0.5 — see
``scripts/seed_agents.py``). A brand-new emerging interest starts near zero
and has to earn its way up through repeated reinforcement, the same
arithmetic that reinforces it the second and third time.

This mirrors the shape ``app/services/beliefs.py`` already established: the
*qualitative* trigger (a rabbit hole joined, a research question answered) is
a fact about what happened; the resulting number is computed here, never
proposed by a model.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models.agents import AgentInterest
from app.db.models.world import SimulationClock
from app.domain.enums import EventType
from app.services.events import record_event

#: Deltas, all small and all documented — no single trigger moves strength by
#: more than a few hundredths. Repetition, not magnitude, is what makes an
#: interest real.
RESEARCH_DELTA = 0.07
UNRESOLVED_BONUS = 0.03
RABBIT_HOLE_JOIN_DELTA = 0.05
RABBIT_HOLE_CONTRIBUTE_DELTA = 0.08
RABBIT_HOLE_LEAVE_DELTA = -0.04
WALL_EXPOSURE_DELTA = 0.03

MIN_STRENGTH = 0.0
MAX_STRENGTH = 1.0

#: An interest below this floor, untouched for this many simulated days,
#: is swept to dormant — see :func:`sweep_dormancy`. Never deleted.
DORMANT_STRENGTH_FLOOR = 0.15
DORMANT_AFTER_DAYS = 5

#: A fixture-only artifact: every title/question this codebase's fixture
#: providers generate is prefixed "[fixture] " (see app/providers/llm/fixture.py).
#: Stripping it only for matching means a fixture-sourced rabbit hole titled
#: "[fixture] underground events" correctly reinforces an existing founding
#: interest "underground events" instead of silently forking into a
#: duplicate, near-identical row. A live model's own prose never carries this
#: prefix, so this is a no-op outside fixture runs.
_FIXTURE_PREFIX = "[fixture] "


def _normalize(text: str) -> str:
    stripped = text[len(_FIXTURE_PREFIX):] if text.startswith(_FIXTURE_PREFIX) else text
    return " ".join(stripped.strip().lower().split())


def _find(session: Session, agent_id: str, topic: str) -> AgentInterest | None:
    normalized = _normalize(topic)
    if not normalized:
        return None
    for row in session.scalars(
        select(AgentInterest).where(AgentInterest.agent_id == agent_id)
    ):
        if _normalize(row.interest) == normalized:
            return row
    return None


def bump(
    session: Session,
    agent_id: str,
    topic: str,
    *,
    delta: float,
    origin: str,
    clock: SimulationClock,
    correlation_id: str | None = None,
    research_id: str | None = None,
    event_id: int | None = None,
) -> AgentInterest | None:
    """Move one interest by ``delta``, creating it if this is a genuinely new
    topic and ``delta`` is positive. Returns the row, or ``None`` if there was
    nothing to create (a negative delta on a topic that doesn't exist yet is
    a no-op — you cannot become less interested in something you were never
    interested in).
    """
    topic = topic.strip()
    if not topic:
        return None

    row = _find(session, agent_id, topic)
    created = row is None
    if created:
        if delta <= 0:
            return None
        row = AgentInterest(
            agent_id=agent_id,
            interest=topic,
            strength=0.0,
            origin=origin,
        )
        session.add(row)
        session.flush()

    was_dormant = row.dormant
    row.strength = max(MIN_STRENGTH, min(MAX_STRENGTH, row.strength + delta))
    row.last_engaged = utcnow()
    row.last_engaged_sim_day = clock.current_day
    if research_id and research_id not in (row.supporting_research_ids or []):
        row.supporting_research_ids = [*(row.supporting_research_ids or []), research_id]
    if event_id and event_id not in (row.supporting_event_ids or []):
        row.supporting_event_ids = [*(row.supporting_event_ids or []), event_id]

    if was_dormant and delta > 0:
        row.dormant = False
        record_event(
            session,
            event_type=EventType.INTEREST_REVIVED,
            agent_id=agent_id,
            payload={"interest": row.interest, "strength": row.strength},
            entity_type="agent_interest",
            entity_id=str(row.id),
            correlation_id=correlation_id,
            clock=clock,
        )

    if created:
        record_event(
            session,
            event_type=EventType.INTEREST_CREATED,
            agent_id=agent_id,
            payload={"interest": row.interest, "strength": row.strength, "origin": origin},
            entity_type="agent_interest",
            entity_id=str(row.id),
            correlation_id=correlation_id,
            clock=clock,
        )
    elif delta != 0:
        record_event(
            session,
            event_type=EventType.INTEREST_INCREASED if delta > 0 else EventType.INTEREST_DECREASED,
            agent_id=agent_id,
            payload={"interest": row.interest, "strength": row.strength, "delta": delta, "origin": origin},
            entity_type="agent_interest",
            entity_id=str(row.id),
            correlation_id=correlation_id,
            clock=clock,
        )

    return row


def sweep_dormancy(session: Session, clock: SimulationClock) -> int:
    """Once-per-day-advance maintenance: flag long-neglected weak interests
    dormant. Never deletes, never touches strength — only visibility.

    Returns how many interests were newly marked dormant this sweep.
    """
    count = 0
    for row in session.scalars(select(AgentInterest).where(AgentInterest.dormant.is_(False))):
        if row.strength >= DORMANT_STRENGTH_FLOOR:
            continue
        last_day = row.last_engaged_sim_day
        stale = last_day is None or (clock.current_day - last_day) >= DORMANT_AFTER_DAYS
        if not stale:
            continue
        row.dormant = True
        record_event(
            session,
            event_type=EventType.INTEREST_DORMANT,
            agent_id=row.agent_id,
            payload={"interest": row.interest, "strength": row.strength},
            entity_type="agent_interest",
            entity_id=str(row.id),
            clock=clock,
        )
        count += 1
    return count
