"""What the Village costs to run — one place, used by every kind of model call.

Agent decisions and research synthesis both spend tokens; both write through
here so ``llm_runs`` stays the single source of truth for "was this worth the
API cost", per the build bible's Day 7 question.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import MODEL_PRICES_USD_PER_MTOK
from app.db.models.telemetry import LLMRun
from app.providers.llm.base import LLMResult


def estimate_cost_usd(model: str, usage) -> float:
    """Rough spend for one call, from the operator-maintained price table.

    Fixture runs cost nothing and are reported as zero — never as what the same
    tokens would have cost live, which would make a fixture day look like a
    priced one. An unrecognised live model also returns zero; check the model
    against MODEL_PRICES_USD_PER_MTOK before reading a cost report as complete.
    """
    if model.startswith("fixture:"):
        return 0.0
    prices = MODEL_PRICES_USD_PER_MTOK.get(model)
    if not prices:
        return 0.0
    inp, out = prices
    return (usage.input_tokens * inp + usage.output_tokens * out) / 1_000_000


def record_llm_run(
    session: Session,
    result: LLMResult,
    *,
    purpose: str,
    agent_id: str | None,
    prompt_version: str | None = None,
) -> LLMRun:
    """Persist one model call's telemetry and return the row (already flushed,
    so it has an id the caller can cite)."""
    run = LLMRun(
        purpose=purpose,
        agent_id=agent_id,
        provider=result.provider,
        model=result.model,
        is_fixture=result.is_fixture,
        prompt_version=prompt_version,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
        cache_read_input_tokens=result.usage.cache_read_input_tokens,
        estimated_cost_usd=estimate_cost_usd(result.model, result.usage),
        latency_ms=result.latency_ms,
        stop_reason=result.usage.stop_reason,
        retry_count=result.usage.retry_count,
    )
    session.add(run)
    session.flush()
    return run
