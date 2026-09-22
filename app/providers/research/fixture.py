"""A deterministic stand-in for a web search provider.

Everything about its output announces itself as fake: the domain is
``fixture.invalid`` (RFC 2606 reserves ``.invalid`` for names that are never
real), every title and excerpt is prefixed ``[fixture]``, and every result
carries ``is_fixture=True``. A fixture citation can never be mistaken for a
live one even if someone reads the database directly.

Two sentinel substrings let tests drive the failure paths deterministically,
without needing a real outage to exercise "never fabricate when retrieval
fails":

- a query containing ``FORCE_RESEARCH_FAILURE`` raises :class:`ResearchProviderError`
- a query containing ``FORCE_EMPTY_RESULTS`` returns zero results
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone

from app.providers.research.base import ResearchProviderError
from app.schemas.research import SearchResponse, SourceCandidate, SourceDocument

FORCE_FAILURE_SENTINEL = "FORCE_RESEARCH_FAILURE"
FORCE_EMPTY_SENTINEL = "FORCE_EMPTY_RESULTS"

_FIXTURE_DOMAIN = "fixture.invalid"


class FixtureResearchProvider:
    """Deterministic search results seeded by the query text."""

    name = "fixture"
    is_fixture = True

    def __init__(self, seed: str = "village-research") -> None:
        self._seed = seed

    def _rng(self, *parts: str) -> random.Random:
        digest = hashlib.sha256("|".join((self._seed, *parts)).encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        freshness: str | None = None,
    ) -> SearchResponse:
        if FORCE_FAILURE_SENTINEL in query:
            raise ResearchProviderError(
                f"[fixture] simulated provider failure for query {query!r}"
            )
        if FORCE_EMPTY_SENTINEL in query:
            return SearchResponse(provider=self.name, query=query, results=[], is_fixture=True)

        rng = self._rng("search", query, freshness or "")
        now = datetime.now(timezone.utc)
        count = min(max_results, rng.randint(2, 4))

        results = []
        for i in range(count):
            slug = hashlib.sha256(f"{query}|{i}".encode()).hexdigest()[:10]
            published = now - timedelta(days=rng.randint(3, 900))
            results.append(
                SourceCandidate(
                    provider=self.name,
                    provider_result_id=slug,
                    url=f"https://{_FIXTURE_DOMAIN}/articles/{slug}",
                    title=f"[fixture] A source on: {query}",
                    domain=_FIXTURE_DOMAIN,
                    author=f"[fixture] Author {i + 1}",
                    publication="[fixture] Fixture Gazette",
                    published_at=published,
                    retrieved_at=now,
                    source_type="article",
                    snippet=f"[fixture] A snippet touching on {query}, result {i + 1} of {count}.",
                    rank=i + 1,
                )
            )
        return SearchResponse(provider=self.name, query=query, results=results, is_fixture=True)

    def search_recent(self, query: str, *, max_results: int = 5) -> SearchResponse:
        return self.search(query, max_results=max_results, freshness="week")

    def fetch_source(
        self,
        source: SourceCandidate,
        *,
        query: str | None = None,
        max_chars: int | None = None,
    ) -> SourceDocument:
        if source.domain != _FIXTURE_DOMAIN:
            # A live SourceCandidate handed to the fixture fetcher would produce
            # a passage that looks fixture but cites a real URL — worse than
            # simply refusing.
            raise ResearchProviderError(
                f"[fixture] refusing to fetch a non-fixture source: {source.url!r}"
            )

        rng = self._rng("fetch", source.url, query or "")
        sentences = [
            f"[fixture] This is bounded fixture text standing in for {source.url}.",
            f"[fixture] It discusses {query or 'the topic'} in general terms.",
            "[fixture] A second sentence adds a made-up but clearly-labelled detail.",
            "[fixture] A third sentence closes out the excerpt.",
        ]
        excerpt = " ".join(sentences[: 2 + rng.randint(0, 1)])
        if max_chars is not None:
            excerpt = excerpt[:max_chars]

        return SourceDocument(
            url=source.url,
            title=source.title,
            excerpt=excerpt,
            excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            retrieved_at=datetime.now(timezone.utc),
            provider_metadata={"provider": self.name, "fixture": True},
            is_fixture=True,
        )
