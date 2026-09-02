#!/usr/bin/env python3
"""Deterministic Packet 12 smoke test: The Fishbowl.

Drives a few real simulated days under the fixture providers so every kind
of record the Fishbowl displays actually exists (conversations, research
with provenance, wall posts, rabbit holes, a Founder report, LLM/research
telemetry), then exercises the FastAPI app exactly the way a browser would
— through Starlette's TestClient, real HTTP-shaped requests against
``app.main.app`` — and asserts every one of Part R's checkpoints.

Runs against its own throwaway SQLite database (deleted first, so it never
touches village.db), the same convention every other smoke_test_*.py in this
directory uses.

Usage::

    python scripts/test_fishbowl.py
    python scripts/test_fishbowl.py --keep-db   # inspect afterward
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_fishbowl.db"

# Must be set before anything under app/ is imported — the engine and every
# Settings snapshot are built from this at call time.
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet12-smoke"


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--days", type=int, default=6, help="fixture days to seed the Fishbowl with")
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents  # scripts/seed_agents.py

    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.events import Event
    from app.db.models.rabbit_holes import RabbitHole
    from app.db.models.reports import DailyReport
    from app.db.models.research import ResearchSession
    from app.db.models.telemetry import LLMRun
    from app.db.models.research_usage import ResearchProviderUsage
    from app.db.session import SessionLocal
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event
    from sqlalchemy import func, select

    settings = get_settings()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")
    if not settings.uses_fixture_llm or not settings.uses_fixture_research:
        print("This smoke test requires the fixture providers on both sides.")
        return 1

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.")

        provider = get_llm_provider(settings)
        print(f"Driving {args.days} fixture day(s) (seed={args.seed!r}) to populate real data...")
        for _ in range(args.days):
            from app.db.models.world import SimulationClock

            clock = session.scalars(select(SimulationClock).limit(1)).one()
            start_day = clock.current_day
            for _ in range(400):
                outcome = run_next_event(
                    session, settings=settings, provider=provider, seed=args.seed, auto_advance=True,
                )
                session.commit()
                if outcome.clock_advance:
                    session.refresh(clock)
                    if clock.current_day != start_day:
                        break

        research_count = session.scalar(select(func.count(ResearchSession.id))) or 0
        rabbit_hole_count = session.scalar(select(func.count(RabbitHole.id))) or 0
        report_count = session.scalar(select(func.count(DailyReport.id))) or 0
        llm_run_count_before = session.scalar(select(func.count(LLMRun.id))) or 0
        print(
            f"  research sessions: {research_count}, rabbit holes: {rabbit_hole_count}, "
            f"reports: {report_count}, llm_runs: {llm_run_count_before}\n"
        )

        # --------------------------------------------------------------
        # Now exercise the actual FastAPI app, the way a browser would.
        # --------------------------------------------------------------
        from starlette.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        checks: list[tuple[str, bool]] = []

        # ---- 1. Dashboard loads, all eight agents appear ------------------
        r = client.get("/fishbowl/")
        checks.append(("dashboard page loads (200)", r.status_code == 200))
        agent_ids = list(session.scalars(select(Agent.agent_id)))
        checks.append(("eight agents seeded", len(agent_ids) == 8))
        dash = client.get("/fishbowl/api/dashboard").json()
        checks.append(("dashboard API returns all eight agents", len(dash["agents"]) == 8))
        checks.append(
            ("every seeded agent_id appears on the dashboard",
             {a["agent_id"] for a in dash["agents"]} == set(agent_ids)),
        )

        # ---- 2. Event feed reads real event rows --------------------------
        feed = client.get("/fishbowl/api/events?limit=20").json()
        checks.append(("event feed returns events", len(feed["events"]) > 0))
        feed_ids = {e["id"] for e in feed["events"]}
        real_ids_matching = set(session.scalars(select(Event.id).where(Event.id.in_(feed_ids))))
        checks.append(("every feed event id is a real row in `events`", feed_ids == real_ids_matching))

        # ---- 3. Agent detail reads real stored data ------------------------
        sample_agent = agent_ids[0]
        detail = client.get(f"/fishbowl/api/agents/{sample_agent}").json()
        checks.append(("agent detail returns the requested agent_id", detail["agent_id"] == sample_agent))
        from app.db.models.agents import Agent as AgentModel

        real_agent = session.scalars(select(AgentModel).where(AgentModel.agent_id == sample_agent)).one()
        checks.append(("agent detail identity matches the real seeded row", detail["identity"] == real_agent.identity))
        r = client.get(f"/fishbowl/agents/{sample_agent}")
        checks.append(("agent detail page loads (200)", r.status_code == 200))

        # ---- 4. Research provenance renders from real fixture records -----
        checks.append(("at least one research session exists to test against", research_count > 0))
        if research_count > 0:
            rid = session.scalars(select(ResearchSession.research_id).limit(1)).first()
            rd = client.get(f"/fishbowl/api/research/{rid}").json()
            checks.append(("research detail question matches a real row", bool(rd["question"])))
            checks.append(
                ("research provenance chain has at least one query, source, or finding",
                 bool(rd["queries"] or rd["sources"] or rd["findings"])),
            )
            r = client.get(f"/fishbowl/research/{rid}")
            checks.append(("research detail page loads (200)", r.status_code == 200))
        r = client.get("/fishbowl/research")
        checks.append(("research list page loads (200)", r.status_code == 200))

        # ---- 5. Research Wall renders ---------------------------------------
        r = client.get("/fishbowl/wall")
        checks.append(("Research Wall page loads (200)", r.status_code == 200))
        wall_api = client.get("/fishbowl/api/wall").json()
        checks.append(("Research Wall API returns a list", isinstance(wall_api["posts"], list)))

        # ---- 6. Rabbit Holes render -----------------------------------------
        r = client.get("/fishbowl/rabbit-holes")
        checks.append(("Rabbit Holes page loads (200)", r.status_code == 200))
        if rabbit_hole_count > 0:
            hid = session.scalars(select(RabbitHole.id).limit(1)).first()
            r = client.get(f"/fishbowl/rabbit-holes/{hid}")
            checks.append(("Rabbit Hole detail page loads (200)", r.status_code == 200))
            rh_api = client.get(f"/fishbowl/api/rabbit-holes/{hid}").json()
            checks.append(("Rabbit Hole detail has a real title", bool(rh_api["title"])))

        # ---- 7. Founder Report renders --------------------------------------
        checks.append(("at least one Founder report was generated", report_count > 0))
        if report_count > 0:
            day = session.scalars(select(DailyReport.day_number).limit(1)).first()
            r = client.get(f"/fishbowl/reports/{day}")
            checks.append(("Founder report detail page loads (200)", r.status_code == 200))
            rep_api = client.get(f"/fishbowl/api/reports/{day}").json()
            checks.append(("Founder report summary_text is non-empty", bool(rep_api["summary_text"])))
        r = client.get("/fishbowl/reports")
        checks.append(("Founder reports list page loads (200)", r.status_code == 200))

        # ---- 8. Usage telemetry renders --------------------------------------
        tel = client.get("/fishbowl/api/telemetry").json()
        checks.append(("telemetry shows LLM calls", tel["llm_total_calls"] > 0))
        checks.append(
            ("telemetry LLM total calls matches the real llm_runs table",
             tel["llm_total_calls"] == llm_run_count_before),
        )
        r = client.get("/fishbowl/telemetry")
        checks.append(("telemetry page loads (200)", r.status_code == 200))

        # ---- 9. Fixture/live indicators are correct --------------------------
        checks.append(("dashboard reports LLM provider as fixture", dash["providers"]["llm_is_live"] is False))
        checks.append(("dashboard reports research provider as fixture", dash["providers"]["research_is_live"] is False))
        checks.append(
            ("every recent LLM run is flagged is_fixture", all(run["is_fixture"] for run in tel["recent_llm_runs"])),
        )

        # ---- 10/11. Read-only polling never touches a provider ----------------
        # app/web/reads.py, api.py, pages.py must never import a provider
        # module at all — checked structurally (not just "count didn't move",
        # which a lazy import could still satisfy).
        import inspect

        import app.web.api as fb_api
        import app.web.pages as fb_pages
        import app.web.reads as fb_reads

        def _imports_a_provider(module) -> bool:
            """Parses the module's actual import statements (via ast) rather
            than substring-matching the raw source — a docstring is allowed
            to *mention* app.providers.llm/research while explaining why the
            module doesn't import it; only a real import statement counts."""
            import ast

            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name.startswith("app.providers.") for alias in node.names):
                        return True
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("app.providers."):
                        return True
            return False

        checks.append(
            ("app/web/reads.py never imports a provider module", not _imports_a_provider(fb_reads)),
        )
        checks.append(
            ("app/web/api.py never imports a provider module", not _imports_a_provider(fb_api)),
        )
        checks.append(
            ("app/web/pages.py never imports a provider module", not _imports_a_provider(fb_pages)),
        )

        llm_before = session.scalar(select(func.count(LLMRun.id))) or 0
        research_before = session.scalar(select(func.count(ResearchProviderUsage.id))) or 0
        for _ in range(3):
            client.get("/fishbowl/")
            client.get("/fishbowl/api/dashboard")
            client.get("/fishbowl/api/events")
            client.get("/fishbowl/api/telemetry")
            client.get("/fishbowl/research")
            client.get("/fishbowl/wall")
        session.expire_all()
        llm_after = session.scalar(select(func.count(LLMRun.id))) or 0
        research_after = session.scalar(select(func.count(ResearchProviderUsage.id))) or 0
        checks.append(("repeated read-only polling creates zero new llm_runs rows", llm_after == llm_before))
        checks.append(
            ("repeated read-only polling creates zero new research_provider_usage rows",
             research_after == research_before),
        )

        # ---- 12. Control endpoints invoke existing simulation boundaries ------
        event_count_before_control = session.scalar(select(func.count(Event.id))) or 0
        cr = client.post("/fishbowl/api/control/next-event")
        checks.append(("next-event control returns 200", cr.status_code == 200))
        session.expire_all()
        event_count_after_control = session.scalar(select(func.count(Event.id))) or 0
        checks.append(
            ("next-event control actually advanced the real event log",
             event_count_after_control > event_count_before_control),
        )
        pr = client.post("/fishbowl/api/control/pause")
        checks.append(("pause control returns 200 and reports paused", pr.status_code == 200 and pr.json()["is_paused"] is True))
        rr = client.post("/fishbowl/api/control/resume")
        checks.append(("resume control returns 200 and reports resumed", rr.status_code == 200 and rr.json()["is_paused"] is False))
        fm = client.post(
            "/fishbowl/api/control/founder-message",
            json={"content": "Testing the Fishbowl.", "target_agent_id": None},
        )
        checks.append(("founder-message control returns 200", fm.status_code == 200))
        from app.db.models.reports import FounderMessage

        checks.append(
            ("founder-message control inserted a real FounderMessage row",
             session.scalars(
                 select(FounderMessage).where(FounderMessage.content == "Testing the Fishbowl.")
             ).first() is not None),
        )

        # ---- 13. Duplicate control submission protection ------------------------
        results: list[int] = []

        def _hit():
            results.append(client.post("/fishbowl/api/control/run-period").status_code)

        threads = [threading.Thread(target=_hit) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        checks.append(("concurrent control submissions: exactly one succeeds (200)", results.count(200) == 1))
        checks.append(
            ("concurrent control submissions: the rest are rejected (409)", results.count(409) == len(results) - 1),
        )

        # ---- 14. Responsive HTML contains required viewport metadata -----------
        pages_to_check = ["/fishbowl/", "/fishbowl/wall", "/fishbowl/rabbit-holes", "/fishbowl/reports", "/fishbowl/telemetry"]
        checks.append(
            ("every page carries the responsive viewport meta tag",
             all('name="viewport"' in client.get(p).text for p in pages_to_check)),
        )

        # ---- Bonus: LIVE-mode confirmation gate on RUN DAY ------------------
        os.environ["LLM_PROVIDER"] = "anthropic"
        try:
            live_rd = client.post("/fishbowl/api/control/run-day")
            checks.append(
                ("RUN DAY in LIVE mode without confirmation is refused (409)", live_rd.status_code == 409),
            )
        finally:
            os.environ["LLM_PROVIDER"] = "fixture"

        print("Fishbowl checks:")
        all_ok = True
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
            all_ok &= ok

        if not all_ok:
            print("\nFAIL: one or more Fishbowl assertions failed. See above.")
            return 1

        print(f"\nPASS: The Fishbowl ({len(checks)} checks) renders real data end to end and never mutates on read.")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())
