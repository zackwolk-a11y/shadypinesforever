#!/usr/bin/env python3
"""Seed the village's starting state: the Founding Eight (§3), the clubhouse
locations (§5), and the simulation clock.

Seed data lives here and not in an Alembic migration on purpose. Migrations
describe *schema*; a roster seeded from a migration could not be corrected
without authoring a new revision, and the Founding Eight are content, not
structure.

The script is idempotent — run it as many times as you like. Rows that already
exist are left alone rather than overwritten, because several of the columns it
would otherwise clobber (``current_location``, ``current_activity``,
``AgentInterest.strength``) are *runtime* state that the simulation moves. Use
``--update`` to refresh the authored fields (identity, voice) without touching
runtime state, and ``--reset`` to wipe seeded rows on a throwaway database.

Seeding deliberately writes no rows to ``events``: the event log records what
happens *in* the simulation, and world setup happens before the simulation
starts.

Usage::

    python scripts/seed_agents.py                # seed anything missing
    python scripts/seed_agents.py --dry-run      # report what it would do
    python scripts/seed_agents.py --update       # refresh identity/voice too
    python scripts/seed_agents.py --reset        # wipe seeded rows, then seed
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import SessionLocal, get_database_url  # noqa: E402
from app.models import (  # noqa: E402
    Agent,
    AgentBelief,
    AgentInterest,
    Location,
    Relationship,
    SimulationClock,
)
from app.models.world import CLUBHOUSE_LOCATIONS  # noqa: E402

EXPECTED_AGENT_COUNT = 8

#: The day and period a fresh village starts on (§5).
STARTING_DAY = 1
STARTING_PERIOD = "MORNING"


@dataclass(frozen=True)
class SeedInterest:
    """A starting interest for an agent (§9).

    ``strength`` is the initial pull toward the topic; the simulation moves it
    from there, so re-seeding never resets it.
    """

    interest: str
    strength: float
    origin: str | None = None


@dataclass(frozen=True)
class SeedAgent:
    """One of the Founding Eight, exactly as §3 describes them."""

    agent_id: str
    identity: str
    voice: str
    interests: tuple[SeedInterest, ...] = ()
    starting_location: str | None = None


@dataclass(frozen=True)
class SeedRelationship:
    """A relationship §3 establishes before day one (§12)."""

    agent_a_id: str
    agent_b_id: str
    notes: str | None = None


# --------------------------------------------------------------------------
# THE FOUNDING EIGHT (§3)
#
# Fill this in from §3 of the build bible. Nothing here is invented: the roster
# is authored content and belongs verbatim to the bible, so the list stays empty
# until §3 is transcribed rather than being filled with plausible-looking
# placeholders that could be mistaken for canon.
#
# Each entry looks like:
#
#     SeedAgent(
#         agent_id="agent_example",
#         identity="who they are, in the bible's words",
#         voice="how they talk",
#         starting_location="espresso_counter",   # must be in CLUBHOUSE_LOCATIONS
#         interests=(
#             SeedInterest("corvid cognition", 0.8, origin="§3"),
#         ),
#     ),
#
# `validate_roster()` below refuses to seed a roster that is not exactly eight
# agents, has duplicate agent_ids, or names a location outside §5.
# --------------------------------------------------------------------------
FOUNDING_EIGHT: tuple[SeedAgent, ...] = ()

#: Relationships §3 establishes up front. Left empty rather than auto-generating
#: all 28 pairs: who knows whom, and how, is authored content too.
FOUNDING_RELATIONSHIPS: tuple[SeedRelationship, ...] = ()


class SeedError(RuntimeError):
    """Raised when the roster is unusable, before anything is written."""


@dataclass
class SeedReport:
    """What a seeding run did, so ``--dry-run`` and a real run print the same shape."""

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = []
        for label, rows in (
            ("created", self.created),
            ("updated", self.updated),
            ("unchanged", self.skipped),
        ):
            lines.append(f"  {label}: {len(rows)}")
            for row in rows:
                lines.append(f"    - {row}")
        return "\n".join(lines)


def validate_roster(
    roster: tuple[SeedAgent, ...],
    relationships: tuple[SeedRelationship, ...] = (),
    *,
    allow_partial: bool = False,
) -> None:
    """Check the roster before touching the database.

    Every problem is raised here rather than as an IntegrityError halfway
    through a transaction, so a bad roster never leaves a half-seeded village.
    """
    if not roster:
        raise SeedError(
            "FOUNDING_EIGHT is empty. Transcribe the roster from §3 of the build "
            "bible into scripts/seed_agents.py before seeding."
        )

    if not allow_partial and len(roster) != EXPECTED_AGENT_COUNT:
        raise SeedError(
            f"Expected {EXPECTED_AGENT_COUNT} founding agents, found {len(roster)}. "
            "Pass --allow-partial if you are deliberately seeding a subset."
        )

    seen: set[str] = set()
    for agent in roster:
        if agent.agent_id in seen:
            raise SeedError(f"Duplicate agent_id in roster: {agent.agent_id!r}")
        seen.add(agent.agent_id)

        if agent.starting_location and agent.starting_location not in CLUBHOUSE_LOCATIONS:
            raise SeedError(
                f"{agent.agent_id!r} starts at {agent.starting_location!r}, which is not "
                f"one of the §5 clubhouse locations: {', '.join(CLUBHOUSE_LOCATIONS)}"
            )

        interests_seen: set[str] = set()
        for interest in agent.interests:
            if interest.interest in interests_seen:
                raise SeedError(
                    f"{agent.agent_id!r} lists the interest {interest.interest!r} twice"
                )
            interests_seen.add(interest.interest)

    for relationship in relationships:
        for side in (relationship.agent_a_id, relationship.agent_b_id):
            if side not in seen:
                raise SeedError(
                    f"Relationship references unknown agent {side!r}; "
                    "relationships may only join agents in the roster."
                )
        if relationship.agent_a_id == relationship.agent_b_id:
            raise SeedError(
                f"Relationship joins {relationship.agent_a_id!r} to itself."
            )


def seed_locations(session: Session, report: SeedReport) -> None:
    """Insert any §5 clubhouse location that is missing."""
    existing = set(session.scalars(select(Location.name)))
    for name in CLUBHOUSE_LOCATIONS:
        if name in existing:
            report.skipped.append(f"location {name}")
            continue
        session.add(Location(name=name))
        report.created.append(f"location {name}")


def seed_clock(session: Session, report: SeedReport) -> None:
    """Create the singleton clock row if the village has no clock yet.

    An existing clock is never rewritten — that would rewind the simulation.
    """
    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is not None:
        report.skipped.append(
            f"clock (day {clock.current_day}, {clock.current_period})"
        )
        return
    session.add(
        SimulationClock(
            id=1,
            current_day=STARTING_DAY,
            current_period=STARTING_PERIOD,
            is_paused=False,
        )
    )
    report.created.append(f"clock (day {STARTING_DAY}, {STARTING_PERIOD})")


def seed_agents(
    session: Session,
    roster: tuple[SeedAgent, ...],
    report: SeedReport,
    *,
    update: bool = False,
) -> None:
    """Insert missing agents and their starting interests.

    An agent that already exists keeps its runtime state. ``update`` refreshes
    the authored fields (identity, voice) only — never ``current_location``,
    ``current_activity`` or ``interaction_target``, which belong to the running
    simulation.
    """
    existing = {a.agent_id: a for a in session.scalars(select(Agent))}

    for spec in roster:
        agent = existing.get(spec.agent_id)
        if agent is None:
            session.add(
                Agent(
                    agent_id=spec.agent_id,
                    identity=spec.identity,
                    voice=spec.voice,
                    current_location=spec.starting_location,
                )
            )
            report.created.append(f"agent {spec.agent_id}")
        elif update and (agent.identity != spec.identity or agent.voice != spec.voice):
            agent.identity = spec.identity
            agent.voice = spec.voice
            report.updated.append(f"agent {spec.agent_id} (identity/voice)")
        else:
            report.skipped.append(f"agent {spec.agent_id}")

        seed_interests(session, spec, report)

    # Agents must exist before interests and relationships can reference them.
    session.flush()


def seed_interests(session: Session, spec: SeedAgent, report: SeedReport) -> None:
    """Insert any starting interest this agent does not already have.

    Existing interests keep their ``strength``: it drifts as the agent engages
    with a topic (§9), and re-seeding must not undo that.
    """
    existing = set(
        session.scalars(
            select(AgentInterest.interest).where(AgentInterest.agent_id == spec.agent_id)
        )
    )
    for interest in spec.interests:
        label = f"interest {spec.agent_id}/{interest.interest}"
        if interest.interest in existing:
            report.skipped.append(label)
            continue
        session.add(
            AgentInterest(
                agent_id=spec.agent_id,
                interest=interest.interest,
                strength=interest.strength,
                origin=interest.origin,
            )
        )
        report.created.append(label)


def seed_relationships(
    session: Session,
    relationships: tuple[SeedRelationship, ...],
    report: SeedReport,
) -> None:
    """Insert authored relationships, treating a pair as unordered."""
    existing = {
        frozenset((row.agent_a_id, row.agent_b_id))
        for row in session.scalars(select(Relationship))
    }
    for spec in relationships:
        pair = frozenset((spec.agent_a_id, spec.agent_b_id))
        label = f"relationship {spec.agent_a_id} <-> {spec.agent_b_id}"
        if pair in existing:
            report.skipped.append(label)
            continue
        session.add(
            Relationship(
                agent_a_id=spec.agent_a_id,
                agent_b_id=spec.agent_b_id,
                notes=spec.notes,
            )
        )
        existing.add(pair)
        report.created.append(label)


def reset_seeded_rows(session: Session, report: SeedReport) -> None:
    """Delete every row this script creates, for a throwaway dev database.

    Deletion order respects the foreign keys, and nothing cascades: if research,
    memories or wall posts reference an agent, the delete fails loudly rather
    than taking that work down with it.
    """
    counts = {
        "relationships": session.query(Relationship).delete(),
        "agent_interests": session.query(AgentInterest).delete(),
        "agent_beliefs": session.query(AgentBelief).delete(),
        "agents": session.query(Agent).delete(),
        "locations": session.query(Location).delete(),
        "simulation_clock": session.query(SimulationClock).delete(),
    }
    for table, deleted in counts.items():
        if deleted:
            report.updated.append(f"deleted {deleted} row(s) from {table}")


def run(
    session: Session,
    roster: tuple[SeedAgent, ...] | None = None,
    relationships: tuple[SeedRelationship, ...] | None = None,
    *,
    update: bool = False,
    reset: bool = False,
    allow_partial: bool = False,
) -> SeedReport:
    """Seed the world in one transaction. The caller commits.

    ``roster`` and ``relationships`` default to the module constants, read at
    call time so tests can supply their own.
    """
    roster = FOUNDING_EIGHT if roster is None else roster
    relationships = FOUNDING_RELATIONSHIPS if relationships is None else relationships
    validate_roster(roster, relationships, allow_partial=allow_partial)

    report = SeedReport()
    if reset:
        reset_seeded_rows(session, report)
        session.flush()

    seed_locations(session, report)
    seed_clock(session, report)
    seed_agents(session, roster, report, update=update)
    seed_relationships(session, relationships, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change, then roll back",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="refresh identity/voice on agents that already exist",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete seeded rows first (throwaway databases only)",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help=f"permit a roster that is not exactly {EXPECTED_AGENT_COUNT} agents",
    )
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")

    session = SessionLocal()
    try:
        report = run(
            session,
            update=args.update,
            reset=args.reset,
            allow_partial=args.allow_partial,
        )
    except SeedError as exc:
        session.rollback()
        print(f"\nRefusing to seed: {exc}", file=sys.stderr)
        return 1
    else:
        if args.dry_run:
            session.rollback()
            print("\nDry run — nothing was written.")
        else:
            session.commit()
        print(report.render())
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
