"""The research wall — the clubhouse's shared, public surface (§13, §17)."""

from __future__ import annotations


from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import WallPostType

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK
from app.db.models.research import RESEARCH_FK

WALL_FK = "research_wall.id"


class ResearchWallPost(TimestampMixin, Base):
    """A single pinned post.

    ``related_wall_post_id`` is what a CONNECTION post points at — the other
    agent's earlier post this one is drawing a line to. ``related_rabbit_hole_id``
    marks a post as being about a specific rabbit hole (a contribution note, a
    RABBIT_HOLE_SUGGESTION that named an existing hole rather than proposing a
    new one, etc). Both are nullable and independent of ``related_research_id``
    — a post can cite research, a wall post, a rabbit hole, all three, or none.
    """

    __tablename__ = "research_wall"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    post_type: Mapped[WallPostType] = mapped_column(
        Enum(WallPostType, name="wall_post_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    related_research_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), index=True, nullable=True
    )
    related_wall_post_id: Mapped[int | None] = mapped_column(
        ForeignKey(WALL_FK), index=True, nullable=True
    )
    related_rabbit_hole_id: Mapped[int | None] = mapped_column(
        ForeignKey("rabbit_holes.id"), index=True, nullable=True
    )
