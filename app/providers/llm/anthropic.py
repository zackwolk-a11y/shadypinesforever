"""The live Anthropic adapter.

Uses native structured outputs (``client.messages.parse``) so the output is
schema-validated by the API rather than regex-parsed out of prose, and reports
the real usage block back for telemetry. ``complete()`` is generic over
whatever Pydantic model it is asked for — the same client call serves an
:class:`~app.schemas.actions.AgentDecision` and a
:class:`~app.schemas.research.ResearchSynthesis` alike, so adding a third
structured call later needs no change here.

Untested in this repository so far: no API key has been available, so only the
fixture path has been exercised end to end. Treat the first live run as a smoke
test.
"""

from __future__ import annotations

import time
from typing import TypeVar

from pydantic import BaseModel

from app.providers.llm.base import LLMError, LLMResult, LLMSchemaError, LLMUsage

T = TypeVar("T", bound=BaseModel)


class AnthropicLLMProvider:
    """Structured output from the Messages API."""

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

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
        output_type: type[T],
    ) -> LLMResult:
        started = time.perf_counter()
        try:
            response = self._client.messages.parse(
                model=model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_type,
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"Anthropic call failed ({purpose}): {exc}") from exc

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))

        output = response.parsed_output
        if output is None:
            raise LLMSchemaError(
                f"Anthropic returned no parsed {output_type.__name__} for {purpose!r}."
            )

        usage = response.usage
        return LLMResult(
            output=output,
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
