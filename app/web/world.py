"""Presentation-only clubhouse route. No database writes or engine imports."""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["world"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/world/", response_class=HTMLResponse)
def world(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "world.html", {})
