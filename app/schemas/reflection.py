"""What the reflection model produces (Packet 9, §15).

Mirrors the boundary :mod:`app.schemas.research` already draws for
``ResearchSynthesis``: the model is shown a small, bounded, numbered set of
the agent's own real prior experience (memories, research, beliefs,
conversations, rabbit holes, wall posts, and earlier reflections — see
:mod:`app.services.reflection`), and this is the only thing it may return
about it. It never sees anything it was not explicitly shown, and every id it
cites is validated against exactly what was shown before anything is
persisted — an id that doesn't match gets dropped, never trusted blindly
(the same discipline ``app.services.orchestrator`` already applies to every
action a live model proposes).

No chain-of-thought is requested. ``summary`` is the conclusion itself, not
a trace of how the model got there.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_SOURCE_IDS_PER_LIST = 8


class ReflectionSynthesis(BaseModel):
    """One concise, higher-level conclusion drawn from real prior experience."""

    model_config = {"extra": "forbid"}

    topic: str = Field(description="A short label for the pattern being noticed.")
    summary: str = Field(
        description="The conclusion itself, a few sentences, plain language — "
        "not a summary of what happened, but what the pattern across it means."
    )
    confidence: float | None = Field(
        default=None, description="0-100, if the agent has a real basis for a number."
    )
    open_question: str | None = Field(
        default=None, description="Something this pattern leaves genuinely unresolved, if anything."
    )
    suggested_follow_up: str | None = Field(
        default=None, description="A concrete next step this reflection suggests, if any."
    )
    supersedes_reflection_id: int | None = Field(
        default=None,
        description="A real id from YOUR EARLIER REFLECTIONS below that this one directly "
        "replaces, if any — only when this genuinely supersedes that specific earlier "
        "conclusion, not merely related to it.",
    )

    #: Real database ids the agent is drawing on, copied from what it was
    #: shown — never invented. Validated server-side against the actual
    #: candidate set before anything is persisted.
    source_memory_ids: list[int] = Field(default_factory=list)
    source_research_ids: list[str] = Field(default_factory=list)
    source_belief_ids: list[int] = Field(default_factory=list)
    source_conversation_ids: list[int] = Field(default_factory=list)
    source_rabbit_hole_ids: list[int] = Field(default_factory=list)
    source_wall_post_ids: list[int] = Field(default_factory=list)
    source_reflection_ids: list[int] = Field(default_factory=list)

    @field_validator(
        "source_memory_ids", "source_research_ids", "source_belief_ids",
        "source_conversation_ids", "source_rabbit_hole_ids", "source_wall_post_ids",
        "source_reflection_ids",
    )
    @classmethod
    def _cap(cls, value: list) -> list:
        return value[:MAX_SOURCE_IDS_PER_LIST]
