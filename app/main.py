"""FastAPI application skeleton.

Phase 1 deliberately exposes nothing but a health check. Agent logic, research
execution and the founder API arrive in later sections of the build bible; this
module exists so the app boots against the schema.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_database_url, get_settings
from app.db.session import get_session
from app.providers.llm import get_llm_provider
from app.services.orchestrator import run_next_event

app = FastAPI(
    title="The Internal Village",
    description="Phase 1 — The Research Clubhouse.",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 as long as the app is up."""
    return {"status": "ok", "phase": "1", "database_url": get_database_url()}


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
        "rejected_reason": outcome.rejected_reason,
        "event_ids": outcome.event_ids,
        "llm_run_id": outcome.llm_run_id,
        "correlation_id": outcome.correlation_id,
        "is_fixture": outcome.is_fixture,
        "note": outcome.note,
    }
