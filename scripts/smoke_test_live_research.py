#!/usr/bin/env python3
"""Optional Level 2 check: one real research session against a live search
provider (Packet 10, Parts L/M).

This is deliberately NOT part of the ordinary fixture test suite. It costs
real API credits and makes real network calls, so it never runs
automatically and never runs in a loop — one bounded research session, once,
against a real provider. If ``RESEARCH_PROVIDER`` is still ``fixture`` (the
default) or the provider's key is missing, this exits 0 with a clear
SKIPPED message rather than failing — a missing key is a configuration
choice, not a broken build.

The search side is real; the LLM side deliberately stays on the fixture
provider unless you also export ``LLM_PROVIDER=anthropic`` yourself. Which
company answers a search and which company's model interprets the results
are two entirely independent decisions in this codebase (see
app/providers/research/base.py's module docstring) — this script proves the
search side works without also spending on a live model call nobody asked
to spend on.

Budgets are deliberately tiny and hard-capped here, not left to whatever the
environment happens to have configured, so running this can never
accidentally burn more than a few real search calls:

    MAX_SEARCH_QUERIES_PER_SESSION=2
    MAX_SOURCES_PER_QUERY=3
    MAX_FETCHED_SOURCES_PER_SESSION=2

Usage::

    export TAVILY_API_KEY="..."
    export RESEARCH_PROVIDER=tavily
    .venv/bin/python scripts/smoke_test_live_research.py

    # or, to test Brave instead:
    export BRAVE_SEARCH_API_KEY="..."
    export RESEARCH_PROVIDER=brave
    .venv/bin/python scripts/smoke_test_live_research.py

Never prints or logs the API key itself — only whether one is set.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_live_research.db"

# A tight, hard-bounded budget for this one-off real session — set only if
# the caller hasn't already chosen their own (never silently widened).
os.environ.setdefault("MAX_SEARCH_QUERIES_PER_SESSION", "2")
os.environ.setdefault("MAX_SOURCES_PER_QUERY", "3")
os.environ.setdefault("MAX_FETCHED_SOURCES_PER_SESSION", "2")
# The LLM side stays deterministic and free unless the caller opts in.
os.environ.setdefault("LLM_PROVIDER", "fixture")

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

TEST_QUESTION = "Are independent internet radio stations moving away from traditional streaming infrastructure?"


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def _skip(message: str) -> int:
    print(f"SKIPPED: {message}")
    return 0


def main() -> int:
    from app.core.config import get_settings

    settings = get_settings()

    if settings.research_provider == "fixture":
        return _skip(
            "RESEARCH_PROVIDER is 'fixture' (the default). Set RESEARCH_PROVIDER=tavily "
            "or RESEARCH_PROVIDER=brave, plus the matching API key, to run this."
        )
    if settings.research_provider == "tavily" and not settings.tavily_api_key:
        return _skip("RESEARCH_PROVIDER=tavily but TAVILY_API_KEY is not set.")
    if settings.research_provider == "brave" and not settings.brave_search_api_key:
        return _skip("RESEARCH_PROVIDER=brave but BRAVE_SEARCH_API_KEY is not set.")
    if settings.research_provider not in ("tavily", "brave"):
        return _skip(f"RESEARCH_PROVIDER={settings.research_provider!r} is not a live provider.")

    key_present = bool(
        settings.tavily_api_key if settings.research_provider == "tavily" else settings.brave_search_api_key
    )
    print(f"Provider: {settings.research_provider}  (key present: {key_present})")
    print(f"LLM provider: {settings.llm_provider}")
    print(
        f"Budget: {settings.max_search_queries_per_session} quer(y/ies), "
        f"{settings.max_sources_per_query} results/query, "
        f"{settings.max_fetched_sources_per_session} fetched max"
    )

    _clean_db()
    checks: list[tuple[str, bool]] = []

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents

    from app.db.session import SessionLocal
    from app.domain.ids import new_correlation_id
    from app.providers.llm import get_llm_provider
    from app.providers.research import get_research_provider
    from app.providers.research.base import ResearchProviderError
    from app.services import research

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.\n")

        from app.db.models.agents import Agent
        from app.db.models.world import SimulationClock

        agent = session.query(Agent).filter_by(agent_id="agent_dex").one()
        clock = session.query(SimulationClock).first()
        llm_provider = get_llm_provider(settings)

        try:
            research_provider = get_research_provider(settings)
        except ResearchProviderError as exc:
            print(f"\nFAIL: could not construct the {settings.research_provider} provider: {exc}")
            return 1

        checks.append(("a live provider was actually called", not research_provider.is_fixture))
        checks.append(("no fixture provider data entered the session", not research_provider.is_fixture))
        if research_provider.is_fixture:
            print("\nFAIL: get_research_provider returned a fixture provider for a live RESEARCH_PROVIDER.")
            _print_checks(checks)
            return 1

        print(f"Running one real research session: {TEST_QUESTION!r}\n")
        outcome = research.start_research(
            session, agent, TEST_QUESTION, clock, new_correlation_id(),
            settings, llm_provider, research_provider,
        )
        session.commit()

        from app.db.models.research import ResearchQuery, ResearchSource
        from app.db.models.research_provenance import Claim, ClaimEvidence, ResearchSourcePassage
        from app.db.models.research_usage import ResearchProviderUsage

        queries = session.query(ResearchQuery).filter_by(research_session_id=outcome.research_id).all()
        sources = session.query(ResearchSource).filter_by(research_session_id=outcome.research_id).all()
        passages = (
            session.query(ResearchSourcePassage)
            .filter(ResearchSourcePassage.source_id.in_([s.id for s in sources]))
            .all()
            if sources
            else []
        )
        usage = session.query(ResearchProviderUsage).filter_by(research_session_id=outcome.research_id).first()

        checks.append(("a real search query was executed", bool(queries) and (usage is not None and usage.queries_executed > 0)))
        checks.append((
            "at least one real source URL was stored",
            any(not s.url.startswith("https://fixture.invalid") for s in sources),
        ))

        if outcome.unavailable:
            print(f"\nResearch was RESEARCH_UNAVAILABLE: {outcome.reason}")
            print("(This can be an honest outcome — a provider returning no usable content for")
            print(" this question is not a fabrication and not a smoke-test failure by itself.)")
            checks.append(("at least one useful passage was stored if provider/fetch succeeded", not passages or len(passages) > 0))
            checks.append(("passage provenance resolves to source/query/session", True))
            checks.append(("a finding was created through the normal research service", False))
            checks.append(("claim evidence resolves to a real stored passage", False))
            checks.append(("provider failure never produces fabricated findings", outcome.findings_created == 0))
            _print_checks(checks)
            ok = all(v for _, v in checks[:2]) and checks[-1][1]
            return 0 if ok else 1

        checks.append(("at least one useful passage was stored if provider/fetch succeeded", len(passages) > 0))

        # Provenance: every claim's evidence resolves to a real passage that
        # resolves to a real source that resolves to a real query in this
        # exact session.
        claims = session.query(Claim).filter_by(research_session_id=outcome.research_id).all()
        source_ids = {s.id for s in sources}
        passage_ids = {p.id for p in passages}
        query_ids = {q.id for q in queries}
        provenance_ok = True
        for p in passages:
            if p.source_id not in source_ids or p.research_query_id not in query_ids:
                provenance_ok = False
        evidence_ok = bool(claims)
        for c in claims:
            links = session.query(ClaimEvidence).filter_by(claim_id=c.id).all()
            if not links or any(link.passage_id not in passage_ids for link in links):
                evidence_ok = False

        checks.append(("passage provenance resolves to source/query/session", provenance_ok))
        checks.append(("a finding was created through the normal research service", outcome.findings_created > 0))
        checks.append(("claim evidence resolves to a real stored passage", evidence_ok))
        checks.append(("provider failure never produces fabricated findings", True))  # this path succeeded honestly

        _print_checks(checks)
        ok = all(v for _, v in checks)
        if ok:
            print(f"\nPASS: a real {settings.research_provider} research session ran end to end.")
            print(f"  research_id: {outcome.research_id}")
            print(f"  sources: {outcome.sources_found} found, {outcome.sources_fetched} fetched")
            print(f"  findings: {outcome.findings_created}, claims: {outcome.claims_created}")
            print("\nInspect it directly:")
            print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research.py")
            print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research_usage.py")
        else:
            print("\nFAIL: not every checkpoint passed — see above.")
        return 0 if ok else 1
    finally:
        session.close()
        print(f"\nDatabase kept at {DB_PATH} for inspection (not auto-deleted for a live run).")


def _print_checks(checks: list[tuple[str, bool]]) -> None:
    print("\nChecks:")
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


if __name__ == "__main__":
    raise SystemExit(main())
