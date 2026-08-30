#!/usr/bin/env python3
"""Developer tool: one agent, one real research session, tightly bounded
(Packet 10, Part O).

Before letting all eight agents burn live research credits at once, this
lets you watch exactly one of them do exactly one piece of real research —
using its own current top interest as the question, and running through the
identical ``app.services.research.start_research`` path a real agent
decision takes (never a parallel implementation; see Part I).

Defaults to the fixture LLM provider (free, deterministic) so the only real
spend is the search itself — set ``LLM_PROVIDER=anthropic`` yourself if you
also want a live model's interpretation of the retrieved evidence.

Usage::

    export TAVILY_API_KEY="..."
    export RESEARCH_PROVIDER=tavily
    .venv/bin/python scripts/run_live_research_once.py --agent agent_roxy

    # a specific question instead of the agent's own top interest:
    .venv/bin/python scripts/run_live_research_once.py --agent agent_dex \\
        --question "What independent research exists on venue closures in 2024?"

Refuses to run against RESEARCH_PROVIDER=fixture (use scripts/run_event.py
or scripts/run_day.py for ordinary fixture-mode simulation instead) — this
script exists specifically to spend a small, deliberate amount of real
provider budget on one agent, not to simulate.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "village.db"

os.environ.setdefault("MAX_SEARCH_QUERIES_PER_SESSION", "2")
os.environ.setdefault("MAX_SOURCES_PER_QUERY", "3")
os.environ.setdefault("MAX_FETCHED_SOURCES_PER_SESSION", "2")
os.environ.setdefault("LLM_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", required=True, help="agent_id, e.g. agent_roxy")
    parser.add_argument("--question", default=None, help="override: skip the agent's own top interest")
    parser.add_argument("--database-url", default=None, help="defaults to the village's normal DATABASE_URL / village.db")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from app.core.config import get_settings

    settings = get_settings()
    if settings.research_provider == "fixture":
        print(
            "RESEARCH_PROVIDER is 'fixture'. This script is for spending a small, "
            "deliberate amount of real provider budget on one agent — for ordinary "
            "fixture-mode simulation, use scripts/run_event.py or scripts/run_day.py instead."
        )
        return 1
    key = settings.tavily_api_key if settings.research_provider == "tavily" else settings.brave_search_api_key
    if settings.research_provider in ("tavily", "brave") and not key:
        print(f"RESEARCH_PROVIDER={settings.research_provider} but its API key is not set.")
        return 1

    from sqlalchemy import select

    from app.db.models.agents import Agent, AgentInterest
    from app.db.models.world import SimulationClock
    from app.db.session import SessionLocal
    from app.domain.ids import new_correlation_id
    from app.providers.llm import get_llm_provider
    from app.providers.research import get_research_provider
    from app.services import research

    print(f"Database: {settings.database_url}")
    print(f"Provider: {settings.research_provider}  (key present: {bool(key)})")
    print(f"LLM provider: {settings.llm_provider}")
    print(
        f"Budget: {settings.max_search_queries_per_session} quer(y/ies), "
        f"{settings.max_sources_per_query} results/query, "
        f"{settings.max_fetched_sources_per_session} fetched max\n"
    )

    session = SessionLocal()
    try:
        agent = session.scalars(select(Agent).where(Agent.agent_id == args.agent)).first()
        if agent is None:
            print(f"No agent {args.agent!r}. Run scripts/seed_agents.py first, or check the id.")
            return 1
        clock = session.scalars(select(SimulationClock).limit(1)).first()
        if clock is None:
            print("No simulation clock. Run scripts/seed_agents.py first.")
            return 1

        question = args.question
        if not question:
            top_interest = session.scalars(
                select(AgentInterest)
                .where(AgentInterest.agent_id == agent.agent_id)
                .order_by(AgentInterest.strength.desc(), AgentInterest.id.desc())
                .limit(1)
            ).first()
            if top_interest is None:
                print(f"{agent.agent_id} has no interests recorded; pass --question explicitly.")
                return 1
            question = f"What is the current state of {top_interest.interest}?"

        print(f"{agent.agent_id} researching: {question!r}\n")

        llm_provider = get_llm_provider(settings)
        research_provider = get_research_provider(settings)
        outcome = research.start_research(
            session, agent, question, clock, new_correlation_id(),
            settings, llm_provider, research_provider,
        )
        session.commit()

        print(f"research_id: {outcome.research_id}")
        print(f"status: {outcome.status}")
        if outcome.unavailable:
            print(f"unavailable: {outcome.reason}")
        print(f"sources: {outcome.sources_found} found, {outcome.sources_fetched} fetched")
        print(f"findings: {outcome.findings_created}, claims: {outcome.claims_created}")
        print("\nInspect it directly:")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research.py")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research_usage.py --agent {agent.agent_id}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
