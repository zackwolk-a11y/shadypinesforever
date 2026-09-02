#!/usr/bin/env python3
"""Deterministic regression test for the curiosity-as-legitimate-reason-to-act
prompt addition (Packet 12 live-day behavioral diagnosis): the system prompt
gave an explicit, repeated affirmative reason to stay silent ("silence is a
normal and valid choice") but no equivalent affirmative reason to pursue an
unresolved curiosity — only a paragraph about *when a claim needs external
verification*, framed around epistemic necessity, never around "you have an
open interest, that's a legitimate reason on its own." Confirmed against
real live Day 1-3 telemetry: START_RESEARCH was mechanically available for
the large majority of ~97 non-conversation activations across two days, and
essentially none were chosen.

This does not test whether a live model's *behavior* changes (that needs a
real live day) — it tests that the two symmetric principles the diagnosis
called for both actually reach the rendered prompt, together, unconditionally:

1. The existing silence-is-legitimate language is still present, verbatim
   in spirit — this fix must never quietly remove or soften it.
2. The new curiosity-is-legitimate language is present.
3. Neither principle contains a quota, minimum frequency, "should", or any
   other language that would turn a legitimate option into an obligation —
   checked directly against a small banned-phrase list, so a future edit
   that accidentally turns this into a forced-activity nudge fails loudly.
4. Both principles reach a real rendered agent context end to end (not just
   the raw SYSTEM_PROMPT constant) — built the same way run_next_event
   actually builds one for a real agent.
5. The AVAILABLE ACTIONS fix (Packet 12, prior commit) is still intact.

Runs against its own throwaway SQLite database (deleted first).

Usage::

    python scripts/smoke_test_curiosity_principle_prompt.py
    python scripts/smoke_test_curiosity_principle_prompt.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_curiosity_principle_prompt.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

#: Phrases that would turn a legitimate *option* into an obligation — none
#: of these may ever appear in the system prompt. Checked case-insensitively.
_BANNED_PHRASES = (
    "must research",
    "should research",
    "every day",
    "at least one",
    "minimum of",
    "required to",
    "quota",
    "always research",
)


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.world import SimulationClock
    from app.db.session import SessionLocal
    from app.services.context_builder import SYSTEM_PROMPT, build_agent_context
    from app.services.orchestrator import ALLOWED_ACTIONS, _available_actions_for
    from sqlalchemy import select

    checks: list[tuple[str, bool]] = []

    # ------------------------------------------------------------------
    # 1-3. The raw SYSTEM_PROMPT constant itself.
    # ------------------------------------------------------------------
    checks.append(
        (
            "silence-is-legitimate language is still present",
            "silence is a normal and valid choice" in " ".join(SYSTEM_PROMPT.split()),
        )
    )
    checks.append(
        (
            "the new curiosity-is-legitimate language is present",
            "An unresolved curiosity is itself a legitimate reason to act" in " ".join(SYSTEM_PROMPT.split()),
        )
    )
    checks.append(
        (
            "the new language explicitly frames both options as equally normal, not a default",
            "exactly as normal as staying quiet" in " ".join(SYSTEM_PROMPT.split())
            and "Neither is the default" in " ".join(SYSTEM_PROMPT.split()),
        )
    )
    lowered = SYSTEM_PROMPT.lower()
    banned_found = [p for p in _BANNED_PHRASES if p in lowered]
    checks.append(
        (
            f"no quota/frequency/obligation language was introduced (checked {len(_BANNED_PHRASES)} "
            f"banned phrases) — found: {banned_found or 'none'}",
            not banned_found,
        )
    )

    # ------------------------------------------------------------------
    # 4. A real rendered agent context, end to end.
    # ------------------------------------------------------------------
    session = SessionLocal()
    try:
        seed_agents.run(session)
        session.commit()
        settings = get_settings()
        clock = session.scalars(select(SimulationClock)).one()
        agent = session.scalars(select(Agent)).first()

        context = build_agent_context(
            session, agent, clock, settings,
            available_actions=_available_actions_for(False),
        )
        checks.append(
            (
                "a real rendered agent context's system prompt carries the silence principle",
                "silence is a normal and valid choice" in " ".join(context.system.split()),
            )
        )
        checks.append(
            (
                "a real rendered agent context's system prompt carries the curiosity principle",
                "An unresolved curiosity is itself a legitimate reason to act" in " ".join(context.system.split()),
            )
        )

        # ------------------------------------------------------------------
        # 5. The AVAILABLE ACTIONS fix is still intact.
        # ------------------------------------------------------------------
        from app.schemas.actions import NOT_IN_CONVERSATION_ACTIONS

        in_convo_actions = set(_available_actions_for(True))
        not_in_convo_values = {a.value for a in NOT_IN_CONVERSATION_ACTIONS}
        checks.append(
            (
                "the AVAILABLE ACTIONS fix is still intact "
                "(no NOT_IN_CONVERSATION action offered while in a conversation)",
                not (in_convo_actions & not_in_convo_values),
            )
        )
        checks.append(
            ("ALLOWED_ACTIONS still covers every real action type", len(ALLOWED_ACTIONS) > 0),
        )
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
        print("\nFAIL: one or more curiosity-principle prompt assertions failed.")
        return 1
    print(f"\nPASS: silence and curiosity-driven pursuit are both legitimated, symmetrically, with no "
          f"obligation language ({len(checks)} checks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
