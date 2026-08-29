"""The Brave Search adapter — the build bible's primary research provider.

**Unverified.** This session has no ``BRAVE_SEARCH_API_KEY`` and no way to make
a live network call, so unlike the fixture provider this has not been
exercised against the real API. It is written against Brave's publicly
documented Web Search API shape (``GET /res/v1/web/search``, header
``X-Subscription-Token``, response nested under ``web.results``), parsed
defensively — every field access falls back to ``None`` rather than raising —
so a small shape drift degrades a single result instead of crashing the
adapter. Treat the first live call as a smoke test, and re-check the field
names against Brave's current documentation before relying on it.

Brave's public Search API returns snippets, not full page bodies. There is no
attempt here to separately fetch and parse the live page for a deeper excerpt
— that would mean building and maintaining an HTML-extraction pipeline this
session cannot verify either. ``fetch_source`` therefore returns the search
snippet, bounded, as the passage. A provider that does real extraction (Tavily,
with ``include_raw_content``) is a better choice when the deeper excerpt
matters more than staying inside one vendor.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.providers.research.base import ResearchProviderError
from app.schemas.research import SearchResponse, SourceCandidate, SourceDocument

_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

#: Brave's freshness codes: past day / week / month / year.
_FRESHNESS_CODES = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}


class BraveResearchProvider:
    """Search via the Brave Search API."""

    name = "brave"
    is_fixture = False

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise ResearchProviderError(
                "BRAVE_SEARCH_API_KEY is not set. Set it, or set RESEARCH_PROVIDER=fixture."
            )
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise ResearchProviderError(
                "The httpx package is not installed. Install it to use the Brave "
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
        params: dict = {"q": query, "count": max(1, min(max_results, 20))}
        code = _FRESHNESS_CODES.get(freshness or "", freshness)
        if code:
            params["freshness"] = code

        try:
            response = self._httpx.get(
                _SEARCH_URL,
                params=params,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._api_key,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
        except self._httpx.HTTPError as exc:
            raise ResearchProviderError(f"Brave search request failed: {exc}") from exc
        except ValueError as exc:
            raise ResearchProviderError(f"Brave search returned unparseable JSON: {exc}") from exc

        raw_results = ((payload.get("web") or {}).get("results")) or []
        now = datetime.now(timezone.utc)
        results = [
            candidate
            for raw in raw_results[:max_results]
            if (candidate := _parse_result(raw, now)) is not None
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
        # Brave's public Search API has no full-content endpoint — see module
        # docstring. The snippet from search is the best bounded text available
        # without a separate extraction pipeline.
        excerpt = (source.snippet or "").strip()
        if not excerpt:
            raise ResearchProviderError(
                f"Brave returned no snippet to use as a passage for {source.url!r}"
            )
        if max_chars is not None:
            excerpt = excerpt[:max_chars]

        return SourceDocument(
            url=source.url,
            title=source.title,
            excerpt=excerpt,
            excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            retrieved_at=datetime.now(timezone.utc),
            provider_metadata={"provider": self.name, "source": "search_snippet"},
            is_fixture=False,
        )


def _parse_result(raw: dict, now: datetime) -> SourceCandidate | None:
    url = raw.get("url")
    if not url:
        return None
    domain = None
    try:
        domain = urlparse(url).netloc or None
    except ValueError:
        pass

    profile = raw.get("profile") or {}
    return SourceCandidate(
        provider="brave",
        provider_result_id=hashlib.sha256(url.encode()).hexdigest()[:16],
        url=url,
        title=raw.get("title") or url,
        domain=domain,
        author=None,  # Brave's web results do not carry a structured author.
        publication=profile.get("long_name") or profile.get("name"),
        published_at=None,  # Brave gives relative ages ("2 days ago"), not dates.
        retrieved_at=now,
        source_type="article",
        snippet=raw.get("description"),
    )
