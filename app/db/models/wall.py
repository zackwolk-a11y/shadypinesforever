"""The research wall — the clubhouse's shared, public surface (§13, §17)."""

from __future__ import annotations


from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import WallPostType

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK
from app.db.models.research import RESEARCH_FK


class ResearchWallPost(TimestampMixin, Base):
    """A single pinned post."""

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
