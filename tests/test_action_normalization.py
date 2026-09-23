"""Unit tests for action normalization: unblocking Rabbit Hole contributions
and START_CONVERSATION/READ_WALL_POST from hard-rejecting on omissions the
orchestrator can safely infer instead (the "Culture Ignition Gap" fixes).

Runs against a throwaway in-memory-per-file SQLite database built straight
from the ORM metadata (no Alembic, no fixture providers) — fast, and every
test gets its own isolated schema.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401 -- registers every model on Base.metadata
from app.db.base import Base
from app.db.models.agents import Agent, Relationship
from app.db.models.rabbit_holes import RabbitHole
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.enums import WallPostType
from app.schemas.actions import ActionType, AgentAction, AgentDecision, TargetKind
from app.services import rabbit_holes as rh
from app.services.orchestrator import (
    DecisionRejected,
    execute_decision,
    normalize_decision,
    validate_decision,
)


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'action_normalization.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def _agent(session: Session, agent_id: str) -> Agent:
    agent = Agent(agent_id=agent_id, identity="a resident", voice="plain")
    session.add(agent)
    session.flush()
    return agent


def _clock(session: Session) -> SimulationClock:
    clock = SimulationClock(id=1, current_day=1, current_period="MORNING")
    session.add(clock)
    session.flush()
    return clock


def _decision(actions: list[AgentAction]) -> AgentDecision:
    return AgentDecision(summary="doing something", activity="thinking", actions=actions)


# ---------------------------------------------------------------------------
# 1. Auto-join a Rabbit Hole on contribution
# ---------------------------------------------------------------------------

def test_contribute_to_rabbit_hole_does_not_reject_non_member(db_session):
    agent = _agent(db_session, "agent_a")
    hole = RabbitHole(title="a shared mystery", originating_agent_id=agent.agent_id)
    db_session.add(hole)
    db_session.flush()
    assert not rh.is_member(db_session, hole.id, agent.agent_id)

    action = AgentAction(
        type=ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
        content="here is a new finding",
        target_int_id=hole.id,
        target_kind=TargetKind.RABBIT_HOLE,
    )
    decision = _decision([action])

    # Must NOT raise "not a member of rabbit hole ... — JOIN_RABBIT_HOLE first".
    validate_decision(decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session)


def test_contribute_to_rabbit_hole_auto_enrolls_and_flags_implicit_join(db_session):
    agent = _agent(db_session, "agent_a")
    clock = _clock(db_session)
    hole = RabbitHole(title="a shared mystery", originating_agent_id=agent.agent_id)
    db_session.add(hole)
    db_session.flush()

    action = AgentAction(
        type=ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
        content="here is a new finding",
        target_int_id=hole.id,
        target_kind=TargetKind.RABBIT_HOLE,
    )
    decision = _decision([action])

    from app.db.models.events import Event, EventType

    execute_decision(
        db_session, agent, decision, clock, "corr-1",
        conversation=None, settings=None, llm_provider=None,
    )

    assert rh.is_member(db_session, hole.id, agent.agent_id)
    join_event = db_session.query(Event).filter_by(event_type=EventType.RABBIT_HOLE_JOINED).one()
    assert join_event.payload["implicit_join"] is True
    assert join_event.payload["rabbit_hole_id"] == hole.id


def test_contribute_to_rabbit_hole_does_not_double_join_existing_member(db_session):
    agent = _agent(db_session, "agent_a")
    clock = _clock(db_session)
    hole = RabbitHole(title="a shared mystery", originating_agent_id=agent.agent_id)
    db_session.add(hole)
    db_session.flush()
    rh.join(db_session, hole.id, agent.agent_id, clock, "corr-0")

    from app.db.models.events import Event, EventType

    action = AgentAction(
        type=ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
        content="another finding",
        target_int_id=hole.id,
        target_kind=TargetKind.RABBIT_HOLE,
    )
    execute_decision(
        db_session, agent, _decision([action]), clock, "corr-1",
        conversation=None, settings=None, llm_provider=None,
    )

    join_events = db_session.query(Event).filter_by(event_type=EventType.RABBIT_HOLE_JOINED).all()
    assert len(join_events) == 1  # the explicit join from setup, not a second implicit one


def test_leave_and_resolve_rabbit_hole_still_require_membership(db_session):
    """The relaxation is scoped to CONTRIBUTE_TO_RABBIT_HOLE only."""
    agent = _agent(db_session, "agent_a")
    hole = RabbitHole(title="a shared mystery", originating_agent_id=agent.agent_id)
    db_session.add(hole)
    db_session.flush()

    leave_action = AgentAction(
        type=ActionType.LEAVE_RABBIT_HOLE,
        target_int_id=hole.id,
        target_kind=TargetKind.RABBIT_HOLE,
    )
    with pytest.raises(DecisionRejected, match="JOIN_RABBIT_HOLE first"):
        validate_decision(
            _decision([leave_action]), agent=agent,
            present_agent_ids=(agent.agent_id,), session=db_session,
        )


# ---------------------------------------------------------------------------
# 2. START_CONVERSATION payload normalization
# ---------------------------------------------------------------------------

def test_normalize_infers_single_copresent_agent_as_target(db_session):
    agent = _agent(db_session, "agent_a")
    other = _agent(db_session, "agent_b")

    action = AgentAction(type=ActionType.START_CONVERSATION)
    decision = _decision([action])

    normalize_decision(
        decision, agent=agent,
        present_agent_ids=(agent.agent_id, other.agent_id),
        session=db_session,
    )

    assert action.target_agent_id == other.agent_id
    assert (action.content or "").strip()  # a fallback opener was filled in


def test_normalize_picks_highest_affinity_when_multiple_copresent(db_session):
    agent = _agent(db_session, "agent_a")
    familiar = _agent(db_session, "agent_familiar")
    stranger = _agent(db_session, "agent_stranger")

    db_session.add(
        Relationship(
            agent_a_id="agent_a", agent_b_id="agent_familiar",
            familiarity=80.0, intellectual_affinity=70.0,
        )
    )
    db_session.flush()

    action = AgentAction(type=ActionType.START_CONVERSATION)
    decision = _decision([action])

    normalize_decision(
        decision, agent=agent,
        present_agent_ids=(agent.agent_id, familiar.agent_id, stranger.agent_id),
        session=db_session,
    )

    assert action.target_agent_id == familiar.agent_id


def test_normalize_does_not_override_explicit_target_agent_id(db_session):
    agent = _agent(db_session, "agent_a")
    chosen = _agent(db_session, "agent_chosen")
    other = _agent(db_session, "agent_other")

    action = AgentAction(type=ActionType.START_CONVERSATION, target_agent_id=chosen.agent_id, content="hey there")
    decision = _decision([action])

    normalize_decision(
        decision, agent=agent,
        present_agent_ids=(agent.agent_id, chosen.agent_id, other.agent_id),
        session=db_session,
    )

    assert action.target_agent_id == chosen.agent_id
    assert action.content == "hey there"


def test_normalize_leaves_target_unset_with_no_one_copresent(db_session):
    agent = _agent(db_session, "agent_a")
    action = AgentAction(type=ActionType.START_CONVERSATION)
    decision = _decision([action])

    normalize_decision(
        decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session,
    )

    assert action.target_agent_id is None
    with pytest.raises(DecisionRejected, match="requires a target_agent_id"):
        validate_decision(decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session)


# ---------------------------------------------------------------------------
# 3. READ_WALL_POST normalization
# ---------------------------------------------------------------------------

def test_normalize_defaults_empty_wall_post_target_to_latest_post(db_session):
    agent = _agent(db_session, "agent_a")
    author = _agent(db_session, "agent_author")
    post = ResearchWallPost(
        agent_id=author.agent_id, post_type=WallPostType.FINDING, content="a headline",
    )
    db_session.add(post)
    db_session.flush()

    action = AgentAction(type=ActionType.READ_WALL_POST)
    decision = _decision([action])

    normalize_decision(decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session)

    assert action.target_wall_post_id == post.id
    # And it now clears validation instead of "READ_WALL_POST requires target_wall_post_id".
    validate_decision(decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session)


def test_normalize_wall_post_prefers_unread_over_already_read(db_session):
    agent = _agent(db_session, "agent_a")
    author = _agent(db_session, "agent_author")
    older_read = ResearchWallPost(agent_id=author.agent_id, post_type=WallPostType.FINDING, content="old, already read")
    newer_unread = ResearchWallPost(agent_id=author.agent_id, post_type=WallPostType.FINDING, content="newer, unread")
    db_session.add_all([older_read, newer_unread])
    db_session.flush()

    from app.domain.enums import ExposureType
    from app.services.exposure import expose

    expose(
        db_session, agent_id=agent.agent_id, entity_type="research_wall",
        entity_id=newer_unread.id, exposure_type=ExposureType.SHARED_FINDING,
    )
    db_session.flush()

    action = AgentAction(type=ActionType.READ_WALL_POST)
    decision = _decision([action])
    normalize_decision(decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session)

    # newer_unread is already exposed; older_read is not — the unread one wins
    # even though it is the older post.
    assert action.target_wall_post_id == older_read.id


def test_normalize_does_not_override_explicit_wall_post_target(db_session):
    agent = _agent(db_session, "agent_a")
    author = _agent(db_session, "agent_author")
    chosen = ResearchWallPost(agent_id=author.agent_id, post_type=WallPostType.FINDING, content="chosen")
    other = ResearchWallPost(agent_id=author.agent_id, post_type=WallPostType.FINDING, content="other")
    db_session.add_all([chosen, other])
    db_session.flush()

    action = AgentAction(type=ActionType.READ_WALL_POST, target_int_id=chosen.id, target_kind=TargetKind.WALL_POST)
    decision = _decision([action])

    normalize_decision(decision, agent=agent, present_agent_ids=(agent.agent_id,), session=db_session)

    assert action.target_wall_post_id == chosen.id
