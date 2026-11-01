"""Reproducible model-cost estimates for the cost log (docs/COSTS.md).

Prices are USD per million tokens, copied from Anthropic's published pricing
page (platform.claude.com/docs/en/about-claude/pricing) on PRICES_AS_OF.
Re-check before relying on them. Volumes are assumptions, not measurements;
once the Steward runs, replace them with real numbers from the llm_calls table.

    python -m becoming.cost_model
"""

from __future__ import annotations

from dataclasses import dataclass

PRICES_AS_OF = "2026-10-31"


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write_5m: float
    cache_read: float
    batch_discount: float = 0.5  # Batch API halves input and output


PRICES: dict[str, Price] = {
    # Haiku 5.5 rates apply to prompts up to 100k tokens; village turns stay far below that.
    "claude-haiku-5-5": Price(0.10, 0.50, 0.125, 0.01),
    "claude-sonnet-5-5": Price(2.00, 10.00, 2.50, 0.10),
    "claude-opus-5-5": Price(4.00, 20.00, 5.00, 0.20),
}


@dataclass(frozen=True)
class Volume:
    """Tokens per real day (at default pacing, one real day is one simulated month; see D-006)."""
    input_tokens: float
    output_tokens: float
    cached_read_share: float = 0.0   # share of input served from cache
    cached_write_share: float = 0.0  # share of input written to cache


def daily_cost(model: str, v: Volume) -> float:
    p = PRICES[model]
    uncached = 1.0 - v.cached_read_share - v.cached_write_share
    if uncached < 0:
        raise ValueError("cache shares exceed 100% of input")
    m_in = v.input_tokens / 1e6
    return (m_in * (uncached * p.input + v.cached_read_share * p.cache_read
                    + v.cached_write_share * p.cache_write_5m)
            + v.output_tokens / 1e6 * p.output)


# Baseline assumptions (docs/COSTS.md): ~20 conversation episodes/day x ~12 turns
# x ~4k input tokens of context, ~150 visible output tokens/turn, +30% overhead
# for decisions, memory and reflection. "thinking" adds reasoning tokens (billed
# as output) at low effort, about 300 per call over about 312 calls.
DIALOGUE = Volume(1_300_000, 65_000)
DIALOGUE_CACHED = Volume(1_300_000, 65_000, cached_read_share=0.60, cached_write_share=0.10)
THINKING_EXTRA_OUTPUT = 94_000
# Nightly journal and reports: ~5 calls x ~30k input / ~4k output.
REPORTS = Volume(150_000, 20_000)


def scenario(model: str, activity: float = 1.0, thinking: bool = True) -> float:
    """Daily dialogue cost with caching, scaled by an activity multiplier."""
    v = Volume(DIALOGUE_CACHED.input_tokens * activity, DIALOGUE_CACHED.output_tokens * activity,
               DIALOGUE_CACHED.cached_read_share, DIALOGUE_CACHED.cached_write_share)
    extra = THINKING_EXTRA_OUTPUT * activity / 1e6 * PRICES[model].output if thinking else 0.0
    return daily_cost(model, v) + extra


EXPERIMENT_REAL_DAYS = 12  # 12 simulated months at one real day per simulated month


def main() -> None:
    print(f"Prices as of {PRICES_AS_OF} (USD). One real day = one simulated month (D-006).\n")
    print("Dialogue, with prompt caching and low-effort thinking:")
    print(f"{'Model':20} {'activity':>8} {'per real day':>13} {'12-mo experiment':>17} {'30 real days':>13}")
    for m in PRICES:
        for act in (1.0, 3.0):
            d = scenario(m, act)
            print(f"{m:20} {act:>7.0f}x {d:>13.2f} {d * EXPERIMENT_REAL_DAYS:>17.2f} {d * 30:>13.2f}")
    print("\nNightly journal & reports (per real day):")
    for m in ("claude-sonnet-5-5", "claude-opus-5-5"):
        r = daily_cost(m, REPORTS)
        print(f"  {m:20} standard {r:.2f}   batch {r * PRICES[m].batch_discount:.2f}")
    print("\nNo-cache dialogue at 1x (worst case, per real day): "
          + ", ".join(f"{m} {daily_cost(m, DIALOGUE):.2f}" for m in PRICES))


if __name__ == "__main__":
    main()
