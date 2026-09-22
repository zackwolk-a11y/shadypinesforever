"""The simulated clock: periods, days, and what each period makes likely.

Periods do not schedule model calls. Nothing fires "every virtual hour". A
period changes what kinds of events are *likely* — the activation scheduler
reads its weight — and a period ends when the agents in it have run out of
reasons to act.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.world import SimulationClock
from app.domain.enums import EventType
from app.services.events import record_event

#: The day's shape (§ daily rhythm). NIGHT is where synthesis will live once the
#: reporting packet lands; for now it is simply the quietest period.
PERIODS: tuple[str, ...] = ("MORNING", "RESEARCH", "AFTERNOON", "EVENING", "NIGHT")

FIRST_PERIOD = PERIODS[0]
LAST_PERIOD = PERIODS[-1]


@dataclass(frozen=True)
class ClockAdvance:
    """What one advance did."""

    from_day: int
    from_period: str
    to_day: int
    to_period: str

    @property
    def crossed_day_boundary(self) -> bool:
        return self.to_day != self.from_day

    def __str__(self) -> str:
        return f"day {self.from_day} {self.from_period} -> day {self.to_day} {self.to_period}"


def next_period(period: str) -> tuple[str, bool]:
    """The period after this one, and whether that wraps into a new day."""
    try:
        index = PERIODS.index(period)
    except ValueError:
        # An unrecognised period (hand-edited, or from a later phase's list)
        # resets to the start of the day rather than guessing a successor.
        return FIRST_PERIOD, False
    if index == len(PERIODS) - 1:
        return FIRST_PERIOD, True
    return PERIODS[index + 1], False


def advance(session: Session, clock: SimulationClock) -> ClockAdvance:
    """Move the clock on one period, rolling into the next day at NIGHT's end.

    Records PERIOD_ADVANCED, and DAY_ADVANCED as well when the day rolls over,
    so the log alone is enough to reconstruct the Village's calendar.
    """
    from_day, from_period = clock.current_day, clock.current_period
    to_period, rolled = next_period(from_period)
    to_day = from_day + 1 if rolled else from_day

    clock.current_day = to_day
    clock.current_period = to_period
    clock.last_advanced_at = _now()

    result = ClockAdvance(from_day, from_period, to_day, to_period)

    record_event(
        session,
        event_type=EventType.PERIOD_ADVANCED,
        payload={
            "from": {"day": from_day, "period": from_period},
            "to": {"day": to_day, "period": to_period},
        },
        clock=clock,
    )
    if rolled:
        record_event(
            session,
            event_type=EventType.DAY_ADVANCED,
            payload={"day": to_day},
            clock=clock,
        )
        _daily_maintenance(session, clock)
    return result


def _daily_maintenance(session: Session, clock: SimulationClock) -> None:
    """Packet 7 upkeep that only makes sense once per simulated day: rabbit
    holes and interests going stale from time passing (as opposed to from a
    real interaction, which recompute()/bump() already handle), memory
    decay, and the same staleness-based decay for persistent unresolved
    curiosity (agent_questions.sweep_decay). Imported locally to avoid a
    module-level cycle — clock.py is a low-level service other modules
    import early, and none of these four need to import clock.py back."""
    from app.services import agent_questions, interests, memory
    from app.services import rabbit_holes as rh

    rh.sweep_dormancy(session, clock)
    interests.sweep_dormancy(session, clock)
    memory.apply_daily_decay(session, clock)
    agent_questions.sweep_decay(session, clock)


def _now():
    from app.db.base import utcnow

    return utcnow()
