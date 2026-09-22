"""Research provider selection."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.providers.research.base import ResearchProvider, ResearchProviderError

__all__ = ["ResearchProvider", "ResearchProviderError", "get_research_provider"]


def get_research_provider(settings: Settings | None = None) -> ResearchProvider:
    """Build the configured provider. Defaults to the fixture.

    Construction failures (missing key, missing dependency) raise
    :class:`ResearchProviderError` rather than any other exception type, so a
    caller can catch exactly one thing and treat "misconfigured" the same way
    it treats "the network is down": RESEARCH_UNAVAILABLE, never a fabricated
    result.
    """
    settings = settings or get_settings()

    if settings.research_provider == "fixture":
        from app.providers.research.fixture import FixtureResearchProvider

        return FixtureResearchProvider()

    if settings.research_provider == "brave":
        from app.providers.research.brave import BraveResearchProvider

        return BraveResearchProvider(api_key=settings.brave_search_api_key)

    if settings.research_provider == "tavily":
        from app.providers.research.tavily import TavilyResearchProvider

        return TavilyResearchProvider(api_key=settings.tavily_api_key)

    raise ResearchProviderError(
        f"Unknown RESEARCH_PROVIDER {settings.research_provider!r}; "
        "expected 'fixture', 'brave', or 'tavily'."
    )
