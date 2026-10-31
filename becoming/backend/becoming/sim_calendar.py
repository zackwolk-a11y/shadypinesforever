"""The experimental simulation calendar.

Design (see docs/DECISIONS.md D-006):

- Simulated time is its own quantity, measured in simulated minutes since the
  start of the experiment. It is never derived from wall-clock timestamps.
- Simulated time advances ONLY when the scheduler executes a tick. Paused or
  offline periods do not advance it, and nothing is backfilled. If the server
  was down for six real hours, the village simply did not live those hours,
  and a gap record says so.
- Pacing target: one real day ~ one simulated month (30 simulated days), so
  the default ratio is 30 simulated minutes per real minute. With the default
  15-minute evaluation cadence, each tick advances 450 simulated minutes.
  Both values are configuration.
- The founding experiment lasts 12 simulated months.
"""

from __future__ import annotations

from dataclasses import dataclass

MINUTES_PER_DAY = 24 * 60
DAYS_PER_MONTH = 30
MINUTES_PER_MONTH = MINUTES_PER_DAY * DAYS_PER_MONTH
EXPERIMENT_MONTHS = 12

SEASONS = ("spring", "summer", "autumn", "winter")
PHASES = (  # (start hour, name)
    (0, "night"), (5, "dawn"), (8, "morning"), (12, "midday"),
    (15, "afternoon"), (18, "evening"), (21, "night"),
)


@dataclass(frozen=True)
class CalendarConfig:
    real_minutes_per_tick: float = 15.0
    sim_minutes_per_real_minute: float = 30.0  # 1 real day = 30 sim days
    first_season_index: int = 0  # month 1 begins in spring

    @property
    def sim_minutes_per_tick(self) -> int:
        return round(self.real_minutes_per_tick * self.sim_minutes_per_real_minute)


@dataclass(frozen=True, order=True)
class SimTime:
    minutes: int  # simulated minutes since the experiment began (>= 0)

    def __post_init__(self) -> None:
        if self.minutes < 0:
            raise ValueError("simulated time cannot be negative")

    @property
    def month(self) -> int:  # 1-based
        return self.minutes // MINUTES_PER_MONTH + 1

    @property
    def day(self) -> int:  # 1-based day of month
        return (self.minutes % MINUTES_PER_MONTH) // MINUTES_PER_DAY + 1

    @property
    def day_index(self) -> int:  # 0-based absolute day
        return self.minutes // MINUTES_PER_DAY

    @property
    def hour(self) -> int:
        return (self.minutes % MINUTES_PER_DAY) // 60

    @property
    def minute(self) -> int:
        return self.minutes % 60

    @property
    def phase(self) -> str:
        name = PHASES[0][1]
        for start, label in PHASES:
            if self.hour >= start:
                name = label
        return name

    def season(self, config: CalendarConfig = CalendarConfig()) -> str:
        quarter = ((self.month - 1) % 12) // 3
        return SEASONS[(quarter + config.first_season_index) % 4]

    @property
    def experiment_complete(self) -> bool:
        return self.month > EXPERIMENT_MONTHS

    def advance(self, sim_minutes: int) -> "SimTime":
        if sim_minutes <= 0:
            raise ValueError("a tick must advance time")
        return SimTime(self.minutes + sim_minutes)

    def label(self, config: CalendarConfig = CalendarConfig()) -> str:
        return (f"Month {self.month}, Day {self.day}, {self.hour:02d}:{self.minute:02d} "
                f"({self.season(config).title()}, {self.phase})")


@dataclass(frozen=True)
class OfflineGap:
    """A recorded period when the simulation did not run.

    Reports render this as "the village was not running", never as activity.
    """
    real_seconds: float
    resumed_at: SimTime
    reason: str  # e.g. "server_offline", "paused_by_founder", "provider_rate_limited"
