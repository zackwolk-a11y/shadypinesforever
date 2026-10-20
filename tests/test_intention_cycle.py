"""The intention -> action bridge, end to end through the real event loop.

A scripted provider stands in for the model: each test hands it the exact
decisions to return, so every assertion is about what the *engine* does with
a decision — validation, execution, memory, intentions, feedback — through
the same ``run_next_event`` path a live run takes. Research runs on the
fixture research provider; the scripted provider delegates any non-decision
call (query plans, synthesis) to the fixture LLM.

The scripted provider reports ``is_fixture=False`` on purpose, to show that
``cycle_proof`` calls a chain GENUINE only from that flag — and the fixture
test at the bottom shows the opposite.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models.agents import Agent
from app.db.models.conversations import Conversation
from app.db.models.events import Event
from app.db.models.intentions import AgentFeedback, Intention
from app.db.models.memory import Memory
from app.db.models.research import ResearchSession
from app.db.models.world import SimulationClock
from app.domain.enums import ConversationTrigger, EventType, IntentionStatus
from app.providers.llm.base import LLMError, LLMResult, LLMSchemaError, LLMUsage
from app.providers.llm.fixture import FixtureLLMProvider
from app.schemas.actions import ActionType, AgentAction, AgentDecision, IntentionDraft
from app.services import cycle_proof, intentions, turn_feedback
from app.services.orchestrator import run_next_event
from tests.test_circuit_breaker import _settings as _base_settings


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cycle.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        Agent(agent_id="agent_a", identity="a curious resident", voice="warm"),
        Agent(agent_id="agent_b", identity="a careful resident", voice="dry"),
        Agent(agent_id="agent_c", identity="a third resident", voice="quiet"),
        SimulationClock(id=1, current_day=2, current_period="AFTERNOON", is_paused=False),
    ])
    session.commit()
    yield session
    session.close()


def _settings(**overrides):
    return replace(_base_settings(), morning_gathering="off", **overrides)


class Scripted:
    """Returns the next scripted decision; anything else goes to the fixture."""

    name = "scripted"
    is_fixture = False

    def __init__(self):
        self.queue = []
        self.prompts = []
        self._fixture = FixtureLLMProvider()

    def push(self, decision_or_fn):
        self.queue.append(decision_or_fn)

    def complete(self, *, system, user, model, purpose, output_type, max_tokens=None):
        if output_type is not AgentDecision:
            return self._fixture.complete(system=system, user=user, model=model, purpose=purpose,
                                          output_type=output_type, max_tokens=max_tokens)
        self.prompts.append(user)
        item = self.queue.pop(0)
        decision = item(user) if callable(item) else item
        return LLMResult(output=decision, usage=LLMUsage(), provider=self.name, model="scripted",
                         is_fixture=False, latency_ms=1)


def _d(summary, *actions, **kw):
    return AgentDecision(summary=summary, activity="talking", actions=list(actions), **kw)


def _speak(text):
    return AgentAction(type=ActionType.SPEAK, content=text)


def _step(db, provider, settings=None, agent=None):
    outcome = run_next_event(db, settings=settings or _settings(), provider=provider, force_agent_id=agent)
    db.commit()
    return outcome


def _run_conversation(db, provider, *, record_intention=True):
    """A starts a conversation with B; B commits to research; A leaves."""
    provider.push(_d("I want to ask B about tide pools.",
                     AgentAction(type=ActionType.START_CONVERSATION, target_agent_id="agent_b",
                                 content="Do tide pools bounce back after big storms?")))
    _step(db, provider, agent="agent_a")
    provider.push(_d(
        "B offers to look it up.",
        _speak("Honestly not sure. I'll research how tide pools recover after storms."),
        new_intention=IntentionDraft(what="research how tide pools recover after storms",
                                     planned_action="START_RESEARCH", with_agent_id="agent_a")
        if record_intention else None,
    ))
    _step(db, provider)  # next speaker: B
    provider.push(_d("A is glad.", _speak("Please do — I keep wondering about the anemones.")))
    _step(db, provider)  # A
    provider.push(_d("B adds a thought.", _speak("Anemones might be the slowest to come back.")))
    _step(db, provider)  # B
    provider.push(_d("A heads off.", AgentAction(type=ActionType.LEAVE_CONVERSATION)))
    _step(db, provider)  # A leaves -> conversation closes, memories form
    return db.scalars(select(Conversation)).one()


def _follow_through(explicit=True, cite=True):
    def build(user):
        intention_ids = [int(i) for i in re.findall(r"\[I(\d+)\]", user)]
        memory_ids = [int(m) for m in re.findall(r"\[M(\d+)\][^\n]*\[I\d+\]", user)]
        return _d(
            "Following through on what I told A.",
            AgentAction(type=ActionType.START_RESEARCH, content="How do tide pools recover after storms?"),
            fulfills_intention_id=intention_ids[0] if explicit else 0,
            drew_on_memory_ids=memory_ids if cite else [],
        )
    return build


def test_full_cycle_is_proven_from_rows(db):
    provider = Scripted()
    conv = _run_conversation(db, provider)
    assert conv.status.value == "ENDED"
    intention = db.scalars(select(Intention)).one()
    assert intention.status is IntentionStatus.OPEN
    assert intention.source_conversation_id == conv.id

    # The memory of the conversation carries what was actually said and the promise.
    memory = db.scalars(
        select(Memory).where(Memory.agent_id == "agent_b", Memory.content.contains(f"[I{intention.id}]"))
    ).one()
    assert "tide pools" in memory.content and conv.id in memory.related_conversation_ids

    provider.push(_follow_through())
    outcome = _step(db, provider, agent="agent_b")
    prompt = provider.prompts[-1]
    assert f"[I{intention.id}]" in prompt and f"[M{memory.id}]" in prompt
    assert outcome.executed == ["START_RESEARCH"]

    db.refresh(intention)
    assert intention.status is IntentionStatus.FULFILLED
    assert intention.fulfilled_explicitly is True
    assert intention.fulfilled_entity["type"] == "research_session"
    used = db.scalars(select(Event).where(Event.event_type == EventType.MEMORY_USED)).one()
    assert used.payload["memory_ids"] == [memory.id]
    # A learns B followed through (the research is B's, but the SOCIAL memory
    # only forms for actions visible to A — START_RESEARCH is not, so none).
    assert not db.scalars(select(Memory).where(Memory.agent_id == "agent_a",
                                               Memory.content.contains("followed through"))).first()

    best = cycle_proof.evaluate(db)[0]
    assert [link.status for link in best.links] == ["PROVEN"] * 4, [(l.name, l.why) for l in best.links]
    # Live (scripted) decisions, but the research ran on the fixture search
    # provider — so the chain is complete yet honestly *not* called genuine.
    assert not best.live and "FIXTURE SEARCH" in best.verdict.upper()
    research = db.scalars(select(ResearchSession)).one()
    research.is_fixture = False  # as if RESEARCH_PROVIDER were live
    db.commit()
    best = cycle_proof.evaluate(db)[0]
    assert best.live and best.verdict == "GENUINE CYCLE PROVEN"


def test_inferred_fulfilment_and_uncited_memory_are_only_partial(db):
    provider = Scripted()
    _run_conversation(db, provider)
    provider.push(_follow_through(explicit=False, cite=False))
    _step(db, provider, agent="agent_b")
    intention = db.scalars(select(Intention)).one()
    assert intention.status is IntentionStatus.FULFILLED and intention.fulfilled_explicitly is False
    best = cycle_proof.evaluate(db)[0]
    statuses = {link.name: link.status for link in best.links}
    assert statuses["executed action"] == "PARTIAL"
    assert statuses["remembered experience"] == "PARTIAL"
    assert best.verdict == "PARTIAL CYCLE"


def test_saying_it_without_recording_it_leaves_feedback_and_no_cycle(db):
    provider = Scripted()
    _run_conversation(db, provider, record_intention=False)
    assert db.scalars(select(Intention)).first() is None
    note = db.scalars(select(AgentFeedback).where(AgentFeedback.agent_id == "agent_b")).one()
    assert note.kind == "unrecorded_commitment" and "I'll research" in note.note
    assert cycle_proof.evaluate(db) == []

    # The note was shown on B's very next turn (its second line in the same
    # conversation, prompt #3: A, B, A, B, A) and judged against that turn,
    # which made no new unrecorded promise.
    assert "NOTES ON YOUR RECENT TURNS" in provider.prompts[3]
    assert "NOTES ON YOUR RECENT TURNS" not in provider.prompts[1]
    db.refresh(note)
    assert note.shown_at is not None and note.addressed is True

    # Shown once only; and a near-miss planned_action is normalized, not rejected.
    provider.push(_d("B writes it down this time.", AgentAction(type=ActionType.WRITE_NOTE, content="tide pools"),
                     new_intention=IntentionDraft(what="research tide pool recovery",
                                                  planned_action="research")))
    _step(db, provider, agent="agent_b")
    assert "NOTES ON YOUR RECENT TURNS" not in provider.prompts[-1]
    assert db.scalars(select(Intention)).one().planned_action == "START_RESEARCH"


def test_bad_intention_references_are_rejected_with_a_reason(db):
    provider = Scripted()
    provider.push(_d("claims a fulfilment with nothing to show", AgentAction(type=ActionType.OBSERVE),
                     fulfills_intention_id=999))
    provider.push(_d("tries again", AgentAction(type=ActionType.OBSERVE)))
    outcome = _step(db, provider, agent="agent_a")
    assert outcome.rejected_reason is None and outcome.executed == ["OBSERVE"]
    note = db.scalars(select(AgentFeedback)).one()
    assert note.kind == "corrected_decision" and "no intention [I999]" in note.note


def test_second_conversation_cannot_orphan_the_first(db):
    provider = Scripted()
    provider.push(_d("A starts one.", AgentAction(type=ActionType.START_CONVERSATION, target_agent_id="agent_b",
                                                   content="Quick question about the zine?")))
    _step(db, provider, agent="agent_a")
    start = AgentAction(type=ActionType.START_CONVERSATION, target_agent_id="agent_a", content="Hey A?")
    provider.push(_d("C tries to start another.", start))
    provider.push(_d("C tries again.", start))
    outcome = _step(db, provider, agent="agent_c")
    assert "another conversation is already under way" in (outcome.rejected_reason or "")
    assert "START_CONVERSATION" not in provider.prompts[-1].split("AVAILABLE ACTIONS:")[1].split("\n")[0]
    assert len(db.scalars(select(Conversation)).all()) == 1


def test_intentions_expire_honestly(db, monkeypatch):
    from app.services import clock as clock_service

    provider = Scripted()
    _run_conversation(db, provider)
    monkeypatch.setenv("INTENTION_WINDOW_PERIODS", "2")
    clock = db.scalars(select(SimulationClock)).one()
    clock_service.advance(db, clock)
    clock_service.advance(db, clock)
    db.commit()
    intention = db.scalars(select(Intention)).one()
    assert intention.status is IntentionStatus.EXPIRED
    assert db.scalars(select(AgentFeedback).where(AgentFeedback.kind == "intention_expired")).one()
    assert db.scalars(select(Memory).where(Memory.content.contains("never got to"))).one()


def test_morning_gathering_is_not_a_voluntary_meeting(db):
    clock = db.scalars(select(SimulationClock)).one()
    conv = Conversation(trigger_type=ConversationTrigger.MORNING_GATHERING,
                        participant_ids=["agent_a", "agent_b"], started_sim_day=2, started_sim_period="MORNING")
    db.add(conv)
    db.flush()
    intentions.form(db, "agent_b", IntentionDraft(what="post a note", planned_action="POST_TO_WALL"),
                    clock, None, conversation=conv)
    db.commit()
    best = cycle_proof.evaluate(db)[0]
    assert best.links[0].status == "MISSING" and "compulsory" in best.links[0].why


def test_network_failure_pauses_instead_of_burning_the_agents_turn(db):
    class Flaky:
        name = "flaky"
        is_fixture = False

        def complete(self, **kw):
            raise LLMError("Claude CLI failed: no provider detail (exit=1)")

    outcome = _step(db, Flaky(), agent="agent_a")
    assert outcome.provider_unavailable is True
    clock = db.scalars(select(SimulationClock)).one()
    assert clock.is_paused and clock.pause_reason == "PAUSED_PROVIDER_ERROR"
    kinds = {e.event_type for e in db.scalars(select(Event))}
    assert EventType.SIMULATION_PAUSED_PROVIDER_ERROR in kinds
    assert EventType.INVALID_AGENT_DECISION not in kinds and EventType.AGENT_ACTED not in kinds


def test_malformed_model_output_is_still_the_agents_invalid_turn(db):
    class Garbled:
        name = "garbled"
        is_fixture = False

        def complete(self, **kw):
            raise LLMSchemaError("output failed AgentDecision validation")

    outcome = _step(db, Garbled(), agent="agent_a")
    assert outcome.provider_unavailable is False
    clock = db.scalars(select(SimulationClock)).one()
    assert not clock.is_paused
    assert db.scalars(select(Event).where(Event.event_type == EventType.INVALID_AGENT_DECISION)).one()
    assert db.scalars(select(AgentFeedback)).one().kind == "rejected_decision"


def test_per_period_cap_keeps_budget_for_later(db):
    from app.services import scheduler

    settings = _settings(max_period_agent_activations=2)
    provider = Scripted()
    for _ in range(2):
        provider.push(_d("quiet", AgentAction(type=ActionType.OBSERVE)))
        _step(db, provider, settings=settings, agent="agent_a")
    clock = db.scalars(select(SimulationClock)).one()
    assert not scheduler.has_budget(db, "agent_a", clock, settings)
    assert scheduler.has_budget(db, "agent_a", clock, _settings())  # daily cap alone: still 4 left


def test_unrecorded_commitment_detector_is_narrow():
    said = _d("x", _speak("Good question — I'll dig into it tonight."))
    assert turn_feedback.find_unrecorded_commitment(said)
    recorded = _d("x", _speak("I'll dig into it tonight."),
                  new_intention=IntentionDraft(what="dig in", planned_action="START_RESEARCH"))
    assert turn_feedback.find_unrecorded_commitment(recorded) is None
    assert turn_feedback.find_unrecorded_commitment(_d("x", _speak("Illness is hard to model."))) is None


def test_feedback_control_arm_hides_notes_but_still_judges_them(db):
    provider = Scripted()
    off = _settings(feedback_notes="off")
    provider.push(_d("A promises aloud.", AgentAction(type=ActionType.WRITE_NOTE, content="x"),
                     public_dialogue="I'll sort the zine archive tomorrow."))
    _step(db, provider, settings=off, agent="agent_a")
    provider.push(_d("A again.", AgentAction(type=ActionType.OBSERVE)))
    _step(db, provider, settings=off, agent="agent_a")
    assert "NOTES ON YOUR RECENT TURNS" not in provider.prompts[-1]
    note = db.scalars(select(AgentFeedback)).one()
    assert note.kind == "unrecorded_commitment" and note.addressed is True
