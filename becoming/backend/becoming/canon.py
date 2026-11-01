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
    #: Reviewed in the Founder's own research (checked 2026-10-17), not yet
    #: re-retrieved and hashed by this system.
    FOUNDER_RESEARCH_REVIEWED = "founder_research_reviewed"
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
    disambiguation: str | None = None


class Foundation(Strict):
    """A documented, source-attributed foundation (research layer, not fiction)."""
    statement: str
    sources: list[str] = Field(min_length=1)


class LearnsFrom(Strict):
    resident: str
    what: str


class FictionalDirection(Strict):
    """Proposed fictional choices. Not claims about any real person."""
    reasoning_style: str
    contribution: str
    tension: str
    growth_arc: str
    possible_limitations: list[str] = Field(min_length=2)
    learns_from: list[LearnsFrom] = Field(min_length=2)


class TestScene(Strict):
    """A situation worth testing in simulation: an evaluation probe, NEVER a script."""
    id: str
    situation: str
    participants: list[str] = Field(min_length=1)
    tests: str


SourceRole = Literal[
    "primary_anchor", "research_inventory", "editorial_comparison", "credits_record",
    "organizational_account", "listening_lead", "founder_design",
]


class SourceEntry(Strict):
    """One entry of canon/sources/registry.yaml.

    `editorial_comparison` sources are scholarship the Founder's research paired
    with a resident. They are NOT the real inspiration's influences or
    affiliations, and must never be presented as such.
    """
    code: str
    residents: list[str] = Field(min_length=1)
    label: str
    kind: str
    date: str | None = None
    url: str | None = None
    role: SourceRole
    notes: str | None = None
    status: SourceStatus = SourceStatus.FOUNDER_RESEARCH_REVIEWED

    @field_validator("status")
    @classmethod
    def canon_cannot_claim_verified(cls, v: SourceStatus) -> SourceStatus:
        if v is SourceStatus.RETRIEVED_VERIFIED:
            raise ValueError("canon may not mark a source retrieved_verified; only the research pipeline can")
        return v


class SourceRegistry(Strict):
    schema_version: Literal[1]
    provenance: str
    sources: list[SourceEntry]

    @model_validator(mode="after")
    def _unique(self) -> "SourceRegistry":
        codes = [s.code for s in self.sources]
        dupes = {c for c in codes if codes.count(c) > 1}
        if dupes:
            raise ValueError(f"duplicate source codes {sorted(dupes)}")
        for s in self.sources:
            bad = set(s.residents) - set(RESIDENT_IDS)
            if bad:
                raise ValueError(f"{s.code}: unknown residents {bad}")
        return self

    def by_code(self) -> dict[str, SourceEntry]:
        return {s.code: s for s in self.sources}


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


class Voice(Strict):
    """How the resident sounds. Original phrasing; never real people's words."""
    rhythm: str
    vocabulary: list[str] = Field(min_length=3)
    humor: str
    temper: str
    strong_opinions: list[str] = Field(min_length=2)
    pet_peeves: list[str] = Field(min_length=2)
    never_says: list[str] = Field(min_length=2)
    provenance: str


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
    design_provenance: list[str] = Field(min_length=1)
    inspiration: Inspiration
    source_codes: list[str] = Field(min_length=1)
    documented_foundations: list[Foundation] = Field(min_length=3)
    foundational_identity: FoundationalIdentity
    revisable: Revisable
    fictional_direction: FictionalDirection
    relationship_seeds: list[RelationshipSeed] = []
    test_scenes: list[TestScene] = Field(min_length=1)
    voice: Voice
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
        for lf in self.fictional_direction.learns_from:
            if lf.resident == self.id or lf.resident not in RESIDENT_IDS:
                raise ValueError(f"{self.id}: invalid learns_from resident {lf.resident!r}")
        for sc in self.test_scenes:
            bad = set(sc.participants) - set(RESIDENT_IDS)
            if bad:
                raise ValueError(f"{self.id}: scene {sc.id} has unknown participants {bad}")
        cited = {c for f in self.documented_foundations for c in f.sources}
        missing = cited - set(self.source_codes)
        if missing:
            raise ValueError(f"{self.id}: foundations cite codes not in source_codes: {sorted(missing)}")
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


def load_sources(path: Path = CANON_DIR / "sources" / "registry.yaml") -> SourceRegistry:
    return SourceRegistry.model_validate(yaml.safe_load(path.read_text()))


def load_residents(directory: Path = CANON_DIR / "residents",
                   registry: SourceRegistry | None = None) -> dict[str, ResidentSpec]:
    registry = registry or load_sources()
    known = registry.by_code()
    specs: dict[str, ResidentSpec] = {}
    for f in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        spec = ResidentSpec.model_validate(data)
        if spec.id in specs:
            raise ValueError(f"duplicate resident id {spec.id}")
        for code in spec.source_codes + spec.design_provenance:
            entry = known.get(code)
            if entry is None:
                raise ValueError(f"{spec.id}: source code {code} not in the source registry")
            if spec.id not in entry.residents:
                raise ValueError(f"{spec.id}: registry entry {code} is not assigned to this resident")
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


class VillageQuestion(Strict):
    id: str
    question: str
    natural_voices: list[str]
    theme: str


class EnsembleScene(Strict):
    id: str
    situation: str
    natural_voices: list[str]
    tests: str


class EnsembleCanon(Strict):
    schema_version: Literal[1]
    provenance: str
    village_questions: list[VillageQuestion]
    scenes: list[EnsembleScene]

    @model_validator(mode="after")
    def _voices(self) -> "EnsembleCanon":
        for item in [*self.village_questions, *self.scenes]:
            bad = set(item.natural_voices) - set(RESIDENT_IDS)
            if bad:
                raise ValueError(f"{item.id}: unknown residents {bad}")
        return self


def load_ensemble(path: Path = CANON_DIR / "curriculum" / "ensemble_scenes.yaml") -> EnsembleCanon:
    return EnsembleCanon.model_validate(yaml.safe_load(path.read_text()))


def load_style_paragraph(path: Path = CANON_DIR / "style" / "canonical_style.txt") -> str:
    return path.read_text().strip()


class Genre(Strict):
    id: str
    name: str
    shape: str
    typical_voices: list[str] = Field(min_length=2)
    settings: list[str] = Field(min_length=1)
    example_days: list[int] = Field(min_length=1)


class ConversationPatterns(Strict):
    """Founder-intended conversation types, derived from AUTHORED FICTION (Days 1-75).

    A style and topic reference only: never memories, never events.
    """
    schema_version: Literal[1]
    provenance: str
    founder_intent: str
    observed_craft: dict
    genres: list[Genre] = Field(min_length=8)
    signature_moves_observed: dict[str, str]
    topic_bank: list[dict]

    @model_validator(mode="after")
    def _check(self) -> "ConversationPatterns":
        if "AUTHORED FICTION" not in self.provenance:
            raise ValueError("conversation patterns must be labelled as derived from authored fiction")
        if set(self.signature_moves_observed) != set(RESIDENT_IDS):
            raise ValueError("signature moves must cover exactly the nine residents")
        days = [t["day"] for t in self.topic_bank]
        if days != list(range(1, 76)):
            raise ValueError("topic bank must hold Days 1-75 in order")
        for g in self.genres:
            bad = set(g.typical_voices) - set(RESIDENT_IDS)
            if bad:
                raise ValueError(f"{g.id}: unknown residents {bad}")
            if any(not 1 <= d <= 75 for d in g.example_days):
                raise ValueError(f"{g.id}: example day out of range")
        return self


def load_conversation_patterns(path: Path = CANON_DIR / "curriculum" / "conversation_patterns.yaml") -> ConversationPatterns:
    return ConversationPatterns.model_validate(yaml.safe_load(path.read_text()))
