"""What the Founder daily report synthesis model produces (Packet 9, Part C/E).

The model never sees a raw log. By the time anything reaches it, Stage 1
(``app.services.daily_synthesis.gather_facts``) has already deterministically
pulled the day's real activity from the database and ranked it by actual
significance, never by count — "ten low-value actions should not outrank one
major discovery" is enforced there, before the model is ever involved. This
schema's job is prose and prioritization judgment over facts that are already
true and already bounded, not asserting new ones: nothing here is asked to
invent a fact, only to say which of the facts it was shown matter most and
why, in the Founder's own ten-section report shape.

Every list is capped, and every field is allowed to come back essentially
empty — a quiet day produces a short, honest report, never a padded one (§
"do not force every section to contain content").
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_ITEMS_PER_SECTION = 6


class FounderReportSynthesis(BaseModel):
    """The Founder Field Report's ten sections, in prose, grounded in the
    bounded facts shown in the prompt."""

    model_config = {"extra": "forbid"}

    what_mattered_today: str = Field(
        description="A few sentences: what actually mattered today, prioritized, not a log."
    )
    top_discoveries: list[str] = Field(default_factory=list)
    unexpected_connections: list[str] = Field(default_factory=list)
    active_rabbit_holes: list[str] = Field(default_factory=list)
    beliefs_that_changed: list[str] = Field(default_factory=list)
    character_development: list[str] = Field(default_factory=list)
    disagreements_and_uncertainties: list[str] = Field(default_factory=list)
    questions_the_village_wants_to_follow: list[str] = Field(default_factory=list)
    source_quality: str = Field(
        description="A few sentences on how well-supported today's research was overall."
    )
    one_thing_worth_your_attention: str = Field(
        description="The single most Founder-worthy item today, and why — never generic."
    )

    @field_validator(
        "top_discoveries", "unexpected_connections", "active_rabbit_holes",
        "beliefs_that_changed", "character_development",
        "disagreements_and_uncertainties", "questions_the_village_wants_to_follow",
    )
    @classmethod
    def _cap(cls, value: list[str]) -> list[str]:
        return value[:MAX_ITEMS_PER_SECTION]
