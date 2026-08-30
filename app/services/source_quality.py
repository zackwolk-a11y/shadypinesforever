"""A rough, mechanical read on what kind of source a URL is (Packet 10, Part D).

Deliberately not a fact-checking system: this never says anything about
whether a source's *content* is true, only about what kind of publisher it
looks like, from its domain alone — the same "mechanism, not content" split
the rest of this codebase draws for belief/rabbit-hole arithmetic. Nothing
here calls a model. A domain this can't confidently place is classified
``UNKNOWN``, which is an entirely honest answer, not a shortfall — Part D is
explicit that "unknown is acceptable" and that this must never become an
unsupported factual claim in its own right.

Kept as a service function (not inside a provider adapter) so every
provider's sources get the same classification from the same rules —
provider adapters normalize *retrieval*; this normalizes *judgment about the
retrieval*, which belongs one layer up (Part I: provider-specific parsing
stays inside the adapter, nothing else leaks out of it).
"""

from __future__ import annotations

from app.domain.enums import SourceQualityTier

#: Suffix-matched, not exact-matched, so a subdomain (news.harvard.edu)
#: still classifies correctly.
_OFFICIAL_TLDS = (".gov", ".mil")
_ACADEMIC_TLDS = (".edu", ".ac.uk")

#: A short, deliberately conservative list of large, well-established news
#: operations — enough to make NEWS a real, useful category without
#: pretending to be an exhaustive media directory. Anything not on this list
#: simply falls through to UNKNOWN rather than a guess.
_NEWS_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org",
    "nytimes.com", "washingtonpost.com", "theguardian.com", "wsj.com",
    "bloomberg.com", "ft.com", "economist.com", "pitchfork.com",
    "rollingstone.com", "billboard.com",
}

_ACADEMIC_DOMAINS = {"jstor.org", "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "scholar.google.com"}
_COMMUNITY_DOMAINS = {"reddit.com", "wikipedia.org", "wikimedia.org"}
_BLOG_HOST_HINTS = ("medium.com", "substack.com", "blogspot.com", "wordpress.com", "tumblr.com")


def classify(domain: str | None) -> SourceQualityTier:
    """Classify a source purely from its domain. Never raises."""
    if not domain:
        return SourceQualityTier.UNKNOWN
    host = domain.lower().strip().removeprefix("www.")

    if host.endswith(_OFFICIAL_TLDS):
        return SourceQualityTier.OFFICIAL
    if host.endswith(_ACADEMIC_TLDS) or host in _ACADEMIC_DOMAINS or host.endswith(".edu"):
        return SourceQualityTier.ACADEMIC
    if host in _NEWS_DOMAINS or any(host.endswith(f".{d}") for d in _NEWS_DOMAINS):
        return SourceQualityTier.NEWS
    if host in _COMMUNITY_DOMAINS or any(host.endswith(f".{d}") for d in _COMMUNITY_DOMAINS):
        return SourceQualityTier.COMMUNITY
    if any(hint in host for hint in _BLOG_HOST_HINTS):
        return SourceQualityTier.BLOG
    if host.endswith(".org"):
        # A conservative middle ground: most .org domains are a nonprofit,
        # standards body, or industry association rather than a personal
        # site — INDUSTRY is a better-supported guess than UNKNOWN here, but
        # this is still a heuristic, not a verified affiliation.
        return SourceQualityTier.INDUSTRY

    return SourceQualityTier.UNKNOWN
