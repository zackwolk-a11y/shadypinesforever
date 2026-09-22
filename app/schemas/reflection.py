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

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_SOURCE_IDS_PER_LIST = 8
#: Small on purpose: a reflection manages a couple of its own existing
#: questions at most, never processes its whole backlog in one pass.
MAX_QUESTION_UPDATES = 3


class QuestionUpdate(BaseModel):
    """The agent's own judgment about ONE of its existing open questions,
    shown to it this turn (see YOUR OPEN QUESTIONS in the rendered prompt).

    This is the only path back to RESOLVED/ABANDONED, or back to
    OPEN/RESEARCHING other than an explicit research link — never inferred
    from research merely having completed. ``status`` must reflect what
    actually changed intellectually, not just that time passed or research
    ran.
    """

    model_config = {"extra": "forbid"}

    question_id: int = Field(description="A real id from YOUR OPEN QUESTIONS below — never invented.")
    status: Literal["OPEN", "RESEARCHING", "RESOLVED", "ABANDONED"] = Field(
        description="What this question's status actually is now. RESOLVED means the "
        "pattern above actually answers or settles it — not merely that research on it "
        "happened. ABANDONED means you are genuinely done with it, no answer needed."
    )
    note: str | None = Field(default=None, description="Why, briefly, if it helps.")
    reformulated_question: str | None = Field(
        default=None,
        description="Only if this pattern reframes the question into a better one rather "
        "than answering it — the new phrasing. When set, status should be RESOLVED (this "
        "exact phrasing is superseded) and a new linked question is created from this text.",
    )


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
        default=None, description="Something this pattern leaves genuinely unresolved, if anything. "
        "May become a new persistent question you can return to later — entirely optional, "
        "most reflections leave this empty."
    )
    suggested_follow_up: str | None = Field(
        default=None, description="A concrete next step this reflection suggests, if any."
    )
    question_updates: list[QuestionUpdate] = Field(
        default_factory=list,
        description="Optional. Your own judgment about existing questions shown in YOUR OPEN "
        "QUESTIONS below, if this pattern actually bears on one of them. Most reflections "
        "touch none — leave this empty rather than manufacturing an update.",
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

    @field_validator("question_updates")
    @classmethod
    def _cap_question_updates(cls, value: list[QuestionUpdate]) -> list[QuestionUpdate]:
        return value[:MAX_QUESTION_UPDATES]
