from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import scripts.run_day as run_day
from app.providers.llm.anthropic import AnthropicLLMProvider
from app.providers.llm.base import LLMProviderUnavailable
from app.providers.llm.claude_cli import ClaudeCLILLMProvider
from app.services.orchestrator import EventOutcome


class _Output(BaseModel):
    ok: bool


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


def test_claude_session_limit_is_typed_non_retryable(monkeypatch):
    response = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout=json.dumps(
            {
                "is_error": True,
                "result": "You've hit your session limit; resets later.",
            }
        ),
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: response)
    provider = ClaudeCLILLMProvider(binary="/usr/bin/false")

    with pytest.raises(LLMProviderUnavailable, match="session limit"):
        provider.complete(
            system="system",
            user="user",
            model="test",
            purpose="agent_decision",
            output_type=_Output,
        )


def test_anthropic_rate_limit_is_typed_non_retryable(monkeypatch):
    import httpx2

    provider = AnthropicLLMProvider(api_key="test-key")
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(429, request=request)
    rate_limit_error = provider._anthropic.RateLimitError(
        "Number of request tokens has exceeded your per-minute rate limit.",
        response=response,
        body=None,
    )

    def _raise(*args, **kwargs):
        raise rate_limit_error

    monkeypatch.setattr(provider._client.messages, "create", _raise)

    with pytest.raises(LLMProviderUnavailable, match="rate-limited"):
        provider.complete(
            system="system",
            user="user",
            model="test",
            purpose="agent_decision",
            output_type=_Output,
        )


def _patch_runner(monkeypatch, clock, outcomes):
    session = _Session(clock)
    calls = []

    def next_event(*args, **kwargs):
        calls.append(1)
        outcome = outcomes.pop(0)
        if outcome.clock_advance:
            clock.current_day += 1
            clock.current_period = "MORNING"
        return outcome

    monkeypatch.setattr(run_day, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        run_day,
        "get_settings",
        lambda: SimpleNamespace(app_env="test", database_url="sqlite://"),
    )
    monkeypatch.setattr(
        run_day,
        "get_llm_provider",
        lambda _settings: SimpleNamespace(name="fixture", is_fixture=True),
    )
    monkeypatch.setattr(run_day, "run_next_event", next_event)
    monkeypatch.setattr(sys, "argv", ["run_day.py", "--quiet"])
    return session, calls


def test_run_day_stops_after_first_provider_unavailable_and_can_resume(monkeypatch):
    clock = SimpleNamespace(current_day=9, current_period="AFTERNOON")
    outcomes = [
        EventOutcome(
            provider_unavailable=True,
            rejected_reason="provider unavailable: session limit",
        ),
        EventOutcome(clock_advance="DAY_ADVANCED"),
    ]
    session, calls = _patch_runner(monkeypatch, clock, outcomes)

    assert run_day.main() == 75
    assert len(calls) == 1
    assert session.commits == 1
    assert (clock.current_day, clock.current_period) == (9, "AFTERNOON")

    assert run_day.main() == 0
    assert len(calls) == 2
    assert session.commits == 2
    assert (clock.current_day, clock.current_period) == (10, "MORNING")


def test_ordinary_rejection_does_not_trip_circuit_breaker(monkeypatch):
    clock = SimpleNamespace(current_day=9, current_period="AFTERNOON")
    outcomes = [
        EventOutcome(rejected_reason="missing required target"),
        EventOutcome(clock_advance="DAY_ADVANCED"),
    ]
    session, calls = _patch_runner(monkeypatch, clock, outcomes)

    assert run_day.main() == 0
    assert len(calls) == 2
    assert session.commits == 2
    assert clock.current_day == 10
