"""The research provider boundary.

This is deliberately a separate hierarchy from ``app.providers.llm``. Whatever
company answers a search (Brave, Tavily, or Anthropic's own web search later)
is an entirely different decision from whatever company's model interprets the
results — the Village should be able to run Claude as the agent brain against
Tavily's index, or swap in another search vendor, without either side knowing
the other changed. Nothing in ``app/services/research.py`` imports a specific
provider; it asks for whatever ``get_research_provider(settings)`` returns.

Every method here is synchronous. The build bible's reference interface is
async, but Phase 1 runs one authoritative simulation writer over a synchronous
SQLAlchemy session — bridging to async here would buy concurrency nothing else
in this codebase can use yet, at the cost of a sync/async seam. Async fetching
can be introduced later behind this same Protocol without changing callers.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.research import SearchResponse, SourceCandidate, SourceDocument


class ResearchProviderError(RuntimeError):
    """Retrieval failed. The caller must not fabricate a result to cover for it.

    Raised for anything that keeps a real answer from coming back: a network
    failure, a missing or rejected API key, a malformed response, zero results,
    or a provider that was requested but is not installed. The research
    service's response to every one of these is the same — stop, and record
    RESEARCH_UNAVAILABLE — so the distinction between failure causes lives in
    the exception message, not in different exception types.
    """


class ResearchProvider(Protocol):
    """What every search adapter must offer, regardless of company."""

    name: str
    is_fixture: bool

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        freshness: str | None = None,
    ) -> SearchResponse:
        """Run one search. Raises :class:`ResearchProviderError` on failure."""
        ...

    def search_recent(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> SearchResponse:
        """Search biased toward recent results, where the provider supports it."""
        ...

    def fetch_source(
        self,
        source: SourceCandidate,
        *,
        query: str | None = None,
        max_chars: int | None = None,
    ) -> SourceDocument:
        """Retrieve bounded, exact text for one search result.

        Raises :class:`ResearchProviderError` if the source cannot be fetched;
        the caller decides whether that sinks the whole research session or is
        tolerable given other sources that did fetch.
        """
        ...
