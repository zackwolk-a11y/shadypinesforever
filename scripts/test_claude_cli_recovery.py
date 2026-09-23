#!/usr/bin/env python3
"""Regressions for bounded Claude CLI recovery and actionable diagnostics."""
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel
from app.providers.llm.base import LLMError, LLMProviderUnavailable
from app.providers.llm.claude_cli import ClaudeCLILLMProvider


class Answer(BaseModel):
    value: str


def call(provider):
    return provider.complete(
        system="system", user="user", model="test-model",
        purpose="test", output_type=Answer,
    )


empty_error = CompletedProcess(["claude"], 1, '{"is_error":true}', "")
success_payload = json.dumps({
    "is_error": False,
    "structured_output": {"value": "ok"},
    "usage": {},
})
success = CompletedProcess(["claude"], 0, success_payload, "")

provider = ClaudeCLILLMProvider(binary="/bin/echo")
with patch("app.providers.llm.claude_cli.subprocess.run",
           side_effect=[empty_error, success]) as run, \
     patch("app.providers.llm.claude_cli.time.sleep"):
    result = call(provider)
assert run.call_count == 2
assert result.output.value == "ok"
assert result.usage.retry_count == 1

limit = CompletedProcess(
    ["claude"], 1,
    json.dumps({"is_error": True, "result": "You've hit your session limit"}),
    "",
)
with patch("app.providers.llm.claude_cli.subprocess.run",
           return_value=limit) as run:
    try:
        call(provider)
    except LLMError as exc:
        assert "session limit" in str(exc)
        assert "attempt=1" in str(exc)
    else:
        raise AssertionError("session limit must fail")
assert run.call_count == 1

weekly_limit = CompletedProcess(
    ["claude"], 1,
    json.dumps({
        "is_error": True,
        "result": "You've hit your weekly limit · resets Sep 21 at 10am",
    }),
    "",
)
with patch("app.providers.llm.claude_cli.subprocess.run",
           return_value=weekly_limit) as run:
    try:
        call(provider)
    except LLMProviderUnavailable as exc:
        assert "weekly limit" in str(exc)
        assert "attempt=1" in str(exc)
    else:
        raise AssertionError("weekly subscription limit must be provider-unavailable")
assert run.call_count == 1

with patch("app.providers.llm.claude_cli.subprocess.run",
           side_effect=[empty_error, empty_error]) as run, \
     patch("app.providers.llm.claude_cli.time.sleep"):
    try:
        call(provider)
    except LLMError as exc:
        detail = str(exc)
        assert "attempt=2" in detail
        assert "exit=1" in detail
        assert "stdout_keys=is_error" in detail
        assert "stderr=empty" in detail
    else:
        raise AssertionError("persistent empty-detail failure must fail")
assert run.call_count == 2

print("PASS: transient retry, session-limit fail-fast, and diagnostics")
