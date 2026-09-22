"""JSON read endpoints for the Fishbowl (Packet 12, Part Q).

Every route here does one ``app/web/reads.py`` call and returns its typed
result. None of them writes to the database, and none of them can reach an
LLM or research provider — this module never imports ``app.providers.*`` at
all, which is what ``scripts/test_fishbowl.py`` checks holds in practice.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.web import reads
from app.web.schemas import (
    AgentDetail,
    ConversationDetail,
    ConversationListPage,
    DailyReportDetail,
    DashboardSummary,
    EventFeedPage,
    RabbitHoleDetail,
    RabbitHoleListPage,
    ReportListPage,
    ResearchListPage,
    ResearchSessionDetail,
    TelemetrySummary,
    WallPage,
)

router = APIRouter(prefix="/fishbowl/api", tags=["fishbowl"])


@router.get("/dashboard", response_model=DashboardSummary | None)
def dashboard(session: Session = Depends(get_session)) -> DashboardSummary | None:
    return reads.get_dashboard(session, get_settings())


@router.get("/events", response_model=EventFeedPage)
def events(
    agent: str | None = None,
    category: str | None = None,
    day: int | None = None,
    before_id: int | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> EventFeedPage:
    return reads.get_event_feed(
        session, agent_id=agent, category=category, day=day, before_id=before_id, limit=limit
    )


@router.get("/agents/{agent_id}", response_model=AgentDetail)
def agent_detail(agent_id: str, session: Session = Depends(get_session)) -> AgentDetail:
    detail = reads.get_agent_detail(session, agent_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No agent {agent_id!r}")
    return detail


@router.get("/conversations", response_model=ConversationListPage)
def conversations(
    agent: str | None = None, status: str | None = None, session: Session = Depends(get_session)
) -> ConversationListPage:
    return reads.get_conversations(session, agent_id=agent, status=status)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(conversation_id: int, session: Session = Depends(get_session)) -> ConversationDetail:
    detail = reads.get_conversation_detail(session, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No conversation {conversation_id}")
    return detail


@router.get("/research", response_model=ResearchListPage)
def research_sessions(
    agent: str | None = None, status: str | None = None, session: Session = Depends(get_session)
) -> ResearchListPage:
    return reads.get_research_sessions(session, agent_id=agent, status=status)


@router.get("/research/{research_id}", response_model=ResearchSessionDetail)
def research_detail(research_id: str, session: Session = Depends(get_session)) -> ResearchSessionDetail:
    detail = reads.get_research_detail(session, research_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No research session {research_id!r}")
    return detail


@router.get("/wall", response_model=WallPage)
def wall(
    agent: str | None = None,
    post_type: str | None = None,
    day: int | None = None,
    rabbit_hole: int | None = None,
    session: Session = Depends(get_session),
) -> WallPage:
    return reads.get_wall(session, agent_id=agent, post_type=post_type, day=day, rabbit_hole_id=rabbit_hole)


@router.get("/rabbit-holes", response_model=RabbitHoleListPage)
def rabbit_holes(status: str | None = None, session: Session = Depends(get_session)) -> RabbitHoleListPage:
    return reads.get_rabbit_holes(session, status=status)


@router.get("/rabbit-holes/{rabbit_hole_id}", response_model=RabbitHoleDetail)
def rabbit_hole_detail(rabbit_hole_id: int, session: Session = Depends(get_session)) -> RabbitHoleDetail:
    detail = reads.get_rabbit_hole_detail(session, rabbit_hole_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No rabbit hole {rabbit_hole_id}")
    return detail


@router.get("/reports", response_model=ReportListPage)
def reports(session: Session = Depends(get_session)) -> ReportListPage:
    return reads.get_reports(session)


@router.get("/reports/{day_number}", response_model=DailyReportDetail)
def report_detail(day_number: int, session: Session = Depends(get_session)) -> DailyReportDetail:
    detail = reads.get_report_detail(session, day_number)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No report for day {day_number}")
    return detail


@router.get("/telemetry", response_model=TelemetrySummary)
def telemetry(session: Session = Depends(get_session)) -> TelemetrySummary:
    return reads.get_telemetry(session)
