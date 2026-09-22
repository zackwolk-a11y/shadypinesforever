"""The Tavily adapter — the build bible's second research provider.

**Unverified.** This session has no ``TAVILY_API_KEY`` and no way to make a
live network call. Written against Tavily's publicly documented Search API
shape (``POST /search`` with a JSON body carrying ``api_key``/``query``, a
``results`` array of ``{title, url, content, raw_content, published_date}``),
parsed defensively. Treat the first live call as a smoke test, and re-check
field names against Tavily's current documentation before relying on it.

Requesting ``include_raw_content=True`` asks Tavily to return fuller extracted
page text alongside the short relevance snippet, so ``fetch_source`` here can
return a genuinely deeper passage than Brave's snippet-only adapter — this is
the provider to reach for when the depth of the excerpt matters.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.providers.research.base import ResearchProviderError
from app.schemas.research import SearchResponse, SourceCandidate, SourceDocument

_SEARCH_URL = "https://api.tavily.com/search"


class TavilyResearchProvider:
    """Search via the Tavily Search API."""

    name = "tavily"
    is_fixture = False

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise ResearchProviderError(
                "TAVILY_API_KEY is not set. Set it, or set RESEARCH_PROVIDER=fixture."
            )
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise ResearchProviderError(
                "The httpx package is not installed. Install it to use the Tavily "
                "provider, or set RESEARCH_PROVIDER=fixture."
            ) from exc
        self._httpx = httpx
        self._api_key = api_key

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        freshness: str | None = None,
    ) -> SearchResponse:
        body = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max(1, min(max_results, 20)),
            "search_depth": "basic",
            "include_raw_content": True,
        }
        if freshness == "week":
            body["topic"] = "news"

        try:
            response = self._httpx.post(_SEARCH_URL, json=body, timeout=20.0)
            response.raise_for_status()
            payload = response.json()
        except self._httpx.HTTPError as exc:
            raise ResearchProviderError(f"Tavily search request failed: {exc}") from exc
        except ValueError as exc:
            raise ResearchProviderError(f"Tavily search returned unparseable JSON: {exc}") from exc

        raw_results = payload.get("results") or []
        now = datetime.now(timezone.utc)
        results = [
            candidate
            for i, raw in enumerate(raw_results[:max_results], start=1)
            if (candidate := _parse_result(raw, now, i)) is not None
        ]
        return SearchResponse(provider=self.name, query=query, results=results, is_fixture=False)

    def search_recent(self, query: str, *, max_results: int = 5) -> SearchResponse:
        return self.search(query, max_results=max_results, freshness="week")

    def fetch_source(
        self,
        source: SourceCandidate,
        *,
        query: str | None = None,
        max_chars: int | None = None,
    ) -> SourceDocument:
        # provider_metadata carries what search already returned, since a
        # single Tavily call gives both the snippet and (with
        # include_raw_content) the fuller text — no second request needed.
        raw_content = (source.snippet or "").strip()
        if not raw_content:
            raise ResearchProviderError(
                f"Tavily returned no content to use as a passage for {source.url!r}"
            )
        if max_chars is not None:
            raw_content = raw_content[:max_chars]

        return SourceDocument(
            url=source.url,
            title=source.title,
            excerpt=raw_content,
            excerpt_sha256=hashlib.sha256(raw_content.encode()).hexdigest(),
            retrieved_at=datetime.now(timezone.utc),
            provider_metadata={"provider": self.name},
            is_fixture=False,
        )


def _parse_result(raw: dict, now: datetime, rank: int) -> SourceCandidate | None:
    url = raw.get("url")
    if not url:
        return None

    domain = None
    try:
        domain = urlparse(url).netloc or None
    except ValueError:
        pass

    published_at = None
    raw_date = raw.get("published_date")
    if raw_date:
        try:
            published_at = datetime.fromisoformat(raw_date)
        except ValueError:
            published_at = None

    # Prefer the fuller extracted text when Tavily provided it; fall back to
    # the short relevance snippet.
    content = raw.get("raw_content") or raw.get("content")

    return SourceCandidate(
        provider="tavily",
        provider_result_id=hashlib.sha256(url.encode()).hexdigest()[:16],
        url=url,
        title=raw.get("title") or url,
        domain=domain,
        author=None,
        publication=None,
        published_at=published_at,
        retrieved_at=now,
        source_type="article",
        snippet=content,
        rank=rank,
    )
