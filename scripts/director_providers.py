"""Model-vendor layer for the Director system.

Pure "call a model, get back JSON matching a schema" mechanics — no opinion
about what question is being asked, what fields are expected back, or who's
asking. That separation is deliberate: adding a new reviewer role (Hermes,
or anything after it — see scripts/director_reviewers.py) should never
require touching a provider class, and adding a new vendor should never
require knowing what a "reviewer" or a "round" is.

Deliberately independent of app.providers.llm: that module is built around
the Village's own per-purpose token budgets and Settings plumbing for agent
decisions. The Director is a separate, external observer with its own
minimal contract.

Select a provider by name (``fixture`` — no network, deterministic
placeholder output; ``anthropic`` — a real call, requires
``ANTHROPIC_API_KEY``; ``openrouter`` — a real call, requires
``OPENROUTER_API_KEY`` and ``DIRECTOR_OPENROUTER_MODEL``; ``hermes_cli`` — a
real call through the local, already-authenticated Hermes CLI, no key of
any kind needed here).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol


class ModelProviderError(RuntimeError):
    """A model call failed, or returned something that could not be read as
    the requested structured tool call. Always fail-closed — callers must
    never treat a partial or unparseable result as usable output."""


class TransientModelProviderError(ModelProviderError):
    """A narrow subset of ModelProviderError: failures a caller may
    reasonably retry exactly once because they're about the plumbing of one
    call, not about what the model actually said. Reserved for failure
    modes with real, observed transient recurrence in this codebase (a
    Hermes response failing JSON parsing, or a Hermes CLI timeout) — never
    for a schema-validation failure on a successfully-parsed response, a
    rejected APPROVED_TO_TEST status, a missing API key, or any other
    config/permission/substantive problem, all of which stay plain
    ModelProviderError and must never be retried (see director_reviewers.
    run_reviewer's retry logic, which catches this subclass specifically)."""


@dataclass(frozen=True)
class StructuredCallSpec:
    """Everything a vendor needs to make one structured-output call. Built
    entirely from plain JSON — a vendor never needs to import a reviewer's
    Pydantic model or know what role asked the question."""

    system_prompt: str
    user_content: str
    tool_name: str
    tool_description: str
    schema: dict[str, Any]  # JSON schema for the tool's input object


class ModelProvider(Protocol):
    name: str
    is_fixture: bool

    def complete_structured(self, spec: StructuredCallSpec) -> dict[str, Any]: ...


class FixtureModelProvider:
    """No network call. Synthesizes a schema-shaped placeholder response
    generically from ``spec.schema`` alone — it never hardcodes a
    reviewer's field names, so the same class exercises the Director's
    PRIMARY schema, a CRITIQUE schema like Hermes', or any future reviewer
    role without modification. Safe to run in any test or CI path."""

    name = "fixture"
    is_fixture = True

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        del model, api_key  # accepted for interface uniformity, unused

    def complete_structured(self, spec: StructuredCallSpec) -> dict[str, Any]:
        return {
            field_name: self._placeholder(field_name, prop)
            for field_name, prop in spec.schema.get("properties", {}).items()
        }

    @staticmethod
    def _placeholder(field_name: str, prop: dict[str, Any]) -> Any:
        if "enum" in prop:
            return prop["enum"][0]
        json_type = prop.get("type")
        if json_type == "array":
            return []
        if json_type == "number":
            return 0.0
        if json_type == "integer":
            return 0
        if json_type == "boolean":
            return False
        return f"(fixture placeholder for {field_name!r} — no real model was called)"


class AnthropicModelProvider:
    """Structured output via a single forced tool call — the Messages API's
    normal mechanism, reimplemented minimally here rather than importing
    app.providers.llm.anthropic, whose retry/budget/purpose plumbing is
    scoped to Village agent-decision calls, not this standalone script."""

    name = "anthropic"
    is_fixture = False

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ModelProviderError(
                "The anthropic package is not installed. pip install anthropic, or choose a "
                "different provider."
            ) from exc
        self._anthropic = anthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.model = model or os.getenv("DIRECTOR_ANTHROPIC_MODEL", "claude-sonnet-5")

    def complete_structured(self, spec: StructuredCallSpec) -> dict[str, Any]:
        anthropic = self._anthropic
        tool = {
            "name": spec.tool_name,
            "description": spec.tool_description,
            "input_schema": spec.schema,
        }
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=spec.system_prompt,
                tools=[tool],
                tool_choice={"type": "tool", "name": spec.tool_name},
                messages=[{"role": "user", "content": spec.user_content}],
            )
        except anthropic.APIError as exc:
            raise ModelProviderError(f"Anthropic call failed: {exc}") from exc

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == spec.tool_name:
                return block.input
        raise ModelProviderError(
            f"Anthropic response contained no {spec.tool_name!r} tool call "
            f"(stop_reason={response.stop_reason!r})."
        )


class OpenRouterModelProvider:
    """Structured output via OpenRouter's OpenAI-compatible chat-completions
    endpoint, forced into shape with a single required tool/function call —
    the same idea AnthropicModelProvider uses, translated to OpenRouter's
    request/response shape. Uses ``httpx`` (already a project dependency)
    rather than adding a new one.

    The model is never chosen by this code. ``DIRECTOR_OPENROUTER_MODEL``
    (env var, or an explicit ``model=`` argument) is required — there is no
    default, deliberately: which model reviews the Village is a Founder
    decision, never something this script picks on its own. Constructing
    this provider without one raises immediately, before any network call.
    """

    name = "openrouter"
    is_fixture = False

    _CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
    _KEY_CHECK_URL = "https://openrouter.ai/api/v1/auth/key"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ModelProviderError(
                "OPENROUTER_API_KEY is not set. Add it to .env before using provider=openrouter."
            )
        self.model = model or os.getenv("DIRECTOR_OPENROUTER_MODEL")
        if not self.model:
            raise ModelProviderError(
                "No OpenRouter model configured. Set DIRECTOR_OPENROUTER_MODEL (env var) or pass "
                "model= explicitly — this is a deliberate Founder decision, never defaulted."
            )

    def check_key(self) -> dict[str, Any]:
        """Validate the API key against OpenRouter's own auth/key endpoint.
        Makes a real network call but never invokes a model, spends no
        tokens, and requires no model to be configured — safe to run before
        a Director model has been chosen. Returns OpenRouter's key-info
        payload (rate limits, usage) verbatim; never logs the key itself."""
        import httpx

        try:
            response = httpx.get(
                self._KEY_CHECK_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise ModelProviderError(f"OpenRouter key check failed: {exc}") from exc
        if response.status_code != 200:
            raise ModelProviderError(
                f"OpenRouter key check returned HTTP {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    def complete_structured(self, spec: StructuredCallSpec) -> dict[str, Any]:
        import httpx

        tool = {
            "type": "function",
            "function": {
                "name": spec.tool_name,
                "description": spec.tool_description,
                "parameters": spec.schema,
            },
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": spec.system_prompt},
                {"role": "user", "content": spec.user_content},
            ],
            "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": spec.tool_name}},
            # Explicit budget, not left to the model's own default: some
            # models default to a very large max_tokens regardless of
            # actual need, which OpenRouter reserves credits against up
            # front — bounded here the same way every other budgeted call
            # in this repo is (see app.core.config.MAX_TOKENS_*).
            "max_tokens": int(os.getenv("DIRECTOR_OPENROUTER_MAX_TOKENS", "4096")),
        }
        try:
            response = httpx.post(
                self._CHAT_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=120.0,
            )
        except httpx.HTTPError as exc:
            raise ModelProviderError(f"OpenRouter request failed: {exc}") from exc

        if response.status_code != 200:
            raise ModelProviderError(
                f"OpenRouter returned HTTP {response.status_code}: {response.text[:500]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelProviderError(f"OpenRouter response was not valid JSON: {exc}") from exc

        choices = payload.get("choices") or []
        if not choices:
            raise ModelProviderError(f"OpenRouter response had no choices: {json.dumps(payload)[:500]}")
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            raise ModelProviderError(
                f"OpenRouter response had no tool call (finish_reason="
                f"{choices[0].get('finish_reason')!r}): {json.dumps(payload)[:500]}"
            )

        for call in tool_calls:
            fn = call.get("function", {})
            if fn.get("name") == spec.tool_name:
                try:
                    return json.loads(fn["arguments"])
                except (json.JSONDecodeError, KeyError) as exc:
                    raise ModelProviderError(
                        f"OpenRouter tool call arguments were not valid JSON: {exc}"
                    ) from exc
        raise ModelProviderError(
            f"OpenRouter response contained no {spec.tool_name!r} tool call. Got: "
            f"{[c.get('function', {}).get('name') for c in tool_calls]}"
        )


class OpenAIModelProvider:
    """Structured output via OpenAI's Responses endpoint (``/v1/responses``),
    forced into shape with a single required function-tool call.

    Not Chat Completions: a real call against a reasoning-capable model
    (confirmed empirically, not assumed) returned "Function tools with
    reasoning_effort are not supported for {model} in /v1/chat/completions
    ... use /v1/responses" — Chat Completions' function-calling contract is
    incompatible with this class of model unless reasoning is disabled
    outright, which would defeat the point of choosing a reasoning model
    for the SYNTHESIS role. Responses is OpenAI's own answer to that.

    The model is never chosen by this code. ``DIRECTOR_OPENAI_MODEL`` (env
    var, or an explicit ``model=`` argument) is required — no default,
    deliberately: which model performs strategic synthesis is a Founder
    decision. Constructing this provider without one raises immediately,
    before any network call.
    """

    name = "openai"
    is_fixture = False

    _RESPONSES_URL = "https://api.openai.com/v1/responses"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ModelProviderError(
                "OPENAI_API_KEY is not set. Add it to .env before using provider=openai."
            )
        self.model = model or os.getenv("DIRECTOR_OPENAI_MODEL")
        if not self.model:
            raise ModelProviderError(
                "No OpenAI model configured. Set DIRECTOR_OPENAI_MODEL (env var) or pass model= "
                "explicitly — this is a deliberate Founder decision, never defaulted."
            )

    def complete_structured(self, spec: StructuredCallSpec) -> dict[str, Any]:
        import httpx

        # Responses API function tools are flat — no nested "function" key,
        # unlike Chat Completions' {"type": "function", "function": {...}}.
        tool = {
            "type": "function",
            "name": spec.tool_name,
            "description": spec.tool_description,
            "parameters": spec.schema,
        }
        body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": spec.system_prompt},
                {"role": "user", "content": spec.user_content},
            ],
            "tools": [tool],
            "tool_choice": {"type": "function", "name": spec.tool_name},
            # A reasoning model spends part of this budget on reasoning
            # tokens before any visible output, on top of an already-large
            # SYNTHESIS payload (snapshot + both reviews + reconciliation
            # packet + bridge context) — higher default than other
            # providers'.
            "max_output_tokens": int(os.getenv("DIRECTOR_OPENAI_MAX_TOKENS", "8192")),
        }
        try:
            response = httpx.post(
                self._RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=180.0,
            )
        except httpx.HTTPError as exc:
            raise ModelProviderError(f"OpenAI request failed: {exc}") from exc

        if response.status_code != 200:
            raise ModelProviderError(
                f"OpenAI returned HTTP {response.status_code}: {response.text[:500]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelProviderError(f"OpenAI response was not valid JSON: {exc}") from exc

        output = payload.get("output") or []
        for item in output:
            if item.get("type") == "function_call" and item.get("name") == spec.tool_name:
                try:
                    return json.loads(item["arguments"])
                except (json.JSONDecodeError, KeyError) as exc:
                    raise ModelProviderError(
                        f"OpenAI tool call arguments were not valid JSON: {exc}"
                    ) from exc
        raise ModelProviderError(
            f"OpenAI response contained no {spec.tool_name!r} function_call "
            f"(status={payload.get('status')!r}, output types="
            f"{[i.get('type') for i in output]}): {json.dumps(payload)[:800]}"
        )


class HermesLocalCLIProvider:
    """Structured output via the local Hermes CLI (`hermes chat -q ...
    --oneshot -Q`), authenticated entirely through Hermes' own existing
    Nous Portal OAuth session (`~/.hermes/auth.json`) — no API key of any
    kind lives in this repo or is required by this class.

    Hermes has no forced-tool-call mode we can drive from the outside (it's
    a full agent, not a raw completion endpoint), so structured output is
    requested in the prompt itself and parsed defensively afterward — the
    same discipline as every other provider: fail closed on anything that
    doesn't parse, never guess or repair.

    ``resolved_model`` starts ``None`` and is set after a successful call by
    asking Hermes' own session store (`hermes sessions export`) which model
    actually answered — Hermes' current default is data (`hermes config`),
    not something this class hardcodes or is told in advance. Callers
    (director_reviewers.run_reviewer) read this attribute after the call
    rather than trusting a declared model, since none is ever declared to
    Hermes here unless the caller explicitly requests one.
    """

    name = "hermes_cli"
    is_fixture = False

    #: Total time (seconds) director_loop / director_reviewers should refuse
    #: to wait past for one Hermes call — the process is still killed by
    #: subprocess's own timeout, this is only the value handed to Hermes'
    #: own --run-budget so Hermes wraps up before we'd kill it outright.
    _DEFAULT_RUN_BUDGET_SECONDS = 240
    #: How much longer than --run-budget to wait before subprocess itself
    #: gives up — covers Hermes' own wrap-up time after the budget notice.
    _TIMEOUT_BUFFER_SECONDS = 60

    _RATE_LIMIT_MARKERS = ("rate limit", "rate-limit", "429", "quota exceeded", "too many requests")

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        del api_key  # Hermes needs none — OAuth session already established.
        self._hermes_bin = shutil.which("hermes") or "/Users/zacharywolk/.local/bin/hermes"
        if not os.path.exists(self._hermes_bin):
            raise ModelProviderError(
                "hermes CLI not found on PATH or at /Users/zacharywolk/.local/bin/hermes."
            )
        #: Only set if the caller explicitly requests a model — Hermes' own
        #: currently-configured default is used otherwise (never guessed or
        #: overridden implicitly).
        self.requested_model = model
        self.run_budget_seconds = int(
            os.getenv("DIRECTOR_HERMES_RUN_BUDGET_SECONDS", str(self._DEFAULT_RUN_BUDGET_SECONDS))
        )
        #: Populated after a successful complete_structured() call with the
        #: model Hermes' own session record says actually answered.
        self.resolved_model: str | None = None

    def complete_structured(self, spec: StructuredCallSpec) -> dict[str, Any]:
        schema_field_names = list(spec.schema.get("properties", {}).keys())
        prompt = (
            f"{spec.system_prompt}\n\n{spec.user_content}\n\n"
            "Respond with ONLY a single JSON object — no markdown code fences, no prose before "
            "or after it — matching exactly this JSON schema:\n"
            f"{json.dumps(spec.schema)}\n\n"
            f"The JSON object's top-level keys must be exactly: {schema_field_names}."
        )

        args = [self._hermes_bin, "chat", "-q", prompt, "--oneshot", "-Q",
                "--source", "tool", "--ignore-rules", "--run-budget", str(self.run_budget_seconds)]
        if self.requested_model:
            args += ["-m", self.requested_model]

        try:
            result = subprocess.run(
                args, capture_output=True, text=True,
                timeout=self.run_budget_seconds + self._TIMEOUT_BUFFER_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise TransientModelProviderError(
                f"Hermes CLI timed out after {self.run_budget_seconds + self._TIMEOUT_BUFFER_SECONDS}s."
            ) from exc
        except OSError as exc:
            raise ModelProviderError(f"Hermes CLI failed to launch: {exc}") from exc

        combined_lower = (result.stdout + result.stderr).lower()
        if any(marker in combined_lower for marker in self._RATE_LIMIT_MARKERS):
            raise ModelProviderError(
                f"Hermes CLI appears rate-limited: {(result.stdout + result.stderr)[:500]}"
            )
        if result.returncode != 0:
            raise ModelProviderError(
                f"Hermes CLI exited {result.returncode}: {result.stderr[:500] or result.stdout[:500]}"
            )

        # `-Q` writes "session_id: <id>" to stderr, not stdout — stdout is
        # the pure response text with nothing to strip off it. Confirmed by
        # direct inspection: piping stdout/stderr together (a plain
        # terminal) makes them look interleaved on one stream, but
        # subprocess.run captures them separately and the id only ever
        # showed up in .stderr.
        session_id = self._extract_session_id(result.stderr)
        if session_id:
            self.resolved_model = self._lookup_model_for_session(session_id)

        return self._parse_json_response(result.stdout)

    @staticmethod
    def _extract_session_id(stderr: str) -> str | None:
        match = re.search(r"session_id:\s*(\S+)", stderr)
        return match.group(1) if match else None

    def _lookup_model_for_session(self, session_id: str) -> str | None:
        """Best-effort: ask Hermes' own session store which model actually
        answered. Never fatal — a failure here doesn't invalidate an
        otherwise-valid response, it just leaves resolved_model unset."""
        try:
            export = subprocess.run(
                [self._hermes_bin, "sessions", "export", "--format", "jsonl",
                 "--session-id", session_id, "-"],
                capture_output=True, text=True, timeout=30,
            )
            if export.returncode != 0:
                return None
            line = export.stdout.strip().splitlines()[0]
            return json.loads(line).get("model")
        except Exception:
            return None

    @staticmethod
    def _parse_json_response(text: str) -> dict[str, Any]:
        text = text.strip()
        fence_match = re.match(r"^```(?:json)?\s*\n(.*)\n```\s*$", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise TransientModelProviderError(
                    f"Hermes response was not valid JSON even after fence/brace extraction: {exc}. "
                    f"Raw (truncated): {text[:500]!r}"
                ) from exc
        raise TransientModelProviderError(f"Hermes response was not valid JSON. Raw (truncated): {text[:500]!r}")


_PROVIDERS: dict[str, type] = {
    "fixture": FixtureModelProvider,
    "anthropic": AnthropicModelProvider,
    "openrouter": OpenRouterModelProvider,
    "hermes_cli": HermesLocalCLIProvider,
    "openai": OpenAIModelProvider,
}


def get_model_provider(
    name: str | None = None, *, model: str | None = None, api_key: str | None = None
) -> ModelProvider:
    """Resolve a provider by name (default: ``DIRECTOR_PROVIDER`` env var,
    falling back to ``fixture`` — the safe, no-cost, no-network default)."""
    key = (name or os.getenv("DIRECTOR_PROVIDER") or "fixture").strip().lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ModelProviderError(f"Unknown provider {key!r}. Known providers: {sorted(_PROVIDERS)}.")
    return cls(model=model, api_key=api_key)
