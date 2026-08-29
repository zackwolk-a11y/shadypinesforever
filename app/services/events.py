"""Writing to the append-only event log.

Every state mutation and the event recording it happen in the same transaction:
the caller opens one, calls both, and commits once. A log that can disagree with
the state it describes is worse than no log.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.events import Event
from app.db.models.world import SimulationClock
from app.domain.enums import EventType


def record_event(
    session: Session,
    *,
    event_type: EventType,
    agent_id: str | None = None,
    payload: dict | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: int | None = None,
    clock: SimulationClock | None = None,
) -> Event:
    """Append one event. Never updates, never deletes.

    The simulated position is stamped from the clock so the log can be read back
    in the Village's own time, not just wall-clock order.
    """
    event = Event(
        event_type=event_type,
        agent_id=agent_id,
        payload=payload or {},
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        sim_day=clock.current_day if clock else None,
        sim_period=clock.current_period if clock else None,
    )
    session.add(event)
    session.flush()  # assign the id so a following event can cite it
    return event
