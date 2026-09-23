"""Reproduction tests for the provider rate-limit circuit breaker.

A live LLM call can fail non-retryably in two different ways: the boundary
itself is broken (bad credentials, a decommissioned model, ...), or the
provider is simply refusing more calls for now (HTTP 429, a session/weekly/
usage quota, a depleted credit balance). Only the second case is a genuine
circuit-breaker condition — Village policy is to pause cleanly and resume
later, never to fabricate a degraded, ungrounded, or empty turn in its place.

These tests exercise that path at three levels:

1. The provider adapters (``app/providers/llm/anthropic.py``,
   ``app/providers/llm/claude_cli.py``) type a mocked 429/quota failure as
   :class:`~app.providers.llm.base.LLMRateLimited`, never a bare
   :class:`~app.providers.llm.base.LLMError`.
2. The orchestrator's tick (``run_next_event``), run end-to-end against a
   real SQLite database built straight from the ORM metadata (no mocks
   below the provider boundary), catches that exception and — in the same
   transaction, with no decision ever normalized/validated/executed —
   flips ``SimulationClock`` to ``PAUSED_RATE_LIMIT`` and logs a single
   ``SIMULATION_PAUSED_RATE_LIMIT`` event carrying the checkpoint and the
   turn's correlation id.
3. DB safety: the pause is only ever visible after a real commit (a
   rollback leaves the previous, still-consistent state — proving there is
   no window where the clock says "paused" but nothing explains why, or
   vice versa), and ``scripts/run_day.py``'s tick loop exits cleanly (75,
   the existing provider-unavailable checkpoint code) instead of crashing
   or continuing into a fabricated turn.
"""

from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import httpx2
import pytest
from pydantic import BaseModel

import app.db.models  # noqa: F401 -- registers every model on Base.metadata
import scripts.run_day as run_day
from app.db.base import Base
from app.db.models.agents import Agent
from app.db.models.events import Event
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, PauseReason
from app.providers.llm.anthropic import AnthropicLLMProvider
from app.providers.llm.base import LLMProviderUnavailable, LLMRateLimited
from app.providers.llm.claude_cli import ClaudeCLILLMProvider
from app.services.orchestrator import EventOutcome, run_next_event
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


class _Output(BaseModel):
    ok: bool


# ---------------------------------------------------------------------------
# 1. Provider adapters type a 429 / quota failure as LLMRateLimited
# ---------------------------------------------------------------------------


def test_anthropic_429_is_typed_as_rate_limited(monkeypatch):
    provider = AnthropicLLMProvider(api_key="test-key")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(429, request=request)
    rate_limit_error = provider._anthropic.RateLimitError(
        "Number of request tokens has exceeded your per-minute rate limit.",
        response=response,
        body=None,
    )
    monkeypatch.setattr(
        provider._client.messages, "create", lambda *a, **k: (_ for _ in ()).throw(rate_limit_error)
    )

    with pytest.raises(LLMRateLimited, match="rate-limited"):
        provider.complete(
            system="system", user="user", model="test",
            purpose="agent_decision", output_type=_Output,
        )
    # LLMRateLimited is-a LLMProviderUnavailable: every existing non-retryable
    # call site (run_next_event's `except LLMProviderUnavailable`, prior
    # tests written against that type) still catches it.
    with pytest.raises(LLMProviderUnavailable):
        provider.complete(
            system="system", user="user", model="test",
            purpose="agent_decision", output_type=_Output,
        )


def test_claude_cli_quota_exhaustion_is_typed_as_rate_limited(monkeypatch):
    response = subprocess.CompletedProcess(
        args=["claude"], returncode=1,
        stdout=json.dumps({"is_error": True, "result": "You've hit your weekly limit; resets Monday."}),
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: response)
    provider = ClaudeCLILLMProvider(binary="/usr/bin/false")

    with pytest.raises(LLMRateLimited, match="weekly limit"):
        provider.complete(
            system="system", user="user", model="test",
            purpose="agent_decision", output_type=_Output,
        )


def test_claude_cli_raw_429_is_typed_as_rate_limited(monkeypatch):
    response = subprocess.CompletedProcess(
        args=["claude"], returncode=1,
        stdout=json.dumps({"is_error": True, "result": "upstream request failed: HTTP 429 Too Many Requests"}),
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: response)
    provider = ClaudeCLILLMProvider(binary="/usr/bin/false")

    with pytest.raises(LLMRateLimited, match="429"):
        provider.complete(
            system="system", user="user", model="test",
            purpose="agent_decision", output_type=_Output,
        )


def test_claude_cli_auth_failure_stays_provider_unavailable_not_rate_limited(monkeypatch):
    """Bad credentials are a broken boundary, not a quota — must not be
    mistaken for a circuit-breaker condition the simulation should just
    wait out."""
    response = subprocess.CompletedProcess(
        args=["claude"], returncode=1,
        stdout=json.dumps({"is_error": True, "result": "Authentication failed: invalid API key"}),
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: response)
    provider = ClaudeCLILLMProvider(binary="/usr/bin/false")

    with pytest.raises(LLMProviderUnavailable) as exc_info:
        provider.complete(
            system="system", user="user", model="test",
            purpose="agent_decision", output_type=_Output,
        )
    assert not isinstance(exc_info.value, LLMRateLimited)


# ---------------------------------------------------------------------------
# 2 & 3. End-to-end: run_next_event against a real SQLite database
# ---------------------------------------------------------------------------


class _RateLimitedProvider:
    """A fake provider that always raises LLMRateLimited — the mock 429."""

    name = "fake_rate_limited"
    is_fixture = False

    def complete(self, **kwargs):
        raise LLMRateLimited("Anthropic rate-limited 'agent_decision': mock 429 response")


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'circuit_breaker.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def _settings():
    from app.core.config import Settings

    return Settings(
        app_env="test", database_url="sqlite://",
        llm_provider="fixture", anthropic_api_key=None,
        agent_model="test-model", research_model="test-model", report_model="test-model",
        research_effort="low", report_effort="low",
        max_conversation_turns=8, max_context_memories=6, max_context_recent_findings=5,
        max_context_wall_headlines=5, max_daily_agent_activations=6,
        research_provider="fixture", brave_search_api_key=None, tavily_api_key=None,
        max_research_sessions_per_agent_per_day=2, max_search_queries_per_session=3,
        max_sources_per_query=5, max_follow_up_depth=2,
        target_research_sessions_per_village_day=4, max_evidence_tokens_per_research_session=6000,
        max_fetched_sources_per_session=3, max_sources_per_domain_per_session=2,
        reflection_significance_threshold=100.0, max_context_reflections=3,
        max_context_questions=3, max_report_findings=8, max_report_wall_posts=6,
        max_report_rabbit_holes=6, max_report_conversations=6, max_report_memory_events=8,
        max_report_reflections=6, max_report_belief_changes=6,
        max_tokens_agent_decision=1536, max_tokens_search_query=512,
        max_tokens_research_synthesis=8192, max_tokens_reflection=1024, max_tokens_daily_report=4096,
    )


def _seed(session) -> tuple[Agent, SimulationClock]:
    agent = Agent(agent_id="agent_a", identity="a resident", voice="plain")
    # AFTERNOON, not the first period of the day: avoids run_next_event's
    # own morning-gathering auto-start, which is irrelevant to this test and
    # would otherwise open a conversation before the activation under test.
    clock = SimulationClock(id=1, current_day=3, current_period="AFTERNOON", is_paused=False)
    session.add_all([agent, clock])
    session.commit()
    return agent, clock


def test_mock_429_triggers_paused_rate_limit(db_session):
    agent, clock = _seed(db_session)

    outcome = run_next_event(
        db_session, settings=_settings(), provider=_RateLimitedProvider(),
        force_agent_id=agent.agent_id,
    )
    db_session.commit()

    assert outcome.provider_unavailable is True
    assert outcome.rate_limited is True
    assert outcome.decision is None
    assert "mock 429" in outcome.rejected_reason

    db_session.refresh(clock)
    assert clock.is_paused is True
    assert clock.pause_reason == PauseReason.RATE_LIMIT.value
    assert clock.pause_reason == "PAUSED_RATE_LIMIT"
    # The checkpoint is exactly where the clock already was — no state was
    # advanced, skipped, or guessed at in order to "keep the simulation
    # moving".
    assert clock.current_day == 3
    assert clock.current_period == "AFTERNOON"


def test_mock_429_logs_one_clean_pause_event_with_correlation_id(db_session):
    agent, clock = _seed(db_session)

    outcome = run_next_event(
        db_session, settings=_settings(), provider=_RateLimitedProvider(),
        force_agent_id=agent.agent_id,
    )
    db_session.commit()

    pause_events = db_session.scalars(
        select(Event).where(Event.event_type == EventType.SIMULATION_PAUSED_RATE_LIMIT)
    ).all()
    assert len(pause_events) == 1
    pause_event = pause_events[0]
    assert pause_event.correlation_id == outcome.correlation_id
    assert pause_event.agent_id == agent.agent_id
    assert pause_event.payload["checkpoint_day"] == 3
    assert pause_event.payload["checkpoint_period"] == "AFTERNOON"
    assert pause_event.payload["checkpoint_agent_id"] == agent.agent_id
    assert pause_event.id in outcome.event_ids

    # It caused-by the woke event of the same activation, not orphaned.
    woke_event = db_session.scalars(
        select(Event).where(Event.event_type == EventType.AGENT_WOKE)
    ).one()
    assert pause_event.causation_id == woke_event.id


def test_mock_429_never_falls_back_to_a_degraded_or_invalid_turn(db_session):
    """No INVALID_AGENT_DECISION, no AGENT_ACTED — a rate-limited turn is
    not recorded as "the agent decided badly" or "the agent did something";
    it simply never happened, and resumes untouched once unpaused."""
    agent, clock = _seed(db_session)

    run_next_event(
        db_session, settings=_settings(), provider=_RateLimitedProvider(),
        force_agent_id=agent.agent_id,
    )
    db_session.commit()

    for forbidden in (EventType.INVALID_AGENT_DECISION, EventType.AGENT_ACTED):
        assert db_session.scalars(select(Event).where(Event.event_type == forbidden)).first() is None


def test_ordinary_provider_unavailable_does_not_set_rate_limit_pause_reason(db_session):
    """A non-429 provider outage (e.g. bad credentials) still stops the
    turn, but must not be mislabeled as a rate-limit pause — a human
    fixing credentials needs the real reason, not a misleading one."""

    class _BrokenAuthProvider:
        name = "fake_broken_auth"
        is_fixture = False

        def complete(self, **kwargs):
            raise LLMProviderUnavailable("Anthropic authentication failed: invalid API key")

    agent, clock = _seed(db_session)

    outcome = run_next_event(
        db_session, settings=_settings(), provider=_BrokenAuthProvider(),
        force_agent_id=agent.agent_id,
    )
    db_session.commit()

    assert outcome.provider_unavailable is True
    assert outcome.rate_limited is False

    db_session.refresh(clock)
    # The generic provider-unavailable path deliberately leaves is_paused/
    # pause_reason untouched — scripts/run_day.py's exit-75 checkpoint (not
    # an automatic clock pause) is what stops that run; only a genuine
    # rate-limit/quota condition trips the circuit breaker.
    assert clock.is_paused is False
    assert clock.pause_reason is None
    assert (
        db_session.scalars(
            select(Event).where(Event.event_type == EventType.SIMULATION_PAUSED_RATE_LIMIT)
        ).first()
        is None
    )


def test_mid_conversation_rate_limit_leaves_conversation_untouched(db_session):
    """An open conversation's silence/wind-down bookkeeping must not
    advance for a turn that was never actually taken — the "in-flight
    queue" (the agent's pending turn, and whatever conversation it was
    part of) is preserved exactly as it was, not partially processed."""
    from app.db.models.conversations import Conversation
    from app.domain.enums import ConversationTrigger

    agent, clock = _seed(db_session)
    other = Agent(agent_id="agent_b", identity="a resident", voice="plain")
    conversation = Conversation(
        trigger_type=ConversationTrigger.RANDOM_SOCIAL,
        participant_ids=[agent.agent_id, other.agent_id],
        consecutive_silences=0,
    )
    db_session.add_all([other, conversation])
    db_session.commit()
    conversation_id = conversation.id

    outcome = run_next_event(
        db_session, settings=_settings(), provider=_RateLimitedProvider(),
        force_agent_id=agent.agent_id,
    )
    db_session.commit()

    pause_event = db_session.scalars(
        select(Event).where(Event.event_type == EventType.SIMULATION_PAUSED_RATE_LIMIT)
    ).one()
    assert pause_event.payload["checkpoint_conversation_id"] == conversation_id

    db_session.refresh(conversation)
    assert conversation.consecutive_silences == 0
    assert conversation.status.value == "ACTIVE"
    assert outcome.event_ids  # woke + pause, nothing conversation-related


# ---------------------------------------------------------------------------
# 3. DB safety: atomicity of the pause, and integrity_check after commit
# ---------------------------------------------------------------------------


def test_rollback_before_commit_leaves_no_partial_pause_state(db_session):
    """If the process died between catching the 429 and committing, the
    clock mutation and the event row must rise or fall together — never a
    half-written pause visible to the next reader."""
    agent, clock = _seed(db_session)

    run_next_event(
        db_session, settings=_settings(), provider=_RateLimitedProvider(),
        force_agent_id=agent.agent_id,
    )
    # Simulate a crash before the caller's commit: roll back instead.
    db_session.rollback()

    db_session.refresh(clock)
    assert clock.is_paused is False
    assert clock.pause_reason is None
    assert (
        db_session.scalars(
            select(Event).where(Event.event_type == EventType.SIMULATION_PAUSED_RATE_LIMIT)
        ).first()
        is None
    )


def test_committed_pause_survives_a_fresh_connection_with_integrity_intact(db_session, tmp_path):
    import sqlite3

    agent, clock = _seed(db_session)
    run_next_event(
        db_session, settings=_settings(), provider=_RateLimitedProvider(),
        force_agent_id=agent.agent_id,
    )
    db_session.commit()
    db_session.close()

    conn = sqlite3.connect(str(tmp_path / "circuit_breaker.db"))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
        row = conn.execute(
            "SELECT is_paused, pause_reason, current_day, current_period FROM simulation_clock WHERE id = 1"
        ).fetchone()
        assert row == (1, "PAUSED_RATE_LIMIT", 3, "AFTERNOON")
        pause_rows = conn.execute(
            "SELECT count(*) FROM events WHERE event_type = 'SIMULATION_PAUSED_RATE_LIMIT'"
        ).fetchone()[0]
        assert pause_rows == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# scripts/run_day.py: the tick loop exits cleanly (75) on a rate-limit pause,
# the same checkpoint contract as any other provider-unavailable stop, and
# never crashes or continues into a fabricated turn.
# ---------------------------------------------------------------------------


class _ScalarResult:
    def __init__(self, clock):
        self.clock = clock

    def first(self):
        return self.clock


class _Session:
    def __init__(self, clock):
        self.clock = clock
        self.commits = 0

    def scalars(self, _query):
        return _ScalarResult(self.clock)

    def commit(self):
        self.commits += 1

    def refresh(self, _clock):
        pass

    def close(self):
        pass


def test_run_day_exits_75_and_reports_rate_limit_on_mock_429(monkeypatch, capsys):
    clock = SimpleNamespace(
        current_day=5, current_period="EVENING", is_paused=False, pause_reason=None,
    )
    session = _Session(clock)
    outcomes = [
        EventOutcome(
            provider_unavailable=True,
            rate_limited=True,
            rejected_reason="provider rate-limited: mock 429 response",
        ),
    ]

    def next_event(*args, **kwargs):
        clock.is_paused = True
        clock.pause_reason = "PAUSED_RATE_LIMIT"
        return outcomes.pop(0)

    monkeypatch.setattr(run_day, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        run_day, "get_settings",
        lambda: SimpleNamespace(app_env="test", database_url="sqlite://"),
    )
    monkeypatch.setattr(
        run_day, "get_llm_provider",
        lambda _settings: SimpleNamespace(name="fixture", is_fixture=True),
    )
    monkeypatch.setattr(run_day, "run_next_event", next_event)
    monkeypatch.setattr(sys, "argv", ["run_day.py", "--quiet"])

    assert run_day.main() == 75
    assert session.commits == 1
    assert clock.is_paused is True
    assert clock.pause_reason == "PAUSED_RATE_LIMIT"
    # Checkpoint is exactly where it was — run_day never advanced past a
    # rate-limited activation.
    assert (clock.current_day, clock.current_period) == (5, "EVENING")

    printed = capsys.readouterr().out
    assert "PAUSED_RATE_LIMIT" in printed
