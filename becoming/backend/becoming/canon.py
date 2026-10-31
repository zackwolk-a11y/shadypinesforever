"""Canonical resident and curriculum specifications: load and validate.

Canon is AUTHORED design. It is deliberately strict about honesty:

- exactly the nine founding residents, with fixed stable IDs;
- every source carries a verification status, and nothing is marked
  retrieved/verified until the research system has actually retrieved it;
- canon files may not contain event memories, relationship histories or
  development history. Those come only from executed simulation events,
  which carry real event IDs and live in the database.
- foundational identity (stable) is separated from revisable beliefs (seeds).
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from becoming import CANON_DIR

RESIDENT_IDS: tuple[str, ...] = (
    "tony", "mark", "haize", "ashley", "ralph", "bernie", "mao", "pepper", "anna",
)
FORBIDDEN_IDS = {"paisley"}
#: The older prototype's roster. Its presence in this canon would mean the
#: wrong roster was substituted.
LEGACY_ROSTER = {"optimisto", "vince", "questauthor", "the_alien", "sol", "roxy", "dex", "lucid"}


class SourceStatus(str, Enum):
    FOUNDER_NAMED_PENDING_MATERIALS = "founder_named_pending_materials"
    KNOWN_REFERENCE_PENDING_RETRIEVAL = "known_reference_pending_retrieval"
    # Only the research pipeline may produce the next status, with a
    # retrieval record. Canon files are not allowed to claim it (see below).
    RETRIEVED_VERIFIED = "retrieved_verified"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Inspiration(Strict):
    summary: str
    primary: list[str] = Field(min_length=1)
    secondary: list[str] = []
    attribution_notes: str


class Source(Strict):
    id: str
    label: str
    kind: str
    status: SourceStatus
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def canon_cannot_claim_verified(cls, v: SourceStatus) -> SourceStatus:
        if v is SourceStatus.RETRIEVED_VERIFIED:
            raise ValueError("canon may not mark a source retrieved_verified; only the research pipeline can")
        return v


class SocialPreferences(Strict):
    solitude_need: float = Field(ge=0, le=1)
    preferred_group_size: Literal["pair", "small_group", "medium_group", "large_group"]
    social_energy: Literal["low", "medium", "high"]
    favorite_locations: list[str] = Field(min_length=1)


class FoundationalIdentity(Strict):
    background_assumptions: list[str] = Field(min_length=2)
    central_interests: list[str] = Field(min_length=4)
    philosophical_commitments: list[str] = Field(min_length=2)
    recurring_tension: str
    conversational_habits: list[str] = Field(min_length=3)
    preferred_discussion_styles: list[str] = Field(min_length=1)
    avoided_discussion_styles: list[str] = Field(min_length=1)
    personal_boundaries: list[str] = Field(min_length=1)
    social_preferences: SocialPreferences


class SeedBelief(Strict):
    id: str
    statement: str
    confidence: float = Field(ge=0, le=1)


class Revisable(Strict):
    beliefs: list[SeedBelief] = Field(min_length=3)
    uncertainties: list[str] = Field(min_length=2)
    exploring_questions: list[str] = Field(min_length=3)
    research_interests: list[str] = Field(min_length=3)


class RelationshipSeed(Strict):
    with_: str = Field(alias="with")
    disposition: Literal["affinity", "productive_tension", "curiosity", "neutral"]
    note: str


class Home(Strict):
    location_id: str
    description: str
    contents: list[str] = Field(min_length=3)
    public_areas: list[str]
    private_areas: list[str]


class ResidentSpec(Strict):
    schema_version: Literal[1]
    id: str
    number: int = Field(ge=1, le=9)
    display_name: str
    title: str
    pronouns: str
    inspiration: Inspiration
    sources: list[Source] = Field(min_length=1)
    foundational_identity: FoundationalIdentity
    revisable: Revisable
    relationship_seeds: list[RelationshipSeed] = []
    home: Home
    guardrails: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids(self) -> "ResidentSpec":
        if self.id in FORBIDDEN_IDS or self.id in LEGACY_ROSTER:
            raise ValueError(f"{self.id!r} is not a founding resident of this village")
        if self.id not in RESIDENT_IDS:
            raise ValueError(f"unknown resident id {self.id!r}")
        if self.home.location_id != f"home_{self.id}":
            raise ValueError(f"{self.id}: home must be home_{self.id}")
        for b in self.revisable.beliefs:
            if not b.id.startswith(f"{self.id}_"):
                raise ValueError(f"{self.id}: belief id {b.id} must be prefixed with the resident id")
        for r in self.relationship_seeds:
            if r.with_ == self.id or r.with_ not in RESIDENT_IDS:
                raise ValueError(f"{self.id}: invalid relationship seed target {r.with_!r}")
        return self


class Thread(Strict):
    id: str
    prompt: str
    natural_voices: list[str]
    suggested_locations: list[str]


class GreatQuestion(Strict):
    id: str
    title: str
    facets: list[str] = Field(min_length=4)
    threads: list[Thread] = Field(min_length=2)
    evidence_kinds_expected: list[str]
    honesty_note: str | None = None


class Curriculum(Strict):
    schema_version: Literal[1]
    provenance: str
    questions: list[GreatQuestion] = Field(min_length=10, max_length=10)


def load_residents(directory: Path = CANON_DIR / "residents") -> dict[str, ResidentSpec]:
    specs: dict[str, ResidentSpec] = {}
    for f in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        spec = ResidentSpec.model_validate(data)
        if spec.id in specs:
            raise ValueError(f"duplicate resident id {spec.id}")
        specs[spec.id] = spec
    if set(specs) != set(RESIDENT_IDS):
        raise ValueError(f"canon roster {sorted(specs)} != founding nine {sorted(RESIDENT_IDS)}")
    numbers = sorted(s.number for s in specs.values())
    if numbers != list(range(1, 10)):
        raise ValueError(f"resident numbers must be 1..9, got {numbers}")
    return specs


def load_curriculum(path: Path = CANON_DIR / "curriculum" / "great_questions.yaml") -> Curriculum:
    cur = Curriculum.model_validate(yaml.safe_load(path.read_text()))
    for q in cur.questions:
        for t in q.threads:
            bad = set(t.natural_voices) - set(RESIDENT_IDS)
            if bad:
                raise ValueError(f"{t.id}: unknown residents {bad}")
    return cur


def load_style_paragraph(path: Path = CANON_DIR / "style" / "canonical_style.txt") -> str:
    return path.read_text().strip()
