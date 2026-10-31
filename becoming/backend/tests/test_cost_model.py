import pytest

from becoming.cost_model import PRICES, Volume, daily_cost


def test_uncached_cost_is_plain_arithmetic():
    v = Volume(1_000_000, 100_000)
    assert daily_cost("claude-sonnet-5-5", v) == pytest.approx(2.00 + 1.00)


def test_caching_reduces_cost():
    plain = Volume(1_000_000, 0)
    cached = Volume(1_000_000, 0, cached_read_share=0.6, cached_write_share=0.1)
    for m in PRICES:
        assert daily_cost(m, cached) < daily_cost(m, plain)


def test_cache_shares_cannot_exceed_input():
    with pytest.raises(ValueError):
        daily_cost("claude-haiku-5-5", Volume(1, 1, 0.8, 0.3))
