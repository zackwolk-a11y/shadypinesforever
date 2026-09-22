#!/usr/bin/env python3
"""Deterministic unit test for AnthropicLLMProvider's truncation/schema-
validation retry (the bug found by a real forced live research run: a
truncated ``ResearchSynthesis`` response raised a bare
``pydantic.ValidationError`` straight out of ``client.messages.parse()``,
uncaught by the provider's exception chain, crashing the whole script
instead of being retried).

This is deliberately a different kind of test than every ``smoke_test_*.py``
in this repo: those drive the real simulation loop against a real fixture or
real live provider and never fake a result. This one mocks the Anthropic
SDK's ``messages.create`` call itself, because the thing under test —
whether ``AnthropicLLMProvider.complete()`` correctly recovers from a
specific, exact sequence of raw API responses (truncated, then valid;
invalid JSON, then valid; invalid twice) — cannot be driven deterministically
against a real model, which never guarantees producing a truncated response
on command. Nothing here stands in for simulated cognition or fabricates a
research result; it only exercises the provider adapter's own retry
plumbing in isolation, with a fake network boundary.

No API key or network access required — safe to run in ordinary CI.

Usage::

    python scripts/test_anthropic_retry.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402

from app.providers.llm.anthropic import AnthropicLLMProvider  # noqa: E402
from app.providers.llm.base import LLMSchemaError  # noqa: E402


class _TestOutput(BaseModel):
    """A minimal schema — the retry mechanism under test doesn't depend on
    which real schema (ResearchSynthesis, AgentDecision, ...) is in play."""

    model_config = {"extra": "forbid"}

    value: str


def _fake_message(*, stop_reason: str, text: str | None, model: str = "claude-test") -> SimpleNamespace:
    content = [SimpleNamespace(type="text", text=text)] if text is not None else []
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        model=model,
        usage=SimpleNamespace(
            input_tokens=100, output_tokens=50,
            cache_creation_input_tokens=0, cache_read_input_tokens=0,
        ),
    )


class _FakeMessagesAPI:
    """Replaces ``client.messages`` on the provider — records every call's
    kwargs (so a test can assert the retry actually raised max_tokens) and
    returns queued fake responses in order."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError(
                f"provider made {len(self.calls)} call(s) — no more fake responses queued "
                "(the retry loop is not bounded, or made an extra call)"
            )
        return self._responses.pop(0)


def _provider_with(responses: list[SimpleNamespace]) -> tuple[AnthropicLLMProvider, _FakeMessagesAPI]:
    provider = AnthropicLLMProvider(api_key="test-key-not-real")
    fake = _FakeMessagesAPI(responses)
    provider._client.messages = fake
    return provider, fake


def _check(label: str, condition: bool, checks: list[tuple[str, bool]]) -> None:
    checks.append((label, condition))


def test_valid_first_response_needs_no_retry() -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    provider, fake = _provider_with([
        _fake_message(stop_reason="end_turn", text='{"value": "ok"}'),
    ])
    result = provider.complete(
        system="sys", user="user", model="claude-test", purpose="test",
        output_type=_TestOutput, max_tokens=100,
    )
    _check("valid first response: no retry needed", result.usage.retry_count == 0, checks)
    _check("valid first response: correct output parsed", result.output.value == "ok", checks)
    _check("valid first response: exactly one call made", len(fake.calls) == 1, checks)
    return checks


def test_truncated_then_valid_retries_once_with_larger_budget() -> list[tuple[str, bool]]:
    """Reproduces the exact bug: a truncated (stop_reason=max_tokens)
    response with a JSON string cut off mid-value, same shape as the real
    crash ('EOF while parsing a string')."""
    checks: list[tuple[str, bool]] = []
    provider, fake = _provider_with([
        _fake_message(stop_reason="max_tokens", text='{"value": "this got cut off mid-str'),
        _fake_message(stop_reason="end_turn", text='{"value": "complete this time"}'),
    ])
    result = provider.complete(
        system="sys", user="user", model="claude-test", purpose="research_synthesis",
        output_type=_TestOutput, max_tokens=100,
    )
    _check("truncated-then-valid: caught, not crashed", True, checks)
    _check("truncated-then-valid: retried exactly once", result.usage.retry_count == 1, checks)
    _check("truncated-then-valid: correct output on retry", result.output.value == "complete this time", checks)
    _check("truncated-then-valid: exactly two calls made", len(fake.calls) == 2, checks)
    _check(
        "truncated-then-valid: retry used a larger max_tokens budget",
        fake.calls[1]["max_tokens"] > fake.calls[0]["max_tokens"],
        checks,
    )
    return checks


def test_invalid_json_then_valid_retries_once() -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    provider, fake = _provider_with([
        _fake_message(stop_reason="end_turn", text="not json at all {{{"),
        _fake_message(stop_reason="end_turn", text='{"value": "recovered"}'),
    ])
    result = provider.complete(
        system="sys", user="user", model="claude-test", purpose="test",
        output_type=_TestOutput, max_tokens=100,
    )
    _check("invalid-json-then-valid: retried exactly once", result.usage.retry_count == 1, checks)
    _check("invalid-json-then-valid: correct output on retry", result.output.value == "recovered", checks)
    return checks


def test_both_attempts_fail_raises_cleanly_not_a_crash() -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    provider, fake = _provider_with([
        _fake_message(stop_reason="max_tokens", text='{"value": "still cut off'),
        _fake_message(stop_reason="max_tokens", text='{"value": "cut off again'),
    ])
    raised_schema_error = False
    raised_something_else = False
    try:
        provider.complete(
            system="sys", user="user", model="claude-test", purpose="research_synthesis",
            output_type=_TestOutput, max_tokens=100,
        )
    except LLMSchemaError:
        raised_schema_error = True
    except Exception:
        raised_something_else = True

    _check("both-fail: raises LLMSchemaError, not a bare pydantic/other exception", raised_schema_error, checks)
    _check("both-fail: does not raise some other uncaught exception", not raised_something_else, checks)
    _check("both-fail: stopped after exactly one retry (two calls total)", len(fake.calls) == 2, checks)
    return checks


def main() -> int:
    all_checks: list[tuple[str, bool]] = []
    for fn in (
        test_valid_first_response_needs_no_retry,
        test_truncated_then_valid_retries_once_with_larger_budget,
        test_invalid_json_then_valid_retries_once,
        test_both_attempts_fail_raises_cleanly_not_a_crash,
    ):
        print(f"--- {fn.__name__} ---")
        try:
            checks = fn()
        except Exception as exc:  # the test itself crashed — report, don't hide
            print(f"  [FAIL] test raised an unexpected exception: {exc!r}")
            all_checks.append((fn.__name__, False))
            continue
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_checks.extend(checks)
        print()

    ok = all(v for _, v in all_checks)
    print(f"{'PASS' if ok else 'FAIL'}: {sum(1 for _, v in all_checks if v)}/{len(all_checks)} checks.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
