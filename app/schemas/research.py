"""Research contracts: what a search provider returns, and what synthesis produces.

Two different boundaries share this file:

- :class:`SourceCandidate` / :class:`SearchResponse` / :class:`SourceDocument`
  are what a :class:`~app.providers.research.base.ResearchProvider` hands back.
  Nothing here is model-generated; it is what the search API actually said.
- :class:`ResearchSynthesis` is what an LLM produces *after* being shown bounded
  evidence from those sources. It never sees the open web — only what the
  research service already retrieved and persisted.

Keeping these in one module makes the boundary between "retrieved" and
"interpreted" visible at the type level, not just in prose.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import EvidenceRelation, EvidenceStrength, FindingClassification

MAX_FINDINGS_PER_SYNTHESIS = 5
MAX_CLAIMS_PER_FINDING = 5
MAX_OPEN_QUESTIONS = 5
MAX_FOLLOW_UP_QUESTIONS = 3


class SourceCandidate(BaseModel):
    """One result a search returned, before anything is fetched.

    Provider-agnostic on purpose: a Brave result and a Tavily result both
    normalise into this shape, so the research service never branches on which
    company answered.
    """

    provider: str
    provider_result_id: str | None = None
    url: str
    title: str
    domain: str | None = None
    author: str | None = None
    publication: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    source_type: str | None = None
    snippet: str | None = None


class SearchResponse(BaseModel):
    """What one search call returned."""

    provider: str
    query: str
    results: list[SourceCandidate] = Field(default_factory=list)
    is_fixture: bool = False


class SourceDocument(BaseModel):
    """The bounded, exact text actually retrieved for one source.

    ``excerpt_sha256`` is the provenance anchor: it proves which exact bytes an
    interpretation was based on, independent of whatever the page says later.
    """

    url: str
    title: str
    excerpt: str
    excerpt_sha256: str
    retrieved_at: datetime
    provider_metadata: dict = Field(default_factory=dict)
    is_fixture: bool = False


# --------------------------------------------------------------------------
# Research synthesis — the model's structured interpretation of bounded evidence
# --------------------------------------------------------------------------


class SynthesizedEvidenceLink(BaseModel):
    """One claim's relationship to one numbered passage shown in the prompt.

    ``passage_index`` is a 1-based position into the passage list the prompt
    enumerated, not a database id — the model cannot see real ids, and asking
    it to invent one would be exactly the kind of unverifiable citation this
    packet exists to prevent. The research service resolves the index back to
    a real ``research_source_passages.id`` before writing ``claim_evidence``.
    """

    model_config = {"extra": "forbid"}

    passage_index: int
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS


class SynthesizedClaim(BaseModel):
    """One atomic, independently-classified claim inside a finding."""

    model_config = {"extra": "forbid"}

    text: str
    classification: FindingClassification
    confidence: float | None = Field(default=None, description="0-100, if the model has a basis for a number.")
    evidence: list[SynthesizedEvidenceLink] = Field(default_factory=list)


class SynthesizedFinding(BaseModel):
    """One finding, decomposed into the atomic claims that support it."""

    model_config = {"extra": "forbid"}

    text: str
    classification: FindingClassification
    claims: list[SynthesizedClaim] = Field(default_factory=list)

    @field_validator("claims")
    @classmethod
    def _cap_claims(cls, value: list[SynthesizedClaim]) -> list[SynthesizedClaim]:
        if len(value) > MAX_CLAIMS_PER_FINDING:
            raise ValueError(f"at most {MAX_CLAIMS_PER_FINDING} claims per finding, got {len(value)}")
        return value


class ResearchSynthesis(BaseModel):
    """What the research model returns after reading bounded, numbered evidence.

    This is the only thing an LLM is ever asked to produce about a piece of
    research. It never searches, never fetches, and never sees a source it
    was not explicitly shown here.
    """

    model_config = {"extra": "forbid"}

    interpretation: str = Field(description="A few sentences, plain language, on what the evidence shows.")
    evidence_strength: EvidenceStrength
    confidence: float | None = Field(default=None, description="0-100, if the model has a basis for a number.")
    findings: list[SynthesizedFinding] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)

    @field_validator("findings")
    @classmethod
    def _cap_findings(cls, value: list[SynthesizedFinding]) -> list[SynthesizedFinding]:
        if len(value) > MAX_FINDINGS_PER_SYNTHESIS:
            raise ValueError(f"at most {MAX_FINDINGS_PER_SYNTHESIS} findings, got {len(value)}")
        return value

    @field_validator("open_questions")
    @classmethod
    def _cap_open_questions(cls, value: list[str]) -> list[str]:
        return value[:MAX_OPEN_QUESTIONS]

    @field_validator("follow_up_questions")
    @classmethod
    def _cap_follow_ups(cls, value: list[str]) -> list[str]:
        return value[:MAX_FOLLOW_UP_QUESTIONS]
