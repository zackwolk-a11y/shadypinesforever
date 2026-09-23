"""Claude Code subscription-backed LLM provider.

Runs one non-interactive ``claude -p`` process per completion.  The subprocess
uses the logged-in claude.ai subscription rather than an Anthropic Console API
key, while preserving the same structured-output boundary used by services.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.providers.llm.base import (
    LLMError,
    LLMProviderUnavailable,
    LLMRateLimited,
    LLMResult,
    LLMSchemaError,
    LLMUsage,
)

T = TypeVar("T", bound=BaseModel)
_DEFAULT_TIMEOUT_SECONDS = 180
_MAX_TRANSIENT_ATTEMPTS = 2
_RETRY_DELAY_SECONDS = 2.0
#: Quota/rate exhaustion — the subscription itself has run out of budget for
#: the window, not "the request was malformed" or "credentials are broken".
#: Raised as LLMRateLimited so the orchestrator's circuit breaker can pause
#: the simulation cleanly rather than treat it like a broken boundary.
_QUOTA_MARKERS = (
    "session limit", "weekly limit", "usage limit", "credit balance", "429",
)
_AUTH_MARKERS = (
    "authentication", "not logged in", "unauthorized", "invalid api key",
)
_NON_RETRYABLE_MARKERS = _QUOTA_MARKERS + _AUTH_MARKERS


def _failure_detail(proc: subprocess.CompletedProcess[str], outer: dict) -> str:
    reported = outer.get("result") or outer.get("api_error_status") or proc.stderr
    if reported:
        return str(reported).strip()[:500]
    keys = ",".join(sorted(str(key) for key in outer)) or "none"
    return (
        f"no provider detail (exit={proc.returncode}, "
        f"is_error={bool(outer.get('is_error'))}, stdout_keys={keys}, "
        f"stderr={'present' if proc.stderr else 'empty'})"
    )


def _is_quota_exhausted(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in _QUOTA_MARKERS)


def _is_non_retryable_failure(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in _NON_RETRYABLE_MARKERS)


def _is_transient_failure(detail: str) -> bool:
    lowered = detail.lower()
    if _is_non_retryable_failure(detail):
        return False
    return (
        "no provider detail" in lowered
        or "overloaded" in lowered
        or "temporarily unavailable" in lowered
        or any(code in lowered for code in ("429", "500", "502", "503", "529"))
    )


class ClaudeCLILLMProvider:
    name = "claude_cli"
    is_fixture = False

    def __init__(self, binary: str | None = None, *, timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS) -> None:
        self._binary = binary or shutil.which("claude") or ""
        self._timeout_seconds = timeout_seconds
        if not self._binary:
            raise LLMError("Claude CLI is not installed or not on PATH.")

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
        output_type: type[T],
        max_tokens: int | None = None,
    ) -> LLMResult:
        schema = output_type.model_json_schema()
        system_prompt = system
        if max_tokens:
            system_prompt += (
                f"\n\nOUTPUT BUDGET: Keep the structured response within approximately "
                f"{max_tokens} output tokens."
            )
        cmd = [
            self._binary, "-p", "--safe-mode", "--disable-slash-commands",
            "--tools", "", "--no-session-persistence", "--model", model,
            "--system-prompt", system_prompt,
            "--json-schema", json.dumps(schema, separators=(",", ":")),
            "--output-format", "json", user,
        ]
        env = os.environ.copy()
        # Claude Code otherwise prefers API credentials over claude.ai login.
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        started = time.perf_counter()
        retry_count = 0
        for attempt in range(_MAX_TRANSIENT_ATTEMPTS):
            try:
                proc = subprocess.run(
                    cmd, input="", text=True, capture_output=True, env=env,
                    timeout=self._timeout_seconds, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                if attempt + 1 < _MAX_TRANSIENT_ATTEMPTS:
                    retry_count += 1
                    time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise LLMError(
                    f"Claude CLI timed out for {purpose!r} after "
                    f"{self._timeout_seconds}s on {_MAX_TRANSIENT_ATTEMPTS} attempts."
                ) from exc
            except OSError as exc:
                raise LLMError(f"Claude CLI could not start for {purpose!r}: {exc}") from exc

            stdout = (proc.stdout or "").strip()
            try:
                outer = json.loads(stdout) if stdout else {}
            except json.JSONDecodeError as exc:
                detail = (proc.stderr or stdout or "no output").strip()[:500]
                if attempt + 1 < _MAX_TRANSIENT_ATTEMPTS and not stdout:
                    retry_count += 1
                    time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise LLMError(
                    f"Claude CLI returned invalid JSON for {purpose!r} "
                    f"(exit={proc.returncode}, attempt={attempt + 1}): {detail}"
                ) from exc

            if proc.returncode == 0 and not outer.get("is_error"):
                break
            detail = _failure_detail(proc, outer)
            if attempt + 1 < _MAX_TRANSIENT_ATTEMPTS and _is_transient_failure(detail):
                retry_count += 1
                time.sleep(_RETRY_DELAY_SECONDS)
                continue
            if _is_quota_exhausted(detail):
                error_type = LLMRateLimited
            elif _is_non_retryable_failure(detail):
                error_type = LLMProviderUnavailable
            else:
                error_type = LLMError
            raise error_type(
                f"Claude CLI failed for {purpose!r} "
                f"(exit={proc.returncode}, attempt={attempt + 1}): {detail}"
            )

        elapsed_ms = max(1, int((time.perf_counter() - started) * 1000))
        structured = outer.get("structured_output")
        if structured is None:
            structured = outer.get("result")
            if isinstance(structured, str):
                try:
                    structured = json.loads(structured)
                except json.JSONDecodeError as exc:
                    raise LLMSchemaError(
                        f"Claude CLI returned no valid structured output for {purpose!r}."
                    ) from exc
        try:
            output = output_type.model_validate(structured)
        except ValidationError as exc:
            raise LLMSchemaError(
                f"Claude CLI output failed {output_type.__name__} validation for {purpose!r}: {exc}"
            ) from exc

        model_usage = outer.get("modelUsage") or {}
        entries = list(model_usage.values())
        input_tokens = sum(int(e.get("inputTokens") or 0) for e in entries)
        output_tokens = sum(int(e.get("outputTokens") or 0) for e in entries)
        cache_creation = sum(int(e.get("cacheCreationInputTokens") or 0) for e in entries)
        cache_read = sum(int(e.get("cacheReadInputTokens") or 0) for e in entries)

        reported_usage = outer.get("usage") or {}
        if not entries:
            input_tokens = int(reported_usage.get("input_tokens") or 0)
            output_tokens = int(reported_usage.get("output_tokens") or 0)
            cache_creation = int(reported_usage.get("cache_creation_input_tokens") or 0)
            cache_read = int(reported_usage.get("cache_read_input_tokens") or 0)

        used_model = model
        if entries:
            used_model = entries[0].get("canonicalModel") or next(iter(model_usage)) or model
        return LLMResult(
            output=output,
            usage=LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_input_tokens=cache_creation,
                cache_read_input_tokens=cache_read,
                stop_reason=outer.get("stop_reason") or outer.get("terminal_reason"),
                retry_count=retry_count,
            ),
            provider=self.name,
            model=used_model,
            is_fixture=False,
            latency_ms=int(outer.get("duration_ms") or elapsed_ms),
        )
