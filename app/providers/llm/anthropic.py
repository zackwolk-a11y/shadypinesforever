"""The live Anthropic adapter (Packet 11, patched post-Packet-11).

Uses the Messages API's native structured-output schema
(``output_config.format``) so the output is schema-validated deterministically,
and reports the real usage block back for telemetry. ``complete()`` is generic
over whatever Pydantic model it is asked for — the same client call serves
an :class:`~app.schemas.actions.AgentDecision`, a
:class:`~app.schemas.research.ResearchSynthesis`, a
:class:`~app.schemas.research.SearchQueryPlan`, a
:class:`~app.schemas.reflection.ReflectionSynthesis`, and a
:class:`~app.schemas.report.FounderReportSynthesis` alike, so adding a sixth
structured call later needs no change here.

**Deliberately does not use ``client.messages.parse()``.** That helper
receives the full raw ``Message`` (including the real ``stop_reason``)
internally, then validates its text content against the schema — and if
that validation fails, it raises a bare ``pydantic.ValidationError`` from
deep inside the SDK, with the raw response already out of scope and
unrecoverable by the caller (verified by reading
``anthropic.lib._parse._response.parse_text``/``parse_response``: a
schema-validation failure there is a raise, not a return-of-None, so a
retry loop written around "did parsed_output come back None" — this
module's original design — can never observe it). A truncated
response (``stop_reason == "max_tokens"``, evidence never fits its
`max_tokens` budget as a whole and JSON gets cut off mid-string) hits
exactly this path and is indistinguishable, from outside `.parse()`, from
any other schema mismatch.

Instead, ``_call`` uses the plain ``client.messages.create()`` with the same
schema transform `.parse()` uses internally
(``anthropic.lib._parse._transform.transform_schema`` — the exact function
`.parse()` itself calls, reused here rather than reimplemented, with a
graceful fallback to a plain ``model_json_schema()`` if a future SDK
version ever moves it), which always returns the raw ``Message`` regardless
of whether its content validates. ``_parse`` then validates it here, in this
module's own try/except, where ``stop_reason`` is still in scope — so
truncation is diagnosed directly (never confused with an unrelated schema
mismatch) and a schema-validation failure is a caught, retryable outcome
rather than an uncaught crash.

Failure discipline (Part O): every SDK exception is mapped to
:class:`~app.providers.llm.base.LLMError` with a message that never contains
the API key (the key lives in the client's own auth header, never in a
request body or a caught exception's string form here). The underlying SDK
already retries connection errors/408/409/429/5xx with bounded exponential
backoff (``max_retries``, default 2) — this adapter does not reimplement
that. The one thing it can't retry — the model producing truncated or
schema-invalid output — gets exactly one bounded manual retry here, tracked
in the returned usage so ``app.services.telemetry`` can see it happened; a
truncation-caused retry raises the token budget for that one retry (the
same budget would just truncate the same way again), capped, never removed.
"""

from __future__ import annotations

import time
from typing import TypeVar

import pydantic
from pydantic import BaseModel

from app.providers.llm.base import LLMError, LLMResult, LLMSchemaError, LLMUsage

T = TypeVar("T", bound=BaseModel)

#: A conservative fallback when a caller doesn't pass its own per-purpose
#: budget (Settings.max_tokens_*) — see app/providers/llm/base.py's
#: complete() docstring for why this is never inferred from ``purpose``.
_DEFAULT_MAX_TOKENS = 1024

#: A schema-validation or truncation failure gets exactly one retry — never
#: an unbounded loop, matching Part O.
_MAX_SCHEMA_RETRIES = 1

#: A retry caused specifically by hitting max_tokens raises the budget for
#: that retry — the same budget would just truncate the same way again —
#: but stays bounded, never uncapped (never "remove token limits entirely").
_TRUNCATION_RETRY_MULTIPLIER = 2.0
_TRUNCATION_RETRY_CEILING = 16000


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
        # ANTHROPIC_API_KEY is not necessarily an error.
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
        schema = self._schema_for(output_type)

        retries = 0
        raw = None
        output: T | None = None
        failure_reason: str | None = None
        while True:
            raw = self._call(system, user, model, purpose, budget, schema)
            output, failure_reason = self._parse(raw, output_type)
            if output is not None:
                break
            if retries >= _MAX_SCHEMA_RETRIES:
                raise LLMSchemaError(
                    f"Anthropic returned no valid {output_type.__name__} for {purpose!r} "
                    f"after {retries + 1} attempt(s): {failure_reason}"
                )
            retries += 1
            if raw.stop_reason == "max_tokens":
                budget = min(int(budget * _TRUNCATION_RETRY_MULTIPLIER), _TRUNCATION_RETRY_CEILING)

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        usage = raw.usage
        return LLMResult(
            output=output,
            usage=LLMUsage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                stop_reason=raw.stop_reason,
                retry_count=retries,
            ),
            provider=self.name,
            model=raw.model or model,
            is_fixture=False,
            latency_ms=latency_ms,
        )

    def _schema_for(self, output_type: type[T]) -> dict:
        """The same strict-JSON-schema transform ``client.messages.parse()``
        applies internally, reused rather than reimplemented (see module
        docstring). Falls back to a plain schema if a future SDK version
        ever relocates the private helper, rather than hard-failing."""
        try:
            from anthropic.lib._parse._transform import transform_schema

            return transform_schema(output_type)
        except Exception:
            return output_type.model_json_schema()

    def _call(self, system: str, user: str, model: str, purpose: str, max_tokens: int, schema: dict):
        anthropic = self._anthropic
        try:
            return self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
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

    def _parse(self, raw, output_type: type[T]) -> tuple[T | None, str | None]:
        """Validate the raw response's text content against the schema.

        Never raises — every failure mode (truncation, no text block,
        malformed JSON, schema mismatch) returns ``(None, reason)`` so the
        caller's retry loop can act on it, instead of an uncaught exception
        escaping from deep inside the SDK (the exact bug this module was
        rewritten to fix: ``client.messages.parse()`` raises a bare
        ``pydantic.ValidationError`` on this same failure, with the raw
        response — and its real ``stop_reason`` — already out of scope by
        the time it reaches the caller).
        """
        if raw.stop_reason == "max_tokens":
            return None, "response was truncated (stop_reason=max_tokens) before valid JSON completed"

        text = next((block.text for block in raw.content if block.type == "text"), None)
        if text is None:
            return None, f"response had no text content block (stop_reason={raw.stop_reason})"

        try:
            return output_type.model_validate_json(text), None
        except pydantic.ValidationError as exc:
            return None, f"schema validation failed: {exc}"
