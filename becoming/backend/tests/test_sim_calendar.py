"""Simulated time is its own quantity and never backfills offline time."""
import pytest

from becoming.sim_calendar import (
    DAYS_PER_MONTH, MINUTES_PER_DAY, MINUTES_PER_MONTH, CalendarConfig, SimTime,
)


def test_default_pacing_is_one_real_day_per_sim_month():
    cfg = CalendarConfig()
    ticks_per_real_day = 24 * 60 / cfg.real_minutes_per_tick
    assert ticks_per_real_day * cfg.sim_minutes_per_tick == MINUTES_PER_MONTH
    assert cfg.sim_minutes_per_tick == 450


def test_start_of_experiment():
    t = SimTime(0)
    assert (t.month, t.day, t.hour) == (1, 1, 0)
    assert t.season() == "spring" and t.phase == "night"
    assert t.label() == "Month 1, Day 1, 00:00 (Spring, night)"


def test_month_and_season_rollover():
    t = SimTime(3 * MINUTES_PER_MONTH)
    assert t.month == 4 and t.day == 1 and t.season() == "summer"
    assert SimTime(MINUTES_PER_MONTH - 1).day == DAYS_PER_MONTH


def test_experiment_completes_after_twelve_months():
    assert not SimTime(12 * MINUTES_PER_MONTH - 1).experiment_complete
    assert SimTime(12 * MINUTES_PER_MONTH).experiment_complete


def test_ticks_advance_by_exactly_one_step_no_backfill():
    # Advancing is the only way time moves; there is no "advance to now".
    cfg = CalendarConfig()
    t = SimTime(0).advance(cfg.sim_minutes_per_tick)
    assert t.minutes == 450
    assert not hasattr(SimTime, "advance_to_wall_clock")
    with pytest.raises(ValueError):
        t.advance(0)


def test_phases():
    assert SimTime(6 * 60).phase == "dawn"
    assert SimTime(13 * 60).phase == "midday"
    assert SimTime(MINUTES_PER_DAY - 1).phase == "night"


def test_configurable_season_start():
    assert SimTime(0).season(CalendarConfig(first_season_index=2)) == "autumn"
