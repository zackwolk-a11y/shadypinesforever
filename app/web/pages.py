"""Server-rendered HTML pages for the Fishbowl (Packet 12, Part B/C).

Every route below does exactly what ``app/web/api.py`` does — one
``app/web/reads.py`` call, read-only — and hands the result to a Jinja2
template for the first paint; the page's own small script then takes over
with polling (``app/web/static/fishbowl.js``). No route here writes to the
database.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.web import reads

router = APIRouter(prefix="/fishbowl", tags=["fishbowl-pages"])

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _base_ctx(request: Request, session: Session, active_nav: str) -> dict:
    """Context every page needs for the masthead status strip (Part C)."""
    settings = get_settings()
    clock = reads.get_clock_status(session)
    return {
        "request": request,
        "active_nav": active_nav,
        "clock": clock,
        "providers": reads.get_provider_status(settings),
    }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "dashboard")
    settings = get_settings()
    summary = reads.get_dashboard(session, settings)
    ctx["agents"] = summary.agents if summary else []
    feed = reads.get_event_feed(session, limit=40)
    ctx["events"] = feed.events
    ctx["categories"] = feed.categories
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@router.get("/agents/{agent_id}", response_class=HTMLResponse)
def agent_detail(agent_id: str, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "dashboard")
    detail = reads.get_agent_detail(session, agent_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No agent {agent_id!r}")
    ctx["agent"] = detail
    return templates.TemplateResponse(request, "agent_detail.html", ctx)


@router.get("/conversations", response_class=HTMLResponse)
def conversations(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "conversations")
    page = reads.get_conversations(session)
    ctx["conversations"] = page.conversations
    return templates.TemplateResponse(request, "conversations.html", ctx)


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
def conversation_detail(
    conversation_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    ctx = _base_ctx(request, session, "conversations")
    detail = reads.get_conversation_detail(session, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No conversation {conversation_id}")
    ctx["conversation"] = detail
    return templates.TemplateResponse(request, "conversation_detail.html", ctx)


@router.get("/research", response_class=HTMLResponse)
def research(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "research")
    page = reads.get_research_sessions(session)
    ctx["sessions"] = page.sessions
    return templates.TemplateResponse(request, "research.html", ctx)


@router.get("/research/{research_id}", response_class=HTMLResponse)
def research_detail(research_id: str, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "research")
    detail = reads.get_research_detail(session, research_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No research session {research_id!r}")
    ctx["research"] = detail
    return templates.TemplateResponse(request, "research_detail.html", ctx)


@router.get("/wall", response_class=HTMLResponse)
def wall(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "wall")
    page = reads.get_wall(session)
    ctx["posts"] = page.posts
    return templates.TemplateResponse(request, "wall.html", ctx)


@router.get("/rabbit-holes", response_class=HTMLResponse)
def rabbit_holes(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "rabbit_holes")
    page = reads.get_rabbit_holes(session)
    ctx["rabbit_holes"] = page.rabbit_holes
    return templates.TemplateResponse(request, "rabbit_holes.html", ctx)


@router.get("/rabbit-holes/{rabbit_hole_id}", response_class=HTMLResponse)
def rabbit_hole_detail(
    rabbit_hole_id: int, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    ctx = _base_ctx(request, session, "rabbit_holes")
    detail = reads.get_rabbit_hole_detail(session, rabbit_hole_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No rabbit hole {rabbit_hole_id}")
    ctx["hole"] = detail
    return templates.TemplateResponse(request, "rabbit_hole_detail.html", ctx)


@router.get("/reports", response_class=HTMLResponse)
def reports(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "reports")
    page = reads.get_reports(session)
    ctx["reports"] = page.reports
    return templates.TemplateResponse(request, "reports.html", ctx)


@router.get("/reports/{day_number}", response_class=HTMLResponse)
def report_detail(day_number: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "reports")
    detail = reads.get_report_detail(session, day_number)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No report for day {day_number}")
    ctx["report"] = detail
    return templates.TemplateResponse(request, "report_detail.html", ctx)


@router.get("/telemetry", response_class=HTMLResponse)
def telemetry(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    ctx = _base_ctx(request, session, "telemetry")
    ctx["telemetry"] = reads.get_telemetry(session)
    return templates.TemplateResponse(request, "telemetry.html", ctx)
