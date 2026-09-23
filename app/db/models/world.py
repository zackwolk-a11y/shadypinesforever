"""Global simulation state: key/value world state, the clock, and locations (§5, §17)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow

#: The semantic locations of the Phase 1 clubhouse (§5). Seeded by
#: ``scripts/seed_agents.py``, not by a migration.
CLUBHOUSE_LOCATIONS: tuple[str, ...] = (
    "espresso_counter",
    "bar",
    "communal_table",
    "couch",
    "research_computer",
    "zine_desk",
    "recording_desk",
    "research_wall",
    "chalkboard",
    "phone",
    "bookshelf",
)


class WorldState(Base):
    """Generic key/value store for global simulation state.

    Anything that does not yet deserve its own table lives here, so new global
    state can be added in Phase 2 without a migration.
    """

    __tablename__ = "world_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    value: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class SimulationClock(Base):
    """The simulation clock. A single row (``id == 1``) is expected.

    ``current_period`` is a plain string rather than an enum: §5's day structure
    (MORNING / RESEARCH / AFTERNOON / EVENING / NIGHT) is expected to gain
    periods in later phases, and a string keeps that a data change.
    """

    __tablename__ = "simulation_clock"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_period: Mapped[str] = mapped_column(String(32), nullable=False, default="MORNING")
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Why ``is_paused`` is set, when it was the provider circuit breaker
    #: rather than a Founder's manual PAUSE — see
    #: :class:`app.domain.enums.PauseReason`. Plain string, not a DB enum,
    #: matching every other lifecycle column in this codebase (e.g.
    #: ``events.event_type``): SQLite never enforces it as a real
    #: constraint, so a later reason value is a data change, not a
    #: migration. ``None`` whenever ``is_paused`` is False, or True for an
    #: ordinary manual pause.
    pause_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_advanced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Location(Base):
    """A place inside the clubhouse (§5).

    Locations are semantic, not spatial, in Phase 1. Nothing here assumes a
    single clubhouse or forbids coordinates later: a future phase can add
    ``x``/``y``/``building_id`` columns without reshaping this table.
    """

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
