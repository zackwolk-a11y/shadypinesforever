"""FastAPI application skeleton.

Phase 1 deliberately exposes nothing but a health check. Agent logic, research
execution and the founder API arrive in later sections of the build bible; this
module exists so the app boots against the schema.
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.core.config import get_database_url

app = FastAPI(
    title="The Internal Village",
    description="Phase 1 — The Research Clubhouse. Persistence layer only.",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 as long as the app is up."""
    return {"status": "ok", "phase": "1", "database_url": get_database_url()}
