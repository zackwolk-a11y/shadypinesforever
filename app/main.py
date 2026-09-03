"""FastAPI application skeleton.

Phase 1 deliberately exposes nothing but a health check. Agent logic, research
execution and the founder API arrive in later sections of the build bible; this
module exists so the app boots against the schema.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_database_url, get_settings
from app.db.models.world import SimulationClock
from app.db.session import get_session
from app.providers.llm import get_llm_provider
from app.services import clock as clock_service
from app.services import daily_synthesis
from app.services.orchestrator import run_next_event
from app.web.api import router as fishbowl_api_router
from app.web.control import router as fishbowl_control_router
from app.web.pages import router as fishbowl_pages_router

app = FastAPI(
    title="The Internal Village",
    description="Phase 1 — The Research Clubhouse.",
    version=__version__,
)

# The Fishbowl (Packet 12) — a read-only observer UI plus five explicit
# Founder control actions, all layered on the existing FastAPI app. See
# app/web/__init__.py for why opening it can never itself mutate the Village.
app.mount(
    "/fishbowl/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="fishbowl-static",
)
app.include_router(fishbowl_pages_router)
app.include_router(fishbowl_api_router)
app.include_router(fishbowl_control_router)


@app.on_event("startup")
def _print_startup_banner() -> None:
    """Absolute DB path and provider mode, printed the instant the server
    boots — not just on a /health request. Built after a real incident
    where a Fishbowl server silently ran against the wrong database with
    nothing in the terminal to reveal it."""
    settings = get_settings()
    print("=" * 70)
    print(f"The Internal Village — APP_ENV={settings.app_env}")
    print(f"Database: {get_database_url()}")
    print(f"LLM provider: {settings.llm_provider}  Research provider: {settings.research_provider}")
    print("=" * 70)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 as long as the app is up."""
    return {"status": "ok", "phase": "1", "database_url": get_database_url()}


@app.get("/simulation/clock")
def read_clock(session: Session = Depends(get_session)) -> dict:
    """Where the Village is in simulated time."""
    from sqlalchemy import select

    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is None:
        return {"clock": None, "note": "No simulation clock. Seed the village first."}
    return {
        "day": clock.current_day,
        "period": clock.current_period,
        "is_paused": clock.is_paused,
        "periods": list(clock_service.PERIODS),
    }


@app.post("/simulation/advance-period")
def advance_period(session: Session = Depends(get_session)) -> dict:
    """Move the clock on one period, rolling into the next day after NIGHT.

    Periods change what kinds of events are likely; they do not schedule model
    calls. Advancing by hand is the manual counterpart to run_day.py.
    """
    from sqlalchemy import select

    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is None:
        return {"advanced": False, "note": "No simulation clock. Seed the village first."}
    advance = clock_service.advance(session, clock)
    if advance.crossed_day_boundary:
        settings = get_settings()
        daily_synthesis.generate_report(
            session, advance.from_day, clock, settings, get_llm_provider(settings),
        )
    session.commit()
    return {
        "advanced": True,
        "from": {"day": advance.from_day, "period": advance.from_period},
        "to": {"day": advance.to_day, "period": advance.to_period},
        "crossed_day_boundary": advance.crossed_day_boundary,
    }


@app.post("/simulation/next-event")
def next_event(session: Session = Depends(get_session)) -> dict:
    """RUN NEXT EVENT: activate one agent and persist what it decided.

    The Village advances one event at a time. Nothing here interprets the
    decision — the orchestrator validates and executes it, and this returns the
    record of what happened.
    """
    settings = get_settings()
    provider = get_llm_provider(settings)
    outcome = run_next_event(session, settings=settings, provider=provider)
    session.commit()
    return {
        "agent_id": outcome.activated_agent_id,
        "acted": outcome.acted,
        "summary": outcome.decision.summary if outcome.decision else None,
        "activity": outcome.decision.activity if outcome.decision else None,
        "public_dialogue": outcome.decision.public_dialogue if outcome.decision else None,
        "actions": outcome.executed,
        "conversation_id": outcome.conversation_id,
        "spoke": outcome.spoke,
        "clock_advance": outcome.clock_advance,
        "rejected_reason": outcome.rejected_reason,
        "event_ids": outcome.event_ids,
        "llm_run_id": outcome.llm_run_id,
        "correlation_id": outcome.correlation_id,
        "is_fixture": outcome.is_fixture,
        "note": outcome.note,
    }
