"""Runtime configuration, read from the environment.

Every knob the Village has lives here rather than being spread through the code
— model identifiers especially, since providers retire model IDs and a routing
change should never require editing a service.

Values are read at call time, not import time, so tests and scripts can set the
environment before anything is constructed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "sqlite:///./village.db"

#: (input, output) US dollars per million tokens, for local budgeting only.
#: Operator-maintained — verify against current published pricing before
#: trusting a cost report. Unknown models estimate as zero rather than guessing.
MODEL_PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
}


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    """A snapshot of the environment."""

    app_env: str
    database_url: str

    # LLM routing. Model IDs are configuration, never literals in service code.
    llm_provider: str
    anthropic_api_key: str | None
    agent_model: str
    research_model: str
    report_model: str
    research_effort: str
    report_effort: str

    # Simulation budgets (§ "soft global research throttling").
    max_conversation_turns: int
    max_context_memories: int
    max_context_recent_findings: int
    max_context_wall_headlines: int
    max_daily_agent_activations: int

    @property
    def uses_fixture_llm(self) -> bool:
        """True when decisions come from the fixture provider, not a live model."""
        return self.llm_provider == "fixture"


def get_settings() -> Settings:
    """Build a Settings snapshot from the current environment."""
    return Settings(
        app_env=_env("APP_ENV", "development"),
        database_url=_env("DATABASE_URL", DEFAULT_DATABASE_URL),
        llm_provider=_env("LLM_PROVIDER", "fixture").strip().lower(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        agent_model=_env("VILLAGE_AGENT_MODEL", "claude-haiku-4-5"),
        research_model=_env("VILLAGE_RESEARCH_MODEL", "claude-sonnet-5"),
        report_model=_env("VILLAGE_REPORT_MODEL", "claude-sonnet-5"),
        research_effort=_env("VILLAGE_RESEARCH_EFFORT", "low"),
        report_effort=_env("VILLAGE_REPORT_EFFORT", "medium"),
        max_conversation_turns=_env_int("MAX_CONVERSATION_TURNS", 8),
        max_context_memories=_env_int("MAX_CONTEXT_MEMORIES", 6),
        max_context_recent_findings=_env_int("MAX_CONTEXT_RECENT_FINDINGS", 5),
        max_context_wall_headlines=_env_int("MAX_CONTEXT_WALL_HEADLINES", 5),
        max_daily_agent_activations=_env_int("MAX_DAILY_AGENT_ACTIVATIONS", 6),
    )


def get_database_url() -> str:
    """Shortcut for the one setting nearly everything needs."""
    return _env("DATABASE_URL", DEFAULT_DATABASE_URL)
