"""Provider preflight — "can we actually make a call right now?"

A bounded trial needs a fresh answer to that at the start of every session
and before resuming from any pause: a subscription window may have reset or
not, a laptop may have dropped its connection, a CLI login may have expired.
Before this module the only way to find out was to run a real agent turn and
let it fail — which, for a non-quota failure, used to be logged as the
*agent's* invalid decision.

One tiny structured call, classified the same way the orchestrator classifies
failures: OK, RATE_LIMITED (quota/429 — wait for the window), UNAVAILABLE
(credentials/login — a human must fix it), ERROR (timeout/connection —
usually transient; retry with backoff). Never writes to the database.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.providers.llm.base import LLMError, LLMProvider, LLMProviderUnavailable, LLMRateLimited

OK, RATE_LIMITED, UNAVAILABLE, ERROR = "OK", "RATE_LIMITED", "UNAVAILABLE", "ERROR"


class ProviderProbe(BaseModel):
    """Reply with ok=true."""

    model_config = {"extra": "forbid"}

    ok: bool = Field(description="Always true.")


@dataclass(frozen=True)
class ProbeResult:
    status: str
    detail: str
    latency_ms: int
    attempts: int

    @property
    def ok(self) -> bool:
        return self.status == OK


def probe_once(provider: LLMProvider, settings: Settings) -> ProbeResult:
    if provider.is_fixture:
        return ProbeResult(OK, "fixture provider — no live call made", 0, 1)
    started = time.perf_counter()
    try:
        result = provider.complete(
            system="Health check. Reply with ok=true.",
            user="ok?",
            model=settings.agent_model,
            purpose="provider_probe",
            output_type=ProviderProbe,
            max_tokens=32,
        )
    except LLMRateLimited as exc:
        return ProbeResult(RATE_LIMITED, str(exc)[:300], _ms(started), 1)
    except LLMProviderUnavailable as exc:
        return ProbeResult(UNAVAILABLE, str(exc)[:300], _ms(started), 1)
    except LLMError as exc:
        return ProbeResult(ERROR, str(exc)[:300], _ms(started), 1)
    if not getattr(result.output, "ok", False):
        return ProbeResult(ERROR, "probe returned ok=false", _ms(started), 1)
    return ProbeResult(OK, f"{result.provider}:{result.model}", _ms(started), 1)


def probe_with_backoff(
    provider: LLMProvider,
    settings: Settings,
    *,
    attempts: int = 1,
    wait_seconds: float = 60.0,
    max_wait_seconds: float = 900.0,
    sleep=time.sleep,
) -> ProbeResult:
    """Retry transient ERRORs (dropped connection, timeout) with exponential
    backoff. RATE_LIMITED and UNAVAILABLE return immediately: waiting a
    minute won't fix a spent quota window or an expired login."""
    result = probe_once(provider, settings)
    tried = 1
    delay = wait_seconds
    while result.status == ERROR and tried < attempts:
        sleep(delay)
        delay = min(max_wait_seconds, delay * 2)
        result = probe_once(provider, settings)
        tried += 1
    return ProbeResult(result.status, result.detail, result.latency_ms, tried)


def _ms(started: float) -> int:
    return max(1, int((time.perf_counter() - started) * 1000))
