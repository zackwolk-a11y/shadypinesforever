"""Founder control endpoints (Packet 12, Part K).

Every mutation here goes straight through the exact same engine boundary
every other caller of this codebase already uses — ``run_next_event``,
``clock.advance``, ``daily_synthesis.generate_report`` — the same three
functions ``scripts/run_event.py``/``run_day.py`` and ``app/main.py`` call.
Nothing in this module reimplements simulation logic or writes to a table
the orchestrator doesn't already write to; PAUSE/RESUME are the one
exception, and they only flip the same ``SimulationClock.is_paused`` flag
``run_next_event`` already reads and honours.

A single in-process lock serializes every control action (Part K: "prevent
accidental double-submission"). SQLite already serializes writes at the
database level; this lock exists so a second click while RUN DAY is mid-loop
gets a clean, immediate 409 instead of queueing behind a lock for however
long RUN DAY takes, or racing the same clock row.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.reports import FounderMessage
from app.db.models.world import SimulationClock
from app.db.session import get_session
from app.providers.llm import get_llm_provider
from app.services.orchestrator import run_next_event

router = APIRouter(prefix="/fishbowl/api/control", tags=["fishbowl-control"])

#: A ceiling on how many single-agent activations RUN PERIOD / RUN DAY will
#: drive through before giving up and reporting a partial result — the same
#: safety ceiling scripts/run_day.py already enforces (Part K), never an
#: unbounded loop from a browser click.
_MAX_EVENTS_PER_PERIOD = 100
_MAX_EVENTS_PER_DAY = 400

_control_lock = threading.Lock()


class ControlResult(BaseModel):
    action: str
    ok: bool
    message: str
    events_run: int = 0
    day: int | None = None
    period: str | None = None
    is_paused: bool | None = None


def _get_clock(session: Session) -> SimulationClock:
    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is None:
        raise HTTPException(status_code=409, detail="No simulation clock. Seed the village first.")
    return clock


def _guard():
    """Non-blocking acquire — a second concurrent control call fails fast
    rather than silently queuing behind an in-flight one (Part K)."""
    if not _control_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A simulation control action is already in progress. Try again in a moment.",
        )


@router.post("/next-event", response_model=ControlResult)
def next_event(session: Session = Depends(get_session)) -> ControlResult:
    _guard()
    try:
        settings = get_settings()
        provider = get_llm_provider(settings)
        outcome = run_next_event(session, settings=settings, provider=provider)
        session.commit()
        clock = _get_clock(session)
        if outcome.note and not outcome.acted:
            return ControlResult(
                action="next-event", ok=True, message=outcome.note,
                day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
            )
        who = outcome.activated_agent_id or "no one"
        summary = outcome.decision.summary if outcome.decision else (outcome.rejected_reason or "no action")
        return ControlResult(
            action="next-event", ok=True, message=f"{who}: {summary}", events_run=1,
            day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
        )
    finally:
        _control_lock.release()


@router.post("/run-period", response_model=ControlResult)
def run_period(session: Session = Depends(get_session)) -> ControlResult:
    _guard()
    try:
        settings = get_settings()
        provider = get_llm_provider(settings)
        clock = _get_clock(session)
        if clock.is_paused:
            return ControlResult(
                action="run-period", ok=False, message="Simulation is paused.",
                day=clock.current_day, period=clock.current_period, is_paused=True,
            )
        start_period = clock.current_period
        ran = 0
        for _ in range(_MAX_EVENTS_PER_PERIOD):
            outcome = run_next_event(session, settings=settings, provider=provider, auto_advance=True)
            session.commit()
            if outcome.clock_advance:
                session.refresh(clock)
                break
            if outcome.acted:
                ran += 1
        else:
            return ControlResult(
                action="run-period", ok=True,
                message=f"Hit the {_MAX_EVENTS_PER_PERIOD}-event ceiling before the period ended.",
                events_run=ran, day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
            )
        return ControlResult(
            action="run-period", ok=True,
            message=f"Ran {ran} action(s); day {clock.current_day} moved from {start_period} to {clock.current_period}.",
            events_run=ran, day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
        )
    finally:
        _control_lock.release()


@router.post("/run-day", response_model=ControlResult)
def run_day(confirmed: bool = False, session: Session = Depends(get_session)) -> ControlResult:
    _guard()
    try:
        settings = get_settings()
        is_live = not settings.uses_fixture_llm or not settings.uses_fixture_research
        if is_live and not confirmed:
            raise HTTPException(
                status_code=409,
                detail=(
                    "RUN DAY is LIVE (real LLM/research provider) and may incur real API "
                    "usage. Resubmit with confirmed=true to proceed."
                ),
            )
        provider = get_llm_provider(settings)
        clock = _get_clock(session)
        if clock.is_paused:
            return ControlResult(
                action="run-day", ok=False, message="Simulation is paused.",
                day=clock.current_day, period=clock.current_period, is_paused=True,
            )
        start_day = clock.current_day
        ran = 0
        for _ in range(_MAX_EVENTS_PER_DAY):
            outcome = run_next_event(session, settings=settings, provider=provider, auto_advance=True)
            session.commit()
            if outcome.clock_advance:
                session.refresh(clock)
                if clock.current_day != start_day:
                    break
                continue
            if outcome.acted:
                ran += 1
        else:
            return ControlResult(
                action="run-day", ok=True,
                message=f"Hit the {_MAX_EVENTS_PER_DAY}-event ceiling before day {start_day} ended.",
                events_run=ran, day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
            )
        return ControlResult(
            action="run-day", ok=True,
            message=f"Day {start_day} complete — {ran} action(s). Now day {clock.current_day} {clock.current_period}.",
            events_run=ran, day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
        )
    finally:
        _control_lock.release()


@router.post("/pause", response_model=ControlResult)
def pause(session: Session = Depends(get_session)) -> ControlResult:
    _guard()
    try:
        clock = _get_clock(session)
        clock.is_paused = True
        session.commit()
        return ControlResult(
            action="pause", ok=True, message="Simulation paused.",
            day=clock.current_day, period=clock.current_period, is_paused=True,
        )
    finally:
        _control_lock.release()


@router.post("/resume", response_model=ControlResult)
def resume(session: Session = Depends(get_session)) -> ControlResult:
    _guard()
    try:
        clock = _get_clock(session)
        clock.is_paused = False
        session.commit()
        return ControlResult(
            action="resume", ok=True, message="Simulation resumed.",
            day=clock.current_day, period=clock.current_period, is_paused=False,
        )
    finally:
        _control_lock.release()


class FounderMessageRequest(BaseModel):
    content: str
    target_agent_id: str | None = None


@router.post("/founder-message", response_model=ControlResult)
def send_founder_message(
    body: FounderMessageRequest, session: Session = Depends(get_session)
) -> ControlResult:
    """Queue a Founder message through the existing delivery mechanism
    (``app/services/founder.py``'s ``deliver_pending``) — this only inserts
    the same row that mechanism already reads; delivery itself still happens
    on the next real activation, not here."""
    _guard()
    try:
        content = (body.content or "").strip()
        if not content:
            raise HTTPException(status_code=422, detail="content must not be empty")
        clock = _get_clock(session)
        session.add(FounderMessage(target_agent_id=body.target_agent_id, content=content))
        session.commit()
        recipient = body.target_agent_id or "everyone"
        return ControlResult(
            action="founder-message", ok=True,
            message=f"Queued for {recipient}; delivered on the next activation.",
            day=clock.current_day, period=clock.current_period, is_paused=clock.is_paused,
        )
    finally:
        _control_lock.release()
