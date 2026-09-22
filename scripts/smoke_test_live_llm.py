#!/usr/bin/env python3
"""Optional Level 2 check: a minimal real call to the live Anthropic
provider (Packet 11, Part K).

Deliberately NOT part of the ordinary fixture test suite — it costs real API
credits. Exits 0 with a SKIPPED message (never a failure) if
``LLM_PROVIDER`` is still ``fixture`` or ``ANTHROPIC_API_KEY`` is unset.
Makes exactly two live calls, both with tight ``max_tokens`` caps: one real
:class:`~app.schemas.actions.AgentDecision` (through the exact same
``context_builder``/``orchestrator.validate_decision`` path a real
activation uses) and one real
:class:`~app.schemas.research.SearchQueryPlan`, to prove structured output
works for more than one schema without burning further credits proving the
same thing twice.

Usage::

    export ANTHROPIC_API_KEY="..."
    export LLM_PROVIDER=anthropic
    .venv/bin/python scripts/smoke_test_live_llm.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_live_llm.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

_FIXTURE_MARKER = "[fixture]"


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
    if settings.llm_provider != "anthropic":
        return _skip("LLM_PROVIDER is not 'anthropic' (the default is 'fixture'). Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY to run this.")
    if not settings.anthropic_api_key:
        return _skip("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")

    print(f"Model: {settings.agent_model} (decision), {settings.research_model} (query plan)")
    checks: list[tuple[str, bool]] = []

    _clean_db()
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents

    from sqlalchemy import select

    from app.db.models.agents import Agent
    from app.db.models.world import SimulationClock
    from app.db.session import SessionLocal
    from app.providers.llm.anthropic import AnthropicLLMProvider
    from app.providers.llm.base import LLMError
    from app.schemas.actions import AgentDecision
    from app.schemas.research import SearchQueryPlan
    from app.services.context_builder import build_agent_context
    from app.services.orchestrator import ALLOWED_ACTIONS, DecisionRejected, validate_decision

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.\n")

        agent = session.scalars(select(Agent).where(Agent.agent_id == "agent_dex")).one()
        clock = session.scalars(select(SimulationClock).limit(1)).first()
        provider = AnthropicLLMProvider(api_key=settings.anthropic_api_key)

        # --- call 1: a real AgentDecision, through the real context/validation path ---
        context = build_agent_context(
            session, agent, clock, settings,
            available_actions=tuple(a.value for a in ALLOWED_ACTIONS),
        )
        try:
            result = provider.complete(
                system=context.system, user=context.user, model=settings.agent_model,
                purpose="agent_decision", output_type=AgentDecision,
                max_tokens=settings.max_tokens_agent_decision,
            )
        except LLMError as exc:
            print(f"\nFAIL: live AgentDecision call failed: {exc}")
            return 1

        decision: AgentDecision = result.output
        checks.append(("real LLM provider was actually called", not result.is_fixture))
        decision_text = " ".join(
            filter(None, [decision.summary, decision.activity, decision.public_dialogue])
        )
        checks.append(("no fixture text entered the live output", _FIXTURE_MARKER not in decision_text))
        checks.append(("structured decision parses", isinstance(decision, AgentDecision)))

        try:
            validate_decision(
                decision, agent=agent, present_agent_ids=context.present_agent_ids,
                in_conversation=False, session=session, clock=clock, settings=settings,
            )
            validated = True
        except DecisionRejected as exc:
            print(f"  (decision validation rejected it: {exc})")
            validated = False
        checks.append(("action validation works", validated))
        print(f"Decision: {decision.summary}")

        # --- call 2: a real SearchQueryPlan, a different schema entirely ---
        from app.services.research import QUERY_GENERATION_SYSTEM_PROMPT

        prompt = "RESEARCH QUESTION: What independent radio streaming platforms exist today?\nMAX_QUERIES: 2"
        try:
            result2 = provider.complete(
                system=QUERY_GENERATION_SYSTEM_PROMPT, user=prompt, model=settings.research_model,
                purpose="search_query_generation", output_type=SearchQueryPlan,
                max_tokens=settings.max_tokens_search_query,
            )
        except LLMError as exc:
            print(f"\nFAIL: live SearchQueryPlan call failed: {exc}")
            return 1

        plan: SearchQueryPlan = result2.output
        checks.append((
            "a real model-generated query/interpretation is produced",
            bool(plan.queries) and all(_FIXTURE_MARKER not in q for q in plan.queries),
        ))
        print(f"Queries: {plan.queries}")

        total_tokens = (
            result.usage.input_tokens + result.usage.output_tokens
            + result2.usage.input_tokens + result2.usage.output_tokens
        )
        print(f"\nTotal tokens across both calls: {total_tokens}")

        print("\nChecks:")
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

        ok = all(v for _, v in checks)
        print(f"\n{'PASS' if ok else 'FAIL'}: live LLM smoke test.")
        return 0 if ok else 1
    finally:
        session.close()
        _clean_db()


if __name__ == "__main__":
    raise SystemExit(main())
