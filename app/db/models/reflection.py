"""Higher-level reflections an agent forms from its own accumulated experience
(§15, Packet 9).

A reflection is not a memory and not a belief. A memory is "this happened"; a
belief is "I hold this proposition, with this confidence, on this evidence";
a reflection is "here is a pattern I think I am noticing across several of my
own experiences" — a step of abstraction above any one event, never
generated as hidden chain-of-thought, and never silently promoted to a
belief on its own (an agent may choose to act on one — research it, raise it
in conversation, form a belief from what it finds — but that is a separate,
later, ordinary action).

Every reflection keeps full provenance back to the concrete experiences that
produced it (``source_memory_ids`` etc.) — the same "never an untraceable
fact" discipline §6/§2 already hold research and beliefs to. Hierarchical
reflection (a later, higher-order reflection drawing on earlier ones) is
supported through ``source_reflection_ids`` and ``supersedes_reflection_id``,
so abstraction can build in layers without ever losing the chain back to
where it started.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK
from app.domain.enums import ReflectionStatus

REFLECTION_FK = "agent_reflections.id"


class AgentReflection(TimestampMixin, Base):
    """One agent's structured, concise conclusion drawn across several
    experiences — never raw chain-of-thought, only the conclusion itself."""

    __tablename__ = "agent_reflections"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    #: Simulated day the reflection was formed — staleness/recency for
    #: retrieval is always judged in simulated days, never wall-clock time,
    #: matching every other simulation-facing timestamp in this codebase.
    simulation_day: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    #: Mechanically computed from the trigger's accumulated significance
    #: score (app/services/reflection.py), the same "mechanism, not content"
    #: split Memory.importance already draws — never asked of the model.
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Model-supplied, like ResearchSynthesis.confidence: how sure the agent
    #: itself is in the pattern it is reporting, not something arithmetic
    #: could honestly produce.
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[ReflectionStatus] = mapped_column(
        Enum(ReflectionStatus, name="reflection_status"),
        nullable=False,
        default=ReflectionStatus.ACTIVE,
    )
    open_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_reflection_id: Mapped[int | None] = mapped_column(
        ForeignKey(REFLECTION_FK), nullable=True
    )

    source_memory_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_research_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_belief_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_conversation_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_rabbit_hole_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_wall_post_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: Beyond the spec's literal minimum-field list, but required by its own
    #: "Hierarchical Reflection" section: a later, higher-order reflection
    #: needs a real way to cite the earlier ones it built on.
    source_reflection_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    #: Retrieval bookkeeping, mirroring Memory.last_accessed_sim_day — what
    #: lets a reflection surfacing in context again after a genuine gap be
    #: told apart from routine, back-to-back re-display.
    last_accessed_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Beyond §17: a fixture-generated reflection must never be mistaken for
    #: one a live model actually formed — the same flag every other
    #: fixture-producible row in this schema already carries.
    is_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
