"""The live Anthropic adapter (Packet 11).

Uses native structured outputs (``client.messages.parse``) so the output is
schema-validated by the API itself rather than regex-parsed out of prose, and
reports the real usage block back for telemetry. ``complete()`` is generic
over whatever Pydantic model it is asked for — the same client call serves
an :class:`~app.schemas.actions.AgentDecision`, a
:class:`~app.schemas.research.ResearchSynthesis`, a
:class:`~app.schemas.research.SearchQueryPlan`, a
:class:`~app.schemas.reflection.ReflectionSynthesis`, and a
:class:`~app.schemas.report.FounderReportSynthesis` alike, so adding a sixth
structured call later needs no change here.

Failure discipline (Part O): every SDK exception is mapped to
:class:`~app.providers.llm.base.LLMError` with a message that never contains
the API key (the key lives in the client's own auth header, never in a
request body or a caught exception's string form here). The underlying SDK
already retries connection errors/408/409/429/5xx with bounded exponential
backoff (``max_retries``, default 2) — this adapter does not reimplement
that. The one thing the SDK cannot retry for us is the model producing
prose that fails schema validation (``parsed_output is None`` with no
exception raised); that gets exactly one bounded manual retry here, tracked
in the returned usage so ``app.services.telemetry`` can see it happened.
"""

from __future__ import annotations

import time
from typing import TypeVar

from pydantic import BaseModel

from app.providers.llm.base import LLMError, LLMResult, LLMSchemaError, LLMUsage

T = TypeVar("T", bound=BaseModel)

#: A conservative fallback when a caller doesn't pass its own per-purpose
#: budget (Settings.max_tokens_*) — see app/providers/llm/base.py's
#: complete() docstring for why this is never inferred from ``purpose``.
_DEFAULT_MAX_TOKENS = 1024

#: A schema-validation failure (empty parsed_output, no exception) gets
#: exactly one retry — never an unbounded loop, matching Part O.
_MAX_SCHEMA_RETRIES = 1


class AnthropicLLMProvider:
    """Structured output from the Messages API."""

    name = "anthropic"
    is_fixture = False

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise LLMError(
                "The anthropic package is not installed. Install it, or set "
                "LLM_PROVIDER=fixture to run without a model."
            ) from exc

        self._anthropic = anthropic
        # A bare client also resolves an `ant auth login` profile, so an unset
        # ANTHROPIC_API_KEY is not necessarily an error — but Village-side
        # config that explicitly named an api_key and got None is (see
        # get_llm_provider, which is expected to fail loudly rather than
        # silently construct an unauthenticated client here).
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

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
        budget = max_tokens or _DEFAULT_MAX_TOKENS
        started = time.perf_counter()

        retries = 0
        while True:
            response = self._call(system, user, model, purpose, output_type, budget)
            output = response.parsed_output
            if output is not None:
                break
            if retries >= _MAX_SCHEMA_RETRIES:
                raise LLMSchemaError(
                    f"Anthropic returned no parsed {output_type.__name__} for {purpose!r} "
                    f"after {retries + 1} attempt(s)."
                )
            retries += 1

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        usage = response.usage
        return LLMResult(
            output=output,
            usage=LLMUsage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                stop_reason=response.stop_reason,
                retry_count=retries,
            ),
            provider=self.name,
            model=response.model or model,
            is_fixture=False,
            latency_ms=latency_ms,
        )

    def _call(self, system: str, user: str, model: str, purpose: str, output_type: type[T], max_tokens: int):
        anthropic = self._anthropic
        try:
            return self._client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=output_type,
            )
        # Most-specific-first: each of these is a distinct, actionable
        # failure mode (Part O), never collapsed into one generic message.
        # None of these format strings interpolate the request body or the
        # client's auth header, so the API key can never leak into a log.
        except anthropic.AuthenticationError as exc:
            raise LLMError(
                f"Anthropic authentication failed for {purpose!r}: invalid or missing API key."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMError(
                f"Anthropic denied permission for {purpose!r} (model {model!r}): {exc.message}"
            ) from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(
                f"Anthropic model {model!r} not found for {purpose!r}: {exc.message}"
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError(f"Anthropic rate-limited {purpose!r}: {exc.message}") from exc
        except anthropic.APITimeoutError as exc:
            raise LLMError(f"Anthropic timed out for {purpose!r}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"Anthropic connection failed for {purpose!r}: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"Anthropic returned {exc.status_code} for {purpose!r}: {exc.message}"
            ) from exc
        except anthropic.APIError as exc:
            raise LLMError(f"Anthropic call failed ({purpose}): {exc}") from exc
