"""Read models for the Fishbowl (Packet 12, Part Q).

Every one of these is a plain Pydantic model built by ``app/web/reads.py``
from real ORM rows — the browser never sees a SQLAlchemy object, and never
sees more than what the model below declares. Nothing here is a database
model; nothing here is written to.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Shared display vocabulary — the same eight names/roles everywhere in the UI.
# ---------------------------------------------------------------------------

#: Display name for each seeded agent_id (§C's roster, in seed order).
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "agent_optimisto": "Optimisto",
    "agent_vince": "Vince",
    "agent_questauthor": "QuestAuthor",
    "agent_alien": "The Alien",
    "agent_sol": "Sol",
    "agent_roxy": "Roxy",
    "agent_dex": "Dex",
    "agent_lucid": "Lucid",
}


def display_name(agent_id: str | None) -> str:
    if agent_id is None:
        return ""
    return AGENT_DISPLAY_NAMES.get(agent_id, agent_id)


# ---------------------------------------------------------------------------
# C — Dashboard
# ---------------------------------------------------------------------------


class ProviderStatus(BaseModel):
    llm_provider: str
    llm_is_live: bool
    agent_model: str
    research_model: str
    report_model: str
    research_provider: str
    research_is_live: bool


class ClockStatus(BaseModel):
    day: int
    period: str
    is_paused: bool
    last_advanced_at: datetime | None = None
    latest_event_at: datetime | None = None


class ConversationPartner(BaseModel):
    agent_id: str
    name: str


class AgentCard(BaseModel):
    agent_id: str
    name: str
    role: str
    status: str
    current_location: str | None = None
    current_activity: str | None = None
    conversation_id: int | None = None
    conversation_partners: list[ConversationPartner] = []
    current_research_id: str | None = None
    current_research_question: str | None = None
    top_interests: list[str] = []
    recent_memory: str | None = None
    last_action_summary: str | None = None
    last_action_at: datetime | None = None


class DashboardSummary(BaseModel):
    clock: ClockStatus
    providers: ProviderStatus
    agents: list[AgentCard]


# ---------------------------------------------------------------------------
# D — Live activity feed
# ---------------------------------------------------------------------------


class FeedEvent(BaseModel):
    id: int
    event_type: str
    category: str
    agent_id: str | None = None
    agent_name: str | None = None
    headline: str
    sim_day: int | None = None
    sim_period: str | None = None
    created_at: datetime
    correlation_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict


class EventFeedPage(BaseModel):
    events: list[FeedEvent]
    categories: list[str]


# ---------------------------------------------------------------------------
# E — Agent detail
# ---------------------------------------------------------------------------


class InterestItem(BaseModel):
    id: int
    interest: str
    strength: float
    origin: str | None = None
    dormant: bool
    is_founding: bool
    last_engaged: datetime | None = None
    last_engaged_sim_day: int | None = None


class MemoryItem(BaseModel):
    id: int
    memory_type: str
    content: str
    importance: float
    confidence: float
    decay_score: float
    reinforcement_count: int
    created_sim_day: int | None = None
    last_accessed_sim_day: int | None = None
    related_agent_ids: list[str] = []
    related_research_ids: list[str] = []
    related_rabbit_hole_ids: list[int] = []
    related_conversation_ids: list[int] = []


class BeliefBasisItem(BaseModel):
    basis_type: str
    basis_id: str
    relation: str
    created_at: datetime


class BeliefItem(BaseModel):
    id: int
    statement: str
    confidence: float
    status: str
    basis: list[str] = []
    history: list[BeliefBasisItem] = []
    updated_at: datetime | None = None


class RelationshipItem(BaseModel):
    other_agent_id: str
    other_agent_name: str
    trust_score: float
    familiarity: float
    intellectual_affinity: float
    productive_disagreement_count: int
    interaction_count: int
    last_interaction: datetime | None = None
    notes: str | None = None


class ReflectionItem(BaseModel):
    id: int
    simulation_day: int
    topic: str
    summary: str
    importance: float
    confidence: float
    status: str
    open_question: str | None = None
    suggested_follow_up: str | None = None
    is_fixture: bool
    source_counts: dict[str, int] = {}


class QuestionItem(BaseModel):
    id: int
    question: str
    status: str
    salience: float
    last_engaged_sim_day: int | None = None
    origin: str
    origin_reflection_id: int | None = None
    origin_research_session_id: str | None = None
    origin_memory_id: int | None = None
    origin_conversation_id: int | None = None
    research_session_id: str | None = None
    rabbit_hole_id: int | None = None
    reformulated_from_id: int | None = None
    reformulated_into_id: int | None = None


class AgentResearchSummary(BaseModel):
    research_id: str
    question: str
    status: str
    evidence_strength: str
    confidence: float | None = None
    is_fixture: bool
    created_at: datetime
    finding_count: int


class AgentDetail(BaseModel):
    agent_id: str
    name: str
    identity: str
    voice: str
    communication_style: str | None = None
    epistemic_style: str | None = None
    current_location: str | None = None
    current_activity: str | None = None
    conversation_id: int | None = None
    conversation_partners: list[ConversationPartner] = []
    current_research_id: str | None = None
    current_research_question: str | None = None
    reflection_pressure: float
    interests: list[InterestItem]
    memories: list[MemoryItem]
    beliefs: list[BeliefItem]
    relationships: list[RelationshipItem]
    reflections: list[ReflectionItem]
    questions: list[QuestionItem]
    research_sessions: list[AgentResearchSummary]


# ---------------------------------------------------------------------------
# F — Conversations
# ---------------------------------------------------------------------------


class ConversationMessageItem(BaseModel):
    id: int
    agent_id: str
    agent_name: str
    content: str
    turn_number: int
    created_at: datetime


class ConversationSummary(BaseModel):
    id: int
    status: str
    trigger_type: str
    location: str | None = None
    current_subject: str | None = None
    initiating_reason: str | None = None
    ending_reason: str | None = None
    participants: list[ConversationPartner]
    departed_agent_ids: list[str] = []
    started_at: datetime
    ended_at: datetime | None = None
    started_sim_day: int | None = None
    started_sim_period: str | None = None
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessageItem]
    related_research_ids: list[str] = []
    related_wall_post_ids: list[int] = []
    related_rabbit_hole_ids: list[int] = []
    related_memory_ids: list[int] = []


class ConversationListPage(BaseModel):
    conversations: list[ConversationSummary]


# ---------------------------------------------------------------------------
# G — Research / provenance
# ---------------------------------------------------------------------------


class ResearchQueryItem(BaseModel):
    id: int
    query_text: str
    sequence_number: int
    executed_at: datetime


class ResearchPassageItem(BaseModel):
    id: int
    excerpt_text: str
    excerpt_sha256: str
    locator: str | None = None
    research_query_id: int | None = None


class ResearchSourceItem(BaseModel):
    id: int
    url: str
    title: str
    domain: str | None = None
    quality_tier: str
    provider: str | None = None
    provider_rank: int | None = None
    is_primary: bool | None = None
    pub_date: str | None = None
    retrieved_at: datetime
    fetched: bool
    passages: list[ResearchPassageItem] = []


class ClaimEvidenceItem(BaseModel):
    passage_id: int
    source_id: int
    relation: str
    excerpt_text: str


class ClaimItem(BaseModel):
    id: int
    claim_text: str
    classification: str
    confidence: float | None = None
    evidence: list[ClaimEvidenceItem] = []


class FindingItem(BaseModel):
    id: int
    finding_text: str
    classification: str
    claims: list[ClaimItem] = []


class ResearchSessionSummary(BaseModel):
    research_id: str
    agent_id: str
    agent_name: str
    question: str
    status: str
    evidence_strength: str
    confidence: float | None = None
    is_fixture: bool
    provider: str | None = None
    created_at: datetime
    finding_count: int
    source_count: int


class ResearchSessionDetail(ResearchSessionSummary):
    interpretation: str | None = None
    open_questions: list[str] = []
    follow_ups: list[str] = []
    related_research: list[str] = []
    queries: list[ResearchQueryItem]
    sources: list[ResearchSourceItem]
    findings: list[FindingItem]


class ResearchListPage(BaseModel):
    sessions: list[ResearchSessionSummary]


# ---------------------------------------------------------------------------
# H — Research Wall
# ---------------------------------------------------------------------------


class WallPostItem(BaseModel):
    id: int
    agent_id: str
    agent_name: str
    post_type: str
    content: str
    related_research_id: str | None = None
    related_wall_post_id: int | None = None
    related_rabbit_hole_id: int | None = None
    sim_day: int | None = None
    created_at: datetime


class WallPage(BaseModel):
    posts: list[WallPostItem]


# ---------------------------------------------------------------------------
# I — Rabbit Holes
# ---------------------------------------------------------------------------


class RabbitHoleMemberItem(BaseModel):
    agent_id: str
    agent_name: str
    joined_at: datetime
    left_at: datetime | None = None
    active: bool


class RabbitHoleTimelineItem(BaseModel):
    event_type: str
    headline: str
    agent_id: str | None = None
    agent_name: str | None = None
    created_at: datetime


class RabbitHoleSummary(BaseModel):
    id: int
    title: str
    originating_agent_id: str
    originating_agent_name: str
    status: str
    evidence_strength: str
    activity_level: float
    member_count: int
    last_activity: datetime | None = None
    last_activity_day: int | None = None


class RabbitHoleDetail(RabbitHoleSummary):
    description: str | None = None
    current_hypothesis: str | None = None
    counterarguments: list[str] = []
    open_questions: list[str] = []
    members: list[RabbitHoleMemberItem]
    related_research_ids: list[str] = []
    timeline: list[RabbitHoleTimelineItem]


class RabbitHoleListPage(BaseModel):
    rabbit_holes: list[RabbitHoleSummary]


# ---------------------------------------------------------------------------
# J — Founder Report
# ---------------------------------------------------------------------------


class ReportLink(BaseModel):
    kind: str
    text: str
    classification: str | None = None
    url: str | None = None


class DailyReportSummary(BaseModel):
    day_number: int
    title: str
    had_meaningful_activity: bool
    is_fixture: bool
    created_at: datetime


class DailyReportDetail(DailyReportSummary):
    summary_text: str
    links: list[ReportLink] = []


class ReportListPage(BaseModel):
    reports: list[DailyReportSummary]


# ---------------------------------------------------------------------------
# L — Telemetry / cost
# ---------------------------------------------------------------------------


class LLMPurposeBreakdown(BaseModel):
    purpose: str
    calls: int
    input_tokens: int
    output_tokens: int
    retries: int
    estimated_cost_usd: float
    avg_latency_ms: float


class LLMRunItem(BaseModel):
    id: int
    purpose: str
    agent_id: str | None = None
    agent_name: str | None = None
    provider: str
    model: str
    is_fixture: bool
    input_tokens: int
    output_tokens: int
    retry_count: int
    latency_ms: int
    stop_reason: str | None = None
    estimated_cost_usd: float
    created_at: datetime


class ResearchUsageSummary(BaseModel):
    provider: str
    sessions: int
    queries_executed: int
    results_returned: int
    sources_fetched: int
    fetch_failures: int
    retry_count: int
    duration_ms: int
    failed_sessions: int


class TelemetrySummary(BaseModel):
    llm_by_purpose: list[LLMPurposeBreakdown]
    llm_total_calls: int
    llm_total_cost_usd: float
    llm_total_retries: int
    llm_live_calls: int
    recent_llm_runs: list[LLMRunItem]
    research_usage: list[ResearchUsageSummary]
    research_total_sessions: int
    research_live_sessions: int
