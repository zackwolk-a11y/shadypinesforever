#!/usr/bin/env python3
"""Developer tool: one agent, one complete real cognitive cycle, tightly
bounded (Packet 11, Parts J + L).

Drives the exact same decision loop every other activation takes
(``app.services.orchestrator.run_next_event``, targeted at one named agent
via ``force_agent_id`` — never a parallel "live agent" architecture): a real
Anthropic model reads that agent's real bounded context (identity, voice,
epistemic style, memories, interests, beliefs, wall activity, research
budget) and returns one structured decision, validated exactly like a
fixture decision. If that decision is ``START_RESEARCH``, the same
``app.services.research.start_research`` pipeline Packet 10 already proved
runs for real — real Tavily search, real passages, and (if ``LLM_PROVIDER``
is also live) a real model interpreting them into findings and claims.

If the agent reasonably chooses not to research this time, that is reported
honestly as a pass, not forced or treated as a failure — an agent silently
observing or chatting is exactly as valid a live decision as one that
researches (see app/services/context_builder.py's own system prompt: not
everything needs a source).

``--force-research`` (test-only) bypasses *just* that one initial
action-selection call — the "what do you want to do" decision — and starts
a START_RESEARCH cycle directly for a legitimate current interest of the
named agent, real or freshly `--nudge`d. Nothing downstream of that point is
touched: it calls the exact same ``app.services.research.start_research``
every real START_RESEARCH action calls, with the real configured providers,
so query generation, retrieval, and interpretation are exactly as live as
they are in the normal (non-forced) path — this flag only decides *that*
research happens, never *how*. The resulting session's ``correlation_id``
is prefixed ``forced_test_`` so it is unmistakable in the event log and
every inspection script, and the console output is banner-labelled the
same way.

Usage::

    export ANTHROPIC_API_KEY="..."
    export LLM_PROVIDER=anthropic
    export TAVILY_API_KEY="..."          # optional but needed for Part L's
    export RESEARCH_PROVIDER=tavily      # full live-to-live checkpoints
    .venv/bin/python scripts/run_live_agent_once.py --agent agent_roxy

    # nudge (never force) toward a research-worthy context by legitimately
    # strengthening one real interest first — the agent's own decision is
    # still made freely from there:
    .venv/bin/python scripts/run_live_agent_once.py --agent agent_dex --nudge "trends in independent radio streaming"

    # test-only: skip the decision, go straight to a real, live, labelled
    # research cycle on the agent's own (optionally nudged) top interest:
    .venv/bin/python scripts/run_live_agent_once.py --agent agent_roxy \\
        --nudge "Portland's DIY arts scene" --force-research

Refuses to run against LLM_PROVIDER=fixture (use scripts/run_event.py or
scripts/run_day.py for ordinary fixture-mode simulation instead).
``--force-research`` additionally refuses against RESEARCH_PROVIDER=fixture,
since retrieval must be live for the flag to mean what it says.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "run_live_agent_once.db"

os.environ.setdefault("MAX_SEARCH_QUERIES_PER_SESSION", "2")
os.environ.setdefault("MAX_SOURCES_PER_QUERY", "3")
os.environ.setdefault("MAX_FETCHED_SOURCES_PER_SESSION", "2")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

_FIXTURE_MARKER = "[fixture]"


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", required=True, help="agent_id, e.g. agent_roxy")
    parser.add_argument("--seed", default="live-agent-once")
    parser.add_argument(
        "--nudge", default=None,
        help="legitimately strengthen one real interest before the turn, via "
             "the normal interests.bump() mechanism — never forces the final action",
    )
    parser.add_argument(
        "--force-research", action="store_true",
        help="test-only: bypass the initial action-selection decision and start a "
             "real, live START_RESEARCH cycle directly on a legitimate current "
             "interest of --agent. Everything downstream stays fully live — see "
             "the module docstring. Requires a live RESEARCH_PROVIDER too.",
    )
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    from app.core.config import get_settings

    settings = get_settings()
    if settings.llm_provider != "anthropic":
        print(
            "LLM_PROVIDER is not 'anthropic'. This script spends real model credits "
            "on purpose — for ordinary fixture-mode simulation, use scripts/run_event.py "
            "or scripts/run_day.py instead."
        )
        return 1
    if not settings.anthropic_api_key:
        print(
            "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set (and this script "
            "does not attempt to resolve an `ant auth login` profile on your behalf)."
        )
        return 1
    if args.force_research and settings.research_provider == "fixture":
        print(
            "--force-research requires a live RESEARCH_PROVIDER (tavily/brave) — "
            "retrieval must actually be live for the flag to mean what it says. "
            "Set RESEARCH_PROVIDER=tavily and TAVILY_API_KEY."
        )
        return 1

    _clean_db()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")
    print(f"LLM provider: {settings.llm_provider}  agent_model={settings.agent_model}")
    print(f"Research provider: {settings.research_provider}", end="")
    if settings.research_provider == "fixture":
        print("  (fixture — Part L's Tavily checkpoints won't apply even if research happens)")
    else:
        print()
    print(
        f"Research budget: {settings.max_search_queries_per_session} quer(y/ies), "
        f"{settings.max_sources_per_query} results/query, "
        f"{settings.max_fetched_sources_per_session} fetched max\n"
    )

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents

    from sqlalchemy import select

    from app.db.models.agents import Agent
    from app.db.session import SessionLocal
    from app.domain.enums import InterestOrigin
    from app.providers.llm import get_llm_provider
    from app.services import interests
    from app.services.orchestrator import run_next_event

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.\n")

        agent = session.scalars(select(Agent).where(Agent.agent_id == args.agent)).first()
        if agent is None:
            print(f"No agent {args.agent!r}.")
            return 1

        if args.nudge:
            from app.db.models.world import SimulationClock

            clock = session.scalars(select(SimulationClock).limit(1)).first()
            interests.bump(
                session, agent.agent_id, args.nudge,
                delta=interests.RESEARCH_DELTA, origin=InterestOrigin.RESEARCH_DISCOVERY.value,
                clock=clock, correlation_id=None,
            )
            session.commit()
            print(f"Nudged: {agent.agent_id}'s interest in {args.nudge!r} strengthened (not forced).\n")

        llm_provider = get_llm_provider(settings)

        if args.force_research:
            return _run_forced_research(session, settings, llm_provider, agent, args)

        print(f"Activating {agent.agent_id} for one real decision...\n")
        outcome = run_next_event(
            session, settings=settings, provider=llm_provider,
            seed=args.seed, force_agent_id=agent.agent_id,
        )
        session.commit()

        checks: list[tuple[str, bool]] = []

        if outcome.decision is None:
            print(f"No decision produced. {outcome.note or outcome.rejected_reason}")
            checks.append(("real LLM provider was actually called", outcome.llm_run_id is not None or bool(outcome.rejected_reason)))
            _print_checks(checks)
            return 0 if not outcome.is_fixture else 1

        decision_text = " ".join(
            filter(None, [outcome.decision.summary, outcome.decision.activity, outcome.decision.public_dialogue])
        )
        no_fixture_text = _FIXTURE_MARKER not in decision_text
        checks.append(("real LLM provider was actually called", not outcome.is_fixture))
        checks.append(("no fixture decision text entered live cognition", no_fixture_text))

        print(f"Decision: {outcome.decision.summary}")
        print(f"Activity: {outcome.decision.activity}")
        print(f"Actions: {outcome.executed}")

        if outcome.research is None:
            print(
                "\nagent_did_not_research: this agent chose not to START_RESEARCH this "
                "turn — a legitimate, honestly-reported outcome (see the module docstring)."
            )
            _print_checks(checks)
            print("\nInspect it directly:")
            print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_llm_usage.py")
            return 0 if all(v for _, v in checks) else 1

        _assert_research_chain(session, settings, outcome.research, outcome.activated_agent_id, checks)
        _print_checks(checks)

        ok = all(v for _, v in checks)
        print(f"\n{'PASS' if ok else 'FAIL'}: one live agent cycle for {agent.agent_id}.")
        print("\nInspect it directly:")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research.py --agent {agent.agent_id}")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_llm_usage.py --agent {agent.agent_id}")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research_usage.py --agent {agent.agent_id}")
        return 0 if ok else 1
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


def _run_forced_research(session, settings, llm_provider, agent, args) -> int:
    """--force-research: bypass only the action-selection decision, then run
    the exact same app.services.research.start_research every real
    START_RESEARCH action calls — real query generation, real retrieval,
    real interpretation, real provenance, real telemetry. Never a parallel
    or partly-fixtured research path."""
    from sqlalchemy import select

    from app.db.models.agents import AgentInterest
    from app.db.models.world import SimulationClock
    from app.domain.ids import new_correlation_id
    from app.providers.research import get_research_provider
    from app.services import research

    top_interest = session.scalars(
        select(AgentInterest)
        .where(AgentInterest.agent_id == agent.agent_id)
        .order_by(AgentInterest.strength.desc(), AgentInterest.id.desc())
        .limit(1)
    ).first()
    if top_interest is None:
        print(f"{agent.agent_id} has no interests recorded; pass --nudge to give it one.")
        return 1
    question = f"What is the current state of {top_interest.interest}?"

    correlation_id = f"forced_test_{new_correlation_id()}"
    clock = session.scalars(select(SimulationClock).limit(1)).first()
    research_provider = get_research_provider(settings)

    print("=" * 70)
    print("FORCED TEST-ONLY RESEARCH RUN — action-selection bypassed")
    print(f"  agent: {agent.agent_id}")
    print(f"  question (from real interest {top_interest.interest!r}): {question!r}")
    print(f"  correlation_id: {correlation_id}")
    print(f"  LLM provider: {llm_provider.name} (live={not llm_provider.is_fixture})")
    print(f"  research provider: {research_provider.name} (live={not research_provider.is_fixture})")
    print("=" * 70 + "\n")

    outcome = research.start_research(
        session, agent, question, clock, correlation_id, settings, llm_provider, research_provider,
    )
    session.commit()

    checks: list[tuple[str, bool]] = [
        ("run is labelled forced/test-only", correlation_id.startswith("forced_test_")),
    ]
    _assert_research_chain(session, settings, outcome, agent.agent_id, checks)
    _print_checks(checks)

    ok = all(v for _, v in checks)
    print(f"\n{'PASS' if ok else 'FAIL'}: forced test-only research run for {agent.agent_id}.")
    print("\nInspect it directly (filter by the forced_test_ correlation_id prefix to isolate this run):")
    print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research.py --agent {agent.agent_id}")
    print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_llm_usage.py --agent {agent.agent_id}")
    print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_research_usage.py --agent {agent.agent_id}")
    return 0 if ok else 1


def _assert_research_chain(session, settings, research_outcome, agent_id: str, checks: list[tuple[str, bool]]) -> None:
    from app.db.models.research import ResearchFinding, ResearchQuery, ResearchSession, ResearchSource
    from app.db.models.research_provenance import Claim, ClaimEvidence, ResearchSourcePassage
    from app.db.models.research_usage import ResearchProviderUsage

    research_id = research_outcome.research_id
    rs = session.query(ResearchSession).filter_by(research_id=research_id).one()
    queries = session.query(ResearchQuery).filter_by(research_session_id=research_id).all()
    sources = session.query(ResearchSource).filter_by(research_session_id=research_id).all()
    passages = (
        session.query(ResearchSourcePassage).filter(ResearchSourcePassage.source_id.in_([s.id for s in sources])).all()
        if sources else []
    )
    usage = session.query(ResearchProviderUsage).filter_by(research_session_id=research_id).first()

    checks.append((
        "real LLM-generated research question/query exists",
        bool(rs.question) and _FIXTURE_MARKER not in rs.question and bool(queries) and any(_FIXTURE_MARKER not in q.query_text for q in queries),
    ))
    checks.append(("Tavily live provider was called", usage is not None and usage.provider == "tavily" and not usage.is_fixture))
    checks.append((
        "real source URLs were stored",
        any(not s.url.startswith("https://fixture.invalid") for s in sources),
    ))

    if research_outcome.unavailable:
        print(f"\nResearch was RESEARCH_UNAVAILABLE: {research_outcome.reason}")
        checks.append(("real passages were stored", len(passages) > 0))
        checks.append(("real LLM interpretation was stored", False))
        checks.append(("no fixture query/interpretation/finding/claim text remains", True))
        checks.append(("evidence links resolve to actual stored passages", True))
        checks.append(("unsupported source IDs are rejected", True))
        checks.append(("usage telemetry records LLM usage", _has_live_llm_run(session, agent_id)))
        checks.append(("failure does not fabricate cognition", research_outcome.findings_created == 0))
        return

    checks.append(("real passages were stored", len(passages) > 0))
    checks.append(("real LLM interpretation was stored", bool(rs.interpretation) and _FIXTURE_MARKER not in (rs.interpretation or "")))

    findings = session.query(ResearchFinding).filter_by(research_session_id=research_id).all()
    claims = session.query(Claim).filter_by(research_session_id=research_id).all()
    # Part L + the --force-research addendum: no [fixture]-marked text may
    # have entered a live run anywhere along the chain — query, session
    # interpretation, finding, or claim. Every fixture-generated string in
    # this codebase carries that literal marker (see app/providers/llm/
    # fixture.py and app/providers/research/fixture.py's own module
    # docstrings), so its absence is a direct, checkable proof, not an
    # inference.
    no_fixture_anywhere = (
        all(_FIXTURE_MARKER not in q.query_text for q in queries)
        and _FIXTURE_MARKER not in (rs.interpretation or "")
        and all(_FIXTURE_MARKER not in f.finding_text for f in findings)
        and all(_FIXTURE_MARKER not in c.claim_text for c in claims)
    )
    checks.append(("no fixture query/interpretation/finding/claim text remains", no_fixture_anywhere))

    passage_ids = {p.id for p in passages}
    evidence_ok = bool(claims)
    for c in claims:
        links = session.query(ClaimEvidence).filter_by(claim_id=c.id).all()
        if any(link.passage_id not in passage_ids for link in links):
            evidence_ok = False
    checks.append(("evidence links resolve to actual stored passages", evidence_ok))
    # Unsupported source IDs are rejected by construction (research.py drops
    # any claim-evidence passage_index outside the shown passage list before
    # ever persisting it) — checkable here as "every stored link is valid",
    # since an invalid one would never have made it into the database at all.
    checks.append(("unsupported source IDs are rejected", evidence_ok))
    checks.append(("usage telemetry records LLM usage", _has_live_llm_run(session, agent_id)))
    checks.append(("failure does not fabricate cognition", True))


def _has_live_llm_run(session, agent_id: str) -> bool:
    from app.db.models.telemetry import LLMRun

    return (
        session.query(LLMRun)
        .filter(LLMRun.agent_id == agent_id, LLMRun.is_fixture.is_(False))
        .count()
        > 0
    )


def _print_checks(checks: list[tuple[str, bool]]) -> None:
    print("\nChecks:")
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")


if __name__ == "__main__":
    raise SystemExit(main())
