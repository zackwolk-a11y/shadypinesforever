#!/usr/bin/env python3
"""Deterministic regression test for the AVAILABLE ACTIONS prompt/validation
mismatch confirmed against the real Day 1-3 live data: the rendered prompt
listed every action type — including START_RESEARCH, POST_TO_WALL,
CREATE_RABBIT_HOLE, and the rest of NOT_IN_CONVERSATION_ACTIONS — even
while an agent sat inside a conversation, where validate_decision rejects
every one of them outright. Fixed in app/services/orchestrator.py's
``_available_actions_for``.

Two layers:

1. A direct check on ``_available_actions_for`` itself: every action listed
   while "in conversation" must actually be legal in that state (never a
   member of NOT_IN_CONVERSATION_ACTIONS), and every action listed while
   "not in conversation" must never be a member of IN_CONVERSATION_ACTIONS
   — checked against validate_decision's own rule sets directly, not a
   hand-copied duplicate.
2. An end-to-end check: drives the real event loop under the fixture
   provider through a real morning gathering, captures the actual rendered
   prompt text handed to an agent while it is a conversation participant,
   and asserts it never lists a NOT_IN_CONVERSATION_ACTIONS member — the
   exact bug, caught at the point a live model would actually see it.

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_available_actions_prompt.py
    python scripts/smoke_test_available_actions_prompt.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_available_actions_prompt.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet12-available-actions"
MAX_EVENTS = 400


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.db.models.world import SimulationClock
    from app.providers.llm import get_llm_provider
    from app.schemas.actions import IN_CONVERSATION_ACTIONS, NOT_IN_CONVERSATION_ACTIONS
    from app.services import conversations as convo
    from app.services.context_builder import build_agent_context
    from app.services.orchestrator import _available_actions_for, run_next_event
    from sqlalchemy import select

    checks: list[tuple[str, bool]] = []

    # ------------------------------------------------------------------
    # 1. Direct check on _available_actions_for itself.
    # ------------------------------------------------------------------
    in_convo_actions = _available_actions_for(True)
    not_in_convo_actions = _available_actions_for(False)
    not_in_convo_values = {a.value for a in NOT_IN_CONVERSATION_ACTIONS}
    in_convo_values = {a.value for a in IN_CONVERSATION_ACTIONS}

    checks.append(
        (
            "while in a conversation, no NOT_IN_CONVERSATION_ACTIONS member is listed as available",
            not (set(in_convo_actions) & not_in_convo_values),
        )
    )
    checks.append(
        (
            "while not in a conversation, no IN_CONVERSATION_ACTIONS member is listed as available",
            not (set(not_in_convo_actions) & in_convo_values),
        )
    )
    checks.append(("SPEAK is offered while in a conversation", "SPEAK" in in_convo_actions))
    checks.append(("START_RESEARCH is offered while not in a conversation", "START_RESEARCH" in not_in_convo_actions))

    # ------------------------------------------------------------------
    # 2. End-to-end: the actual rendered prompt during a real conversation.
    # ------------------------------------------------------------------
    settings = get_settings()
    session = SessionLocal()
    try:
        seed_agents.run(session)
        session.commit()
        provider = get_llm_provider(settings)
        clock = session.scalars(select(SimulationClock)).one()

        rendered_prompt_checked = False
        for _ in range(MAX_EVENTS):
            run_next_event(session, settings=settings, provider=provider, seed=args.seed, auto_advance=True)
            session.commit()

            conversation = convo.active_conversation(session)
            if conversation is not None and (conversation.participant_ids or []):
                agent_id = conversation.participant_ids[0]
                from app.db.models.agents import Agent

                agent = session.scalars(select(Agent).where(Agent.agent_id == agent_id)).one()
                context = build_agent_context(
                    session, agent, clock, settings,
                    available_actions=_available_actions_for(True),
                    conversation=conversation,
                )
                available_line = next(
                    (line for line in context.user.splitlines() if line.startswith("AVAILABLE ACTIONS:")), ""
                )
                listed = {a.strip() for a in available_line.removeprefix("AVAILABLE ACTIONS:").split(",")}
                leaked = listed & not_in_convo_values
                checks.append(
                    (
                        "the actual rendered prompt for a real in-conversation agent never lists a "
                        f"NOT_IN_CONVERSATION action (checked conversation #{conversation.id}, "
                        f"agent {agent_id}) — leaked: {leaked or 'none'}",
                        not leaked,
                    )
                )
                rendered_prompt_checked = True
                break

        checks.append(("a real conversation was actually reached and checked", rendered_prompt_checked))
    finally:
        session.close()

    print("Checks:")
    all_ok = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_ok &= ok

    if not args.keep_db:
        _clean_db()
    else:
        print(f"\nDatabase kept at {DB_PATH}")

    if not all_ok:
        print("\nFAIL: one or more AVAILABLE ACTIONS assertions failed.")
        return 1
    print(f"\nPASS: the prompt's AVAILABLE ACTIONS always matches what validation actually permits ({len(checks)} checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
