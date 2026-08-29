"""The live Anthropic adapter.

Uses native structured outputs (``client.messages.parse``) so the envelope is
schema-validated by the API rather than regex-parsed out of prose, and reports
the real usage block back for telemetry.

Untested in this repository so far: no API key has been available, so only the
fixture path has been exercised end to end. Treat the first live run as a smoke
test.
"""

from __future__ import annotations

import time

from app.providers.llm.base import LLMError, LLMResult, LLMSchemaError, LLMUsage
from app.schemas.actions import AgentDecision

#: Bumped whenever the prompt text changes, so llm_runs rows stay comparable.
PROMPT_VERSION = "agent_decision.v1"


class AnthropicLLMProvider:
    """Structured decisions from the Messages API."""

    name = "anthropic"
    is_fixture = False

    def __init__(self, api_key: str | None = None, max_tokens: int = 1024) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise LLMError(
                "The anthropic package is not installed. Install it, or set "
                "LLM_PROVIDER=fixture to run without a model."
            ) from exc

        self._anthropic = anthropic
        # A bare client also resolves an `ant auth login` profile, so an unset
        # ANTHROPIC_API_KEY is not necessarily an error.
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._max_tokens = max_tokens

    def decide(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
    ) -> LLMResult:
        started = time.perf_counter()
        try:
            response = self._client.messages.parse(
                model=model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=AgentDecision,
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"Anthropic call failed: {exc}") from exc

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))

        decision = response.parsed_output
        if decision is None:
            raise LLMSchemaError("Anthropic returned no parsed decision envelope.")

        usage = response.usage
        return LLMResult(
            decision=decision,
            usage=LLMUsage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                stop_reason=response.stop_reason,
            ),
            provider=self.name,
            model=response.model or model,
            is_fixture=False,
            latency_ms=latency_ms,
        )
