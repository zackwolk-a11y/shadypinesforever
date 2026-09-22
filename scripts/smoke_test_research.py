#!/usr/bin/env python3
"""Deterministic Packet 5 smoke test: drives the real loop until an agent
autonomously chooses START_RESEARCH, then asserts the full pipeline ran.

This does NOT insert a finished research record into the database. It goes
through the exact path live Brave/Tavily research will use later:

    scheduler picks an agent
      -> FixtureLLMProvider.complete() — the agent's OWN decision, which
         may or may not be START_RESEARCH; nothing here forces it
      -> orchestrator validation (budget, shape, content)
      -> app.services.research.start_research()
      -> FixtureResearchProvider.search() / .fetch_source() — the same
         ResearchProvider interface Brave/Tavily implement
      -> persisted query, sources, passages, findings, claims, evidence links

It runs against its own throwaway SQLite database (deleted first, so it never
touches village.db) and a fixed default seed, so the same sequence of agent
choices happens every run. If START_RESEARCH doesn't fire within the event
ceiling, that is itself a meaningful signal — something changed in the action
weights or validation — so the script fails loudly rather than silently
passing on a day that happened to skip research.

Usage::

    python scripts/smoke_test_research.py
    python scripts/smoke_test_research.py --seed other-seed --max-events 500
    python scripts/smoke_test_research.py --keep-db   # inspect afterward
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_research.db"

# Must be set before anything under app/ is imported: engines and settings are
# read at construction/call time, and this test must never touch village.db.
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet5-smoke"
DEFAULT_MAX_EVENTS = 250


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument(
        "--keep-db", action="store_true", help="don't delete the throwaway database on exit"
    )
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents  # scripts/seed_agents.py

    from app.core.config import get_settings
    from app.db.models import (
        Claim,
        ClaimEvidence,
        ResearchFinding,
        ResearchSession,
        ResearchSource,
    )
    from app.db.models.research_provenance import ResearchSourcePassage
    from app.db.session import SessionLocal
    from app.domain.enums import ResearchStatus
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event

    settings = get_settings()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")
    print(f"LLM_PROVIDER={settings.llm_provider}  RESEARCH_PROVIDER={settings.research_provider}")
    if not settings.uses_fixture_llm or not settings.uses_fixture_research:
        print(
            "This smoke test requires the fixture providers on both sides "
            "(unset LLM_PROVIDER / RESEARCH_PROVIDER, or set both to 'fixture')."
        )
        return 1

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.\n")

        provider = get_llm_provider(settings)
        research_session_id: str | None = None

        print(f"Driving RUN NEXT EVENT (seed={args.seed!r}) until an agent chooses START_RESEARCH...")
        for i in range(1, args.max_events + 1):
            outcome = run_next_event(
                session, settings=settings, provider=provider,
                seed=args.seed, auto_advance=True,
            )
            session.commit()

            if outcome.research is not None and not outcome.research.unavailable:
                research_session_id = outcome.research.research_id
                print(
                    f"  [{i}] {outcome.activated_agent_id} chose START_RESEARCH -> "
                    f"{research_session_id}"
                )
                break
            if outcome.research is not None and outcome.research.unavailable:
                # The fixture provider should never itself fail; if this fires,
                # something is wrong with the fixture path, not with luck.
                print(f"  [{i}] START_RESEARCH ran but was RESEARCH_UNAVAILABLE: {outcome.research.reason}")
                print("FAIL: the fixture research pipeline reported unavailable — see reason above.")
                return 1
        else:
            print(
                f"\nFAIL: no agent chose START_RESEARCH within {args.max_events} events.\n"
                "This can mean the action weights changed, validation now rejects it "
                "unconditionally, or the seed needs updating. Try a higher --max-events "
                "or a different --seed before assuming the pipeline itself is broken."
            )
            return 1

        # ------------------------------------------------------------------
        # Assert the full pipeline actually persisted, end to end. Every
        # assertion below reads back rows written by start_research() through
        # the real ResearchProvider interface — nothing is inserted directly.
        # ------------------------------------------------------------------
        rs = session.query(ResearchSession).filter_by(research_id=research_session_id).one()
        checks: list[tuple[str, bool]] = []

        checks.append(("research session status is COMPLETED", rs.status is ResearchStatus.COMPLETED))
        checks.append(("research session flagged is_fixture", rs.is_fixture is True))

        sources = session.query(ResearchSource).filter_by(research_session_id=rs.research_id).all()
        checks.append(("at least one source was stored", len(sources) > 0))
        checks.append(
            ("every source is labelled provider='fixture'", all(s.provider == "fixture" for s in sources))
        )

        passages = (
            session.query(ResearchSourcePassage)
            .join(ResearchSource, ResearchSourcePassage.source_id == ResearchSource.id)
            .filter(ResearchSource.research_session_id == rs.research_id)
            .all()
        )
        checks.append(("at least one source was fetched into a passage", len(passages) > 0))

        import hashlib

        checks.append(
            (
                "every passage's sha256 matches its own text",
                all(
                    hashlib.sha256(p.excerpt_text.encode()).hexdigest() == p.excerpt_sha256
                    for p in passages
                ),
            )
        )

        findings = session.query(ResearchFinding).filter_by(research_session_id=rs.research_id).all()
        checks.append(("at least one finding was created", len(findings) > 0))

        claims = session.query(Claim).filter_by(research_session_id=rs.research_id).all()
        evidence_links = (
            session.query(ClaimEvidence)
            .filter(ClaimEvidence.claim_id.in_([c.id for c in claims]))
            .all()
            if claims
            else []
        )
        checks.append(("at least one evidence link resolves a claim to a real passage", len(evidence_links) > 0))
        passage_ids = {p.id for p in passages}
        checks.append(
            (
                "every evidence link points at a passage from this session",
                all(link.passage_id in passage_ids for link in evidence_links),
            )
        )

        print(f"\nAsserting the pipeline for {research_session_id}:")
        all_ok = True
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
            all_ok &= ok

        if not all_ok:
            print("\nFAIL: one or more pipeline assertions failed. See above.")
            return 1

        print(f"\nPASS: the full research pipeline ran end to end for {research_session_id}.")
        print("\nInspect it directly:")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research.py")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())
