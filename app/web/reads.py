"""Read-only queries backing the Fishbowl (Packet 12, Part U).

Every function here does exactly one thing: SELECT from the real
simulation database and shape the rows into a typed read model
(``app/web/schemas.py``). None of them writes, none of them calls an LLM
provider or a research provider, and none of them imports
``app.providers.llm`` or ``app.providers.research`` at all — that absence is
what makes "reading the Fishbowl spends nothing" a structural fact checked
by ``scripts/test_fishbowl.py``, not just a claim in this docstring.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agent_questions import AgentQuestion
from app.db.models.agents import Agent, AgentBelief, AgentInterest, Relationship
from app.db.models.belief import BeliefBasis
from app.db.models.conversations import Conversation, ConversationMessage
from app.db.models.events import Event
from app.db.models.memory import Memory
from app.db.models.rabbit_holes import RabbitHole, RabbitHoleMember, RabbitHoleResearch
from app.db.models.reflection import AgentReflection
from app.db.models.reports import DailyReport
from app.db.models.research import ResearchFinding, ResearchQuery, ResearchSession, ResearchSource
from app.db.models.research_provenance import Claim, ClaimEvidence, ResearchSourcePassage
from app.db.models.research_usage import ResearchProviderUsage
from app.db.models.telemetry import LLMRun
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.characters import CHARACTER_PROFILES
from app.domain.enums import (
    ConversationStatus,
    EventType,
    InterestOrigin,
    RabbitHoleStatus,
    ResearchStatus,
    WallPostType,
)
from app.web.schemas import (
    AgentCard,
    AgentDetail,
    AgentResearchSummary,
    BeliefBasisItem,
    BeliefItem,
    ClaimEvidenceItem,
    ClaimItem,
    ClockStatus,
    ConversationDetail,
    ConversationListPage,
    ConversationMessageItem,
    ConversationPartner,
    ConversationSummary,
    DashboardSummary,
    DailyReportDetail,
    DailyReportSummary,
    EventFeedPage,
    FeedEvent,
    FindingItem,
    InterestItem,
    LLMPurposeBreakdown,
    LLMRunItem,
    MemoryItem,
    ProviderStatus,
    QuestionItem,
    RabbitHoleDetail,
    RabbitHoleListPage,
    RabbitHoleMemberItem,
    RabbitHoleSummary,
    RabbitHoleTimelineItem,
    ReflectionItem,
    RelationshipItem,
    ReportLink,
    ReportListPage,
    ResearchListPage,
    ResearchPassageItem,
    ResearchQueryItem,
    ResearchSessionDetail,
    ResearchSessionSummary,
    ResearchSourceItem,
    ResearchUsageSummary,
    TelemetrySummary,
    WallPage,
    WallPostItem,
    display_name,
)

#: Which event category (Part D's filters) each EventType belongs to.
_EVENT_CATEGORIES: dict[str, str] = {
    "AGENT_RESEARCH_STARTED": "research",
    "SEARCH_EXECUTED": "research",
    "SOURCE_DISCOVERED": "research",
    "RESEARCH_COMPLETED": "research",
    "RESEARCH_UNAVAILABLE": "research",
    "FINDING_CREATED": "research",
    "FINDING_SHARED": "research",
    "CLAIM_CHALLENGED": "research",
    "FOLLOWUP_QUESTION_CREATED": "research",
    "CONVERSATION_STARTED": "conversations",
    "CONVERSATION_MESSAGE": "conversations",
    "CONVERSATION_ENDED": "conversations",
    "CONVERSATION_JOINED": "conversations",
    "CONVERSATION_LEFT": "conversations",
    "MEMORY_CREATED": "memory",
    "MEMORY_REINFORCED": "memory",
    "MEMORY_RECALLED": "memory",
    "BELIEF_CREATED": "beliefs",
    "BELIEF_UPDATED": "beliefs",
    "BELIEF_REJECTED": "beliefs",
    "RABBIT_HOLE_CREATED": "rabbit_holes",
    "RABBIT_HOLE_JOINED": "rabbit_holes",
    "RABBIT_HOLE_UPDATED": "rabbit_holes",
    "RABBIT_HOLE_LEFT": "rabbit_holes",
    "RABBIT_HOLE_RESOLVED": "rabbit_holes",
    "RABBIT_HOLE_ABANDONED": "rabbit_holes",
    "RESEARCH_WALL_POSTED": "wall",
    "WALL_POST_READ": "wall",
    "INTEREST_INCREASED": "interests",
    "INTEREST_DECREASED": "interests",
    "INTEREST_CREATED": "interests",
    "INTEREST_DORMANT": "interests",
    "INTEREST_REVIVED": "interests",
    "REFLECTION_CREATED": "reflections",
    "REFLECTION_RECALLED": "reflections",
    "FOUNDER_MESSAGE": "founder",
    "FOUNDER_MESSAGE_DELIVERED": "founder",
    "DAILY_REPORT_CREATED": "founder",
}
EVENT_CATEGORIES: tuple[str, ...] = (
    "research", "conversations", "memory", "beliefs", "rabbit_holes",
    "wall", "interests", "reflections", "founder", "simulation",
)


def _category_for(event_type: str) -> str:
    return _EVENT_CATEGORIES.get(event_type, "simulation")


def _headline(event: Event, agent_name: str | None) -> str:
    """A human-readable line for the activity feed (Part D — never raw JSON)."""
    p = event.payload or {}
    who = agent_name or "Someone"
    et = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

    if et == "AGENT_RESEARCH_STARTED":
        return f"{who} started researching “{p.get('question', '...')}”"
    if et == "RESEARCH_COMPLETED":
        return f"{who}'s research wrapped up — {p.get('finding_count', 0)} finding(s), {p.get('evidence_strength', '?')} evidence"
    if et == "RESEARCH_UNAVAILABLE":
        return f"{who}'s research hit a dead end: {p.get('reason', 'unavailable')}"
    if et == "FINDING_SHARED":
        return f"{who} shared a finding to the Research Wall"
    if et == "CLAIM_CHALLENGED":
        return f"{who} challenged a claim: “{(p.get('claim_text') or '')[:80]}”"
    if et == "CONVERSATION_STARTED":
        others = [display_name(a) for a in p.get("participants", []) if a != event.agent_id]
        return f"{who} started a conversation with {', '.join(others) or 'someone'}"
    if et == "CONVERSATION_JOINED":
        return f"{who} joined a conversation"
    if et == "CONVERSATION_LEFT":
        return f"{who} left a conversation"
    if et == "CONVERSATION_ENDED":
        return f"A conversation ended ({p.get('reason', 'the room went quiet')})"
    if et == "MEMORY_CREATED":
        return f"{who} remembered something ({(p.get('memory_type') or '').lower()})"
    if et == "MEMORY_RECALLED":
        return f"{who} recalled a memory"
    if et == "BELIEF_CREATED":
        return f"{who} formed a belief: “{(p.get('statement') or '')[:80]}”"
    if et == "BELIEF_UPDATED":
        return f"{who} updated a belief ({p.get('new_status', 'revised')})"
    if et == "BELIEF_REJECTED":
        return f"{who} rejected a belief"
    if et == "RABBIT_HOLE_CREATED":
        return f"{who} opened a Rabbit Hole: “{p.get('title', '')}”"
    if et == "RABBIT_HOLE_JOINED":
        return f"{who} joined Rabbit Hole #{p.get('rabbit_hole_id')}"
    if et == "RABBIT_HOLE_UPDATED":
        return f"{who} contributed to Rabbit Hole #{p.get('rabbit_hole_id')}"
    if et == "RABBIT_HOLE_LEFT":
        return f"{who} left Rabbit Hole #{p.get('rabbit_hole_id')}"
    if et == "RABBIT_HOLE_RESOLVED":
        return f"{who} resolved Rabbit Hole #{p.get('rabbit_hole_id')}"
    if et == "RABBIT_HOLE_ABANDONED":
        return f"Rabbit Hole #{p.get('rabbit_hole_id')} went dormant and was abandoned"
    if et == "RESEARCH_WALL_POSTED":
        return f"{who} posted to the Research Wall ({(p.get('post_type') or '').lower()})"
    if et == "WALL_POST_READ":
        return f"{who} read a wall post"
    if et in ("INTEREST_INCREASED", "INTEREST_CREATED", "INTEREST_REVIVED"):
        return f"{who}'s interest grew"
    if et == "INTEREST_DECREASED":
        return f"{who}'s interest faded a little"
    if et == "INTEREST_DORMANT":
        return f"{who}'s interest went dormant"
    if et == "REFLECTION_CREATED":
        return f"{who} reflected: “{p.get('topic', '')}”"
    if et == "REFLECTION_RECALLED":
        return f"{who} recalled a reflection"
    if et == "FOUNDER_MESSAGE_DELIVERED":
        return "A Founder message was delivered" + (f" to {who}" if event.agent_id else " to everyone")
    if et == "DAILY_REPORT_CREATED":
        return f"Daily Founder Field Report created for day {p.get('day')}"
    if et == "AGENT_WOKE":
        return f"{who} woke to act"
    if et == "AGENT_ACTED":
        return f"{who}: {p.get('summary', p.get('activity', 'acted'))}"
    if et == "INVALID_AGENT_DECISION":
        return f"{who}'s decision was rejected ({(p.get('reason') or '')[:80]})"
    if et == "PERIOD_ADVANCED":
        to = p.get("to", {})
        return f"The clock advanced to day {to.get('day')} {to.get('period')}"
    if et == "DAY_ADVANCED":
        return f"Day {p.get('day')} began"
    return f"{who + ': ' if event.agent_id else ''}{et.replace('_', ' ').title()}"


def _sim_day_for_entity(session: Session, entity_type: str, entity_id: str) -> int | None:
    """The simulated day something happened, read back from its own event
    row rather than stored redundantly on every entity (Part H's day filter,
    honestly derived instead of a fabricated column)."""
    return session.scalars(
        select(Event.sim_day)
        .where(Event.entity_type == entity_type, Event.entity_id == entity_id)
        .order_by(Event.id.asc())
        .limit(1)
    ).first()


# ---------------------------------------------------------------------------
# C — Dashboard
# ---------------------------------------------------------------------------


def get_clock_status(session: Session) -> ClockStatus | None:
    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is None:
        return None
    latest = session.scalars(select(func.max(Event.created_at))).first()
    return ClockStatus(
        day=clock.current_day,
        period=clock.current_period,
        is_paused=clock.is_paused,
        last_advanced_at=clock.last_advanced_at,
        latest_event_at=latest,
    )


def get_provider_status(settings: Settings) -> ProviderStatus:
    return ProviderStatus(
        llm_provider=settings.llm_provider,
        llm_is_live=not settings.uses_fixture_llm,
        agent_model=settings.agent_model,
        research_model=settings.research_model,
        report_model=settings.report_model,
        research_provider=settings.research_provider,
        research_is_live=not settings.uses_fixture_research,
    )


def _active_conversation_for(session: Session, agent_id: str) -> Conversation | None:
    """The one open (non-ENDED) conversation this agent is currently in, if
    any — a real agent is in at most one conversation at a time."""
    open_conversations = session.scalars(
        select(Conversation).where(Conversation.status != ConversationStatus.ENDED).order_by(Conversation.id.desc())
    )
    return next(
        (c for c in open_conversations if agent_id in (c.participant_ids or [])), None
    )


def _conversation_partners(conversation: Conversation | None, agent_id: str) -> list[ConversationPartner]:
    if conversation is None:
        return []
    return [
        ConversationPartner(agent_id=a, name=display_name(a))
        for a in (conversation.participant_ids or [])
        if a != agent_id
    ]


def _top_interests(session: Session, agent_id: str, limit: int = 3) -> list[str]:
    rows = session.scalars(
        select(AgentInterest)
        .where(AgentInterest.agent_id == agent_id, AgentInterest.dormant.is_(False))
        .order_by(AgentInterest.strength.desc())
        .limit(limit)
    ).all()
    return [r.interest for r in rows]


def _recent_memory_text(session: Session, agent_id: str) -> str | None:
    m = session.scalars(
        select(Memory).where(Memory.agent_id == agent_id).order_by(Memory.id.desc()).limit(1)
    ).first()
    return m.content if m else None


def _current_research(session: Session, agent_id: str) -> ResearchSession | None:
    return session.scalars(
        select(ResearchSession)
        .where(ResearchSession.agent_id == agent_id, ResearchSession.status == ResearchStatus.IN_PROGRESS)
        .order_by(ResearchSession.id.desc())
        .limit(1)
    ).first()


def _last_action(session: Session, agent_id: str) -> Event | None:
    return session.scalars(
        select(Event)
        .where(Event.agent_id == agent_id, Event.event_type == EventType.AGENT_ACTED)
        .order_by(Event.id.desc())
        .limit(1)
    ).first()


def _agent_status_label(agent: Agent, conversation: Conversation | None, research: ResearchSession | None) -> str:
    if research is not None:
        return "researching"
    if conversation is not None:
        return "in conversation"
    if agent.current_activity:
        return agent.current_activity
    return "idle"


def get_agent_card(session: Session, agent: Agent) -> AgentCard:
    conversation = _active_conversation_for(session, agent.agent_id)
    research = _current_research(session, agent.agent_id)
    last_action = _last_action(session, agent.agent_id)
    profile = CHARACTER_PROFILES.get(agent.agent_id)
    role = profile.communication_style if profile else (agent.identity or "")[:120]
    return AgentCard(
        agent_id=agent.agent_id,
        name=display_name(agent.agent_id),
        role=role,
        status=_agent_status_label(agent, conversation, research),
        current_location=agent.current_location,
        current_activity=agent.current_activity,
        conversation_id=conversation.id if conversation else None,
        conversation_partners=_conversation_partners(conversation, agent.agent_id),
        current_research_id=research.research_id if research else None,
        current_research_question=research.question if research else None,
        top_interests=_top_interests(session, agent.agent_id),
        recent_memory=_recent_memory_text(session, agent.agent_id),
        last_action_summary=(last_action.payload or {}).get("summary") if last_action else None,
        last_action_at=last_action.created_at if last_action else None,
    )


def get_dashboard(session: Session, settings: Settings) -> DashboardSummary | None:
    clock = get_clock_status(session)
    if clock is None:
        return None
    agents = list(session.scalars(select(Agent).order_by(Agent.id)))
    return DashboardSummary(
        clock=clock,
        providers=get_provider_status(settings),
        agents=[get_agent_card(session, a) for a in agents],
    )


# ---------------------------------------------------------------------------
# D — Live activity feed
# ---------------------------------------------------------------------------


def get_event_feed(
    session: Session,
    *,
    agent_id: str | None = None,
    category: str | None = None,
    day: int | None = None,
    before_id: int | None = None,
    limit: int = 50,
) -> EventFeedPage:
    limit = max(1, min(limit, 200))
    stmt = select(Event).order_by(Event.id.desc())
    if agent_id:
        stmt = stmt.where(Event.agent_id == agent_id)
    if day is not None:
        stmt = stmt.where(Event.sim_day == day)
    if before_id is not None:
        stmt = stmt.where(Event.id < before_id)
    # Category can't be pushed into SQL (it's derived from event_type), so
    # over-fetch a bounded window and filter in Python — bounded by a hard
    # ceiling regardless of how sparse the category is.
    rows = list(session.scalars(stmt.limit(limit * 6 if category else limit)))

    events: list[FeedEvent] = []
    for e in rows:
        et = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
        cat = _category_for(et)
        if category and cat != category:
            continue
        events.append(
            FeedEvent(
                id=e.id,
                event_type=et,
                category=cat,
                agent_id=e.agent_id,
                agent_name=display_name(e.agent_id) if e.agent_id else None,
                headline=_headline(e, display_name(e.agent_id) if e.agent_id else None),
                sim_day=e.sim_day,
                sim_period=e.sim_period,
                created_at=e.created_at,
                correlation_id=e.correlation_id,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                payload=e.payload or {},
            )
        )
        if len(events) >= limit:
            break
    return EventFeedPage(events=events, categories=list(EVENT_CATEGORIES))


# ---------------------------------------------------------------------------
# E — Agent detail
# ---------------------------------------------------------------------------


def get_agent_detail(session: Session, agent_id: str) -> AgentDetail | None:
    agent = session.scalars(select(Agent).where(Agent.agent_id == agent_id)).first()
    if agent is None:
        return None

    conversation = _active_conversation_for(session, agent_id)
    research = _current_research(session, agent_id)
    profile = CHARACTER_PROFILES.get(agent_id)

    interests = [
        InterestItem(
            id=i.id, interest=i.interest, strength=i.strength, origin=i.origin,
            dormant=i.dormant, is_founding=(i.origin == InterestOrigin.FOUNDING.value),
            last_engaged=i.last_engaged, last_engaged_sim_day=i.last_engaged_sim_day,
        )
        for i in session.scalars(
            select(AgentInterest).where(AgentInterest.agent_id == agent_id)
            .order_by(AgentInterest.strength.desc())
        )
    ]

    memories = [
        MemoryItem(
            id=m.id, memory_type=m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type),
            content=m.content, importance=m.importance, confidence=m.confidence,
            decay_score=m.decay_score, reinforcement_count=m.reinforcement_count,
            created_sim_day=m.created_sim_day, last_accessed_sim_day=m.last_accessed_sim_day,
            related_agent_ids=m.related_agent_ids or [], related_research_ids=m.related_research_ids or [],
            related_rabbit_hole_ids=m.related_rabbit_hole_ids or [],
            related_conversation_ids=m.related_conversation_ids or [],
        )
        for m in session.scalars(
            select(Memory).where(Memory.agent_id == agent_id).order_by(Memory.id.desc()).limit(30)
        )
    ]

    beliefs: list[BeliefItem] = []
    for b in session.scalars(
        select(AgentBelief).where(AgentBelief.agent_id == agent_id).order_by(AgentBelief.id.desc())
    ):
        history = [
            BeliefBasisItem(
                basis_type=h.basis_type, basis_id=h.basis_id,
                relation=h.relation.value if hasattr(h.relation, "value") else str(h.relation),
                created_at=h.created_at,
            )
            for h in session.scalars(
                select(BeliefBasis).where(BeliefBasis.belief_id == b.id).order_by(BeliefBasis.id.asc())
            )
        ]
        beliefs.append(
            BeliefItem(
                id=b.id, statement=b.statement, confidence=b.confidence,
                status=b.status.value if hasattr(b.status, "value") else str(b.status),
                basis=[str(x) for x in (b.basis or [])], history=history, updated_at=b.updated_at,
            )
        )

    relationships: list[RelationshipItem] = []
    for r in session.scalars(
        select(Relationship).where(
            (Relationship.agent_a_id == agent_id) | (Relationship.agent_b_id == agent_id)
        )
    ):
        other = r.agent_b_id if r.agent_a_id == agent_id else r.agent_a_id
        relationships.append(
            RelationshipItem(
                other_agent_id=other, other_agent_name=display_name(other),
                trust_score=r.trust_score, familiarity=r.familiarity,
                intellectual_affinity=r.intellectual_affinity,
                productive_disagreement_count=r.productive_disagreement_count,
                interaction_count=r.interaction_count, last_interaction=r.last_interaction,
                notes=r.notes,
            )
        )
    relationships.sort(key=lambda x: x.trust_score, reverse=True)

    reflections = [
        ReflectionItem(
            id=rf.id, simulation_day=rf.simulation_day, topic=rf.topic, summary=rf.summary,
            importance=rf.importance, confidence=rf.confidence,
            status=rf.status.value if hasattr(rf.status, "value") else str(rf.status),
            open_question=rf.open_question, suggested_follow_up=rf.suggested_follow_up,
            is_fixture=rf.is_fixture,
            source_counts={
                "memories": len(rf.source_memory_ids or []),
                "research": len(rf.source_research_ids or []),
                "beliefs": len(rf.source_belief_ids or []),
                "conversations": len(rf.source_conversation_ids or []),
                "rabbit_holes": len(rf.source_rabbit_hole_ids or []),
                "wall_posts": len(rf.source_wall_post_ids or []),
                "reflections": len(rf.source_reflection_ids or []),
            },
        )
        for rf in session.scalars(
            select(AgentReflection).where(AgentReflection.agent_id == agent_id)
            .order_by(AgentReflection.id.desc()).limit(20)
        )
    ]

    questions = [
        QuestionItem(
            id=q.id, question=q.question,
            status=q.status.value if hasattr(q.status, "value") else str(q.status),
            salience=q.salience, last_engaged_sim_day=q.last_engaged_sim_day,
            origin=(
                "reflection" if q.origin_reflection_id is not None
                else "research" if q.origin_research_session_id is not None
                else "memory" if q.origin_memory_id is not None
                else "conversation" if q.origin_conversation_id is not None
                else "unspecified"
            ),
            origin_reflection_id=q.origin_reflection_id,
            origin_research_session_id=q.origin_research_session_id,
            origin_memory_id=q.origin_memory_id,
            origin_conversation_id=q.origin_conversation_id,
            research_session_id=q.research_session_id,
            rabbit_hole_id=q.rabbit_hole_id,
            reformulated_from_id=q.reformulated_from_id,
            reformulated_into_id=q.reformulated_into_id,
        )
        for q in session.scalars(
            select(AgentQuestion).where(AgentQuestion.agent_id == agent_id)
            .order_by(AgentQuestion.salience.desc(), AgentQuestion.id.desc())
        )
    ]

    research_sessions: list[AgentResearchSummary] = []
    for rs in session.scalars(
        select(ResearchSession).where(ResearchSession.agent_id == agent_id)
        .order_by(ResearchSession.id.desc())
    ):
        finding_count = session.scalar(
            select(func.count(ResearchFinding.id)).where(
                ResearchFinding.research_session_id == rs.research_id
            )
        ) or 0
        research_sessions.append(
            AgentResearchSummary(
                research_id=rs.research_id, question=rs.question,
                status=rs.status.value if hasattr(rs.status, "value") else str(rs.status),
                evidence_strength=rs.evidence_strength.value if hasattr(rs.evidence_strength, "value") else str(rs.evidence_strength),
                confidence=rs.confidence, is_fixture=rs.is_fixture, created_at=rs.created_at,
                finding_count=finding_count,
            )
        )

    return AgentDetail(
        agent_id=agent.agent_id, name=display_name(agent.agent_id),
        identity=agent.identity, voice=agent.voice,
        communication_style=profile.communication_style if profile else None,
        epistemic_style=profile.epistemic_style if profile else None,
        current_location=agent.current_location, current_activity=agent.current_activity,
        conversation_id=conversation.id if conversation else None,
        conversation_partners=_conversation_partners(conversation, agent_id),
        current_research_id=research.research_id if research else None,
        current_research_question=research.question if research else None,
        reflection_pressure=agent.reflection_pressure,
        interests=interests, memories=memories, beliefs=beliefs,
        relationships=relationships, reflections=reflections,
        questions=questions,
        research_sessions=research_sessions,
    )


# ---------------------------------------------------------------------------
# F — Conversations
# ---------------------------------------------------------------------------


def _conversation_summary(session: Session, c: Conversation) -> ConversationSummary:
    count = session.scalar(
        select(func.count(ConversationMessage.id)).where(ConversationMessage.conversation_id == c.id)
    ) or 0
    return ConversationSummary(
        id=c.id, status=c.status.value if hasattr(c.status, "value") else str(c.status),
        trigger_type=c.trigger_type.value if hasattr(c.trigger_type, "value") else str(c.trigger_type),
        location=c.location, current_subject=c.current_subject,
        initiating_reason=c.initiating_reason, ending_reason=c.ending_reason,
        participants=[ConversationPartner(agent_id=a, name=display_name(a)) for a in (c.participant_ids or [])],
        departed_agent_ids=c.departed_agent_ids or [],
        started_at=c.started_at, ended_at=c.ended_at,
        started_sim_day=c.started_sim_day, started_sim_period=c.started_sim_period,
        message_count=count,
    )


def get_conversations(session: Session, *, agent_id: str | None = None, status: str | None = None) -> ConversationListPage:
    stmt = select(Conversation).order_by(Conversation.id.desc()).limit(100)
    if status and status in ConversationStatus.__members__:
        stmt = stmt.where(Conversation.status == ConversationStatus[status])
    rows = list(session.scalars(stmt))
    if agent_id:
        rows = [c for c in rows if agent_id in (c.participant_ids or []) or agent_id in (c.departed_agent_ids or [])]
    return ConversationListPage(conversations=[_conversation_summary(session, c) for c in rows])


def get_conversation_detail(session: Session, conversation_id: int) -> ConversationDetail | None:
    c = session.get(Conversation, conversation_id)
    if c is None:
        return None
    summary = _conversation_summary(session, c)
    messages = [
        ConversationMessageItem(
            id=m.id, agent_id=m.agent_id, agent_name=display_name(m.agent_id),
            content=m.content, turn_number=m.turn_number, created_at=m.created_at,
        )
        for m in session.scalars(
            select(ConversationMessage).where(ConversationMessage.conversation_id == c.id)
            .order_by(ConversationMessage.turn_number.asc(), ConversationMessage.id.asc())
        )
    ]
    return ConversationDetail(
        **summary.model_dump(), messages=messages,
        related_research_ids=c.related_research_ids or [],
        related_wall_post_ids=c.related_wall_post_ids or [],
        related_rabbit_hole_ids=c.related_rabbit_hole_ids or [],
        related_memory_ids=c.related_memory_ids or [],
    )


# ---------------------------------------------------------------------------
# G — Research / provenance
# ---------------------------------------------------------------------------


def _research_summary(session: Session, rs: ResearchSession) -> ResearchSessionSummary:
    finding_count = session.scalar(
        select(func.count(ResearchFinding.id)).where(ResearchFinding.research_session_id == rs.research_id)
    ) or 0
    source_count = session.scalar(
        select(func.count(ResearchSource.id)).where(ResearchSource.research_session_id == rs.research_id)
    ) or 0
    provider = session.scalars(
        select(ResearchSource.provider).where(ResearchSource.research_session_id == rs.research_id).limit(1)
    ).first()
    return ResearchSessionSummary(
        research_id=rs.research_id, agent_id=rs.agent_id, agent_name=display_name(rs.agent_id),
        question=rs.question, status=rs.status.value if hasattr(rs.status, "value") else str(rs.status),
        evidence_strength=rs.evidence_strength.value if hasattr(rs.evidence_strength, "value") else str(rs.evidence_strength),
        confidence=rs.confidence, is_fixture=rs.is_fixture, provider=provider,
        created_at=rs.created_at, finding_count=finding_count, source_count=source_count,
    )


def get_research_sessions(
    session: Session, *, agent_id: str | None = None, status: str | None = None
) -> ResearchListPage:
    stmt = select(ResearchSession).order_by(ResearchSession.id.desc()).limit(150)
    if agent_id:
        stmt = stmt.where(ResearchSession.agent_id == agent_id)
    if status and status in ResearchStatus.__members__:
        stmt = stmt.where(ResearchSession.status == ResearchStatus[status])
    rows = list(session.scalars(stmt))
    return ResearchListPage(sessions=[_research_summary(session, rs) for rs in rows])


def get_research_detail(session: Session, research_id: str) -> ResearchSessionDetail | None:
    rs = session.scalars(
        select(ResearchSession).where(ResearchSession.research_id == research_id)
    ).first()
    if rs is None:
        return None
    summary = _research_summary(session, rs)

    queries = [
        ResearchQueryItem(id=q.id, query_text=q.query_text, sequence_number=q.sequence_number, executed_at=q.executed_at)
        for q in session.scalars(
            select(ResearchQuery).where(ResearchQuery.research_session_id == research_id)
            .order_by(ResearchQuery.sequence_number.asc())
        )
    ]

    sources: list[ResearchSourceItem] = []
    source_rows = list(
        session.scalars(
            select(ResearchSource).where(ResearchSource.research_session_id == research_id)
            .order_by(ResearchSource.id.asc())
        )
    )
    passages_by_source: dict[int, list[ResearchSourcePassage]] = defaultdict(list)
    if source_rows:
        source_ids = [s.id for s in source_rows]
        for p in session.scalars(
            select(ResearchSourcePassage).where(ResearchSourcePassage.source_id.in_(source_ids))
        ):
            passages_by_source[p.source_id].append(p)
    for s in source_rows:
        passages = passages_by_source.get(s.id, [])
        sources.append(
            ResearchSourceItem(
                id=s.id, url=s.url, title=s.title, domain=s.domain,
                quality_tier=s.quality_tier.value if hasattr(s.quality_tier, "value") else str(s.quality_tier),
                provider=s.provider, provider_rank=s.provider_rank, is_primary=s.is_primary,
                pub_date=s.pub_date.isoformat() if s.pub_date else None, retrieved_at=s.retrieved_at,
                fetched=bool(passages),
                passages=[
                    ResearchPassageItem(
                        id=p.id, excerpt_text=p.excerpt_text, excerpt_sha256=p.excerpt_sha256,
                        locator=p.locator, research_query_id=p.research_query_id,
                    )
                    for p in passages
                ],
            )
        )
    source_by_id = {s.id: s for s in source_rows}

    findings: list[FindingItem] = []
    finding_rows = list(
        session.scalars(
            select(ResearchFinding).where(ResearchFinding.research_session_id == research_id)
            .order_by(ResearchFinding.id.asc())
        )
    )
    for f in finding_rows:
        claims: list[ClaimItem] = []
        for c in session.scalars(select(Claim).where(Claim.finding_id == f.id).order_by(Claim.id.asc())):
            evidence: list[ClaimEvidenceItem] = []
            for ce in session.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == c.id)):
                passage = session.get(ResearchSourcePassage, ce.passage_id)
                if passage is None:
                    continue
                evidence.append(
                    ClaimEvidenceItem(
                        passage_id=passage.id, source_id=passage.source_id,
                        relation=ce.relation.value if hasattr(ce.relation, "value") else str(ce.relation),
                        excerpt_text=passage.excerpt_text,
                    )
                )
            claims.append(
                ClaimItem(
                    id=c.id, claim_text=c.claim_text,
                    classification=c.classification.value if hasattr(c.classification, "value") else str(c.classification),
                    confidence=c.confidence, evidence=evidence,
                )
            )
        findings.append(
            FindingItem(
                id=f.id, finding_text=f.finding_text,
                classification=f.classification.value if hasattr(f.classification, "value") else str(f.classification),
                claims=claims,
            )
        )

    return ResearchSessionDetail(
        **summary.model_dump(),
        interpretation=rs.interpretation, open_questions=rs.open_questions or [],
        follow_ups=rs.follow_ups or [], related_research=rs.related_research or [],
        queries=queries, sources=sources, findings=findings,
    )


# ---------------------------------------------------------------------------
# H — Research Wall
# ---------------------------------------------------------------------------


def get_wall(
    session: Session, *, agent_id: str | None = None, post_type: str | None = None,
    day: int | None = None, rabbit_hole_id: int | None = None,
) -> WallPage:
    stmt = select(ResearchWallPost).order_by(ResearchWallPost.id.desc()).limit(200)
    if agent_id:
        stmt = stmt.where(ResearchWallPost.agent_id == agent_id)
    if post_type and post_type in WallPostType.__members__:
        stmt = stmt.where(ResearchWallPost.post_type == WallPostType[post_type])
    if rabbit_hole_id is not None:
        stmt = stmt.where(ResearchWallPost.related_rabbit_hole_id == rabbit_hole_id)
    rows = list(session.scalars(stmt))
    posts: list[WallPostItem] = []
    for p in rows:
        sim_day = _sim_day_for_entity(session, "research_wall", str(p.id))
        if day is not None and sim_day != day:
            continue
        posts.append(
            WallPostItem(
                id=p.id, agent_id=p.agent_id, agent_name=display_name(p.agent_id),
                post_type=p.post_type.value if hasattr(p.post_type, "value") else str(p.post_type),
                content=p.content, related_research_id=p.related_research_id,
                related_wall_post_id=p.related_wall_post_id, related_rabbit_hole_id=p.related_rabbit_hole_id,
                sim_day=sim_day, created_at=p.created_at,
            )
        )
    return WallPage(posts=posts)


# ---------------------------------------------------------------------------
# I — Rabbit Holes
# ---------------------------------------------------------------------------


def _rabbit_hole_summary(session: Session, h: RabbitHole) -> RabbitHoleSummary:
    member_count = session.scalar(
        select(func.count(RabbitHoleMember.id)).where(
            RabbitHoleMember.rabbit_hole_id == h.id, RabbitHoleMember.left_at.is_(None)
        )
    ) or 0
    return RabbitHoleSummary(
        id=h.id, title=h.title, originating_agent_id=h.originating_agent_id,
        originating_agent_name=display_name(h.originating_agent_id),
        status=h.status.value if hasattr(h.status, "value") else str(h.status),
        evidence_strength=h.evidence_strength.value if hasattr(h.evidence_strength, "value") else str(h.evidence_strength),
        activity_level=h.activity_level, member_count=member_count,
        last_activity=h.last_activity, last_activity_day=h.last_activity_day,
    )


def get_rabbit_holes(session: Session, *, status: str | None = None) -> RabbitHoleListPage:
    stmt = select(RabbitHole).order_by(RabbitHole.id.desc())
    if status and status in RabbitHoleStatus.__members__:
        stmt = stmt.where(RabbitHole.status == RabbitHoleStatus[status])
    rows = list(session.scalars(stmt))
    return RabbitHoleListPage(rabbit_holes=[_rabbit_hole_summary(session, h) for h in rows])


def get_rabbit_hole_detail(session: Session, rabbit_hole_id: int) -> RabbitHoleDetail | None:
    h = session.get(RabbitHole, rabbit_hole_id)
    if h is None:
        return None
    summary = _rabbit_hole_summary(session, h)
    members = [
        RabbitHoleMemberItem(
            agent_id=m.agent_id, agent_name=display_name(m.agent_id),
            joined_at=m.joined_at, left_at=m.left_at, active=m.left_at is None,
        )
        for m in session.scalars(
            select(RabbitHoleMember).where(RabbitHoleMember.rabbit_hole_id == h.id).order_by(RabbitHoleMember.id.asc())
        )
    ]
    related_research_ids = list(
        session.scalars(
            select(RabbitHoleResearch.research_session_id).where(RabbitHoleResearch.rabbit_hole_id == h.id)
        )
    )
    timeline = [
        RabbitHoleTimelineItem(
            event_type=e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
            headline=_headline(e, display_name(e.agent_id) if e.agent_id else None),
            agent_id=e.agent_id, agent_name=display_name(e.agent_id) if e.agent_id else None,
            created_at=e.created_at,
        )
        for e in session.scalars(
            select(Event).where(Event.entity_type == "rabbit_hole", Event.entity_id == str(h.id))
            .order_by(Event.id.asc())
        )
    ]
    return RabbitHoleDetail(
        **summary.model_dump(), description=h.description, current_hypothesis=h.current_hypothesis,
        counterarguments=h.counterarguments or [], open_questions=h.open_questions or [],
        members=members, related_research_ids=related_research_ids, timeline=timeline,
    )


# ---------------------------------------------------------------------------
# J — Founder Report
# ---------------------------------------------------------------------------


def _report_links(structured: dict) -> list[ReportLink]:
    links: list[ReportLink] = []
    kind_to_url = {
        "wall_posts": "/fishbowl/wall",
        "rabbit_holes": "/fishbowl/rabbit-holes/{id}",
        "conversations": "/fishbowl/conversations/{id}",
        "findings": "/fishbowl/research/{id}",
        "belief_changes": None,
        "memories": None,
        "reflections": None,
    }
    for kind, items in (structured or {}).items():
        if not isinstance(items, list):
            continue
        template = kind_to_url.get(kind)
        for item in items:
            if not isinstance(item, dict):
                continue
            ref_id = item.get("id")
            url = template.format(id=ref_id) if (template and ref_id is not None) else None
            links.append(
                ReportLink(
                    kind=kind, text=item.get("text", ""), classification=item.get("classification"), url=url,
                )
            )
    return links


def get_reports(session: Session) -> ReportListPage:
    rows = list(session.scalars(select(DailyReport).order_by(DailyReport.day_number.desc())))
    return ReportListPage(
        reports=[
            DailyReportSummary(
                day_number=r.day_number, title=r.title, had_meaningful_activity=r.had_meaningful_activity,
                is_fixture=r.is_fixture, created_at=r.created_at,
            )
            for r in rows
        ]
    )


def get_report_detail(session: Session, day_number: int) -> DailyReportDetail | None:
    r = session.scalars(select(DailyReport).where(DailyReport.day_number == day_number)).first()
    if r is None:
        return None
    return DailyReportDetail(
        day_number=r.day_number, title=r.title, had_meaningful_activity=r.had_meaningful_activity,
        is_fixture=r.is_fixture, created_at=r.created_at, summary_text=r.summary_text,
        links=_report_links(r.structured or {}),
    )


def get_latest_report(session: Session) -> DailyReportDetail | None:
    r = session.scalars(select(DailyReport).order_by(DailyReport.day_number.desc()).limit(1)).first()
    if r is None:
        return None
    return get_report_detail(session, r.day_number)


# ---------------------------------------------------------------------------
# L — Telemetry / cost
# ---------------------------------------------------------------------------


def get_telemetry(session: Session, *, recent_limit: int = 30) -> TelemetrySummary:
    runs = list(session.scalars(select(LLMRun)))
    by_purpose: dict[str, list[LLMRun]] = defaultdict(list)
    for run in runs:
        by_purpose[run.purpose].append(run)

    llm_by_purpose = [
        LLMPurposeBreakdown(
            purpose=purpose,
            calls=len(rows),
            input_tokens=sum(r.input_tokens for r in rows),
            output_tokens=sum(r.output_tokens for r in rows),
            retries=sum(r.retry_count for r in rows),
            estimated_cost_usd=round(sum(r.estimated_cost_usd for r in rows), 6),
            avg_latency_ms=round(sum(r.latency_ms for r in rows) / len(rows), 1) if rows else 0.0,
        )
        for purpose, rows in sorted(by_purpose.items())
    ]

    recent = list(session.scalars(select(LLMRun).order_by(LLMRun.id.desc()).limit(recent_limit)))
    recent_llm_runs = [
        LLMRunItem(
            id=r.id, purpose=r.purpose, agent_id=r.agent_id,
            agent_name=display_name(r.agent_id) if r.agent_id else None,
            provider=r.provider, model=r.model, is_fixture=r.is_fixture,
            input_tokens=r.input_tokens, output_tokens=r.output_tokens, retry_count=r.retry_count,
            latency_ms=r.latency_ms, stop_reason=r.stop_reason, estimated_cost_usd=r.estimated_cost_usd,
            created_at=r.created_at,
        )
        for r in recent
    ]

    usage_rows = list(session.scalars(select(ResearchProviderUsage)))
    by_provider: dict[str, list[ResearchProviderUsage]] = defaultdict(list)
    for u in usage_rows:
        by_provider[u.provider].append(u)
    research_usage = [
        ResearchUsageSummary(
            provider=provider,
            sessions=len(rows),
            queries_executed=sum(r.queries_executed for r in rows),
            results_returned=sum(r.results_returned for r in rows),
            sources_fetched=sum(r.sources_fetched for r in rows),
            fetch_failures=sum(r.fetch_failures for r in rows),
            retry_count=sum(r.retry_count for r in rows),
            duration_ms=sum(r.duration_ms for r in rows),
            failed_sessions=sum(1 for r in rows if r.failed),
        )
        for provider, rows in sorted(by_provider.items())
    ]

    return TelemetrySummary(
        llm_by_purpose=llm_by_purpose,
        llm_total_calls=len(runs),
        llm_total_cost_usd=round(sum(r.estimated_cost_usd for r in runs), 6),
        llm_total_retries=sum(r.retry_count for r in runs),
        llm_live_calls=sum(1 for r in runs if not r.is_fixture),
        recent_llm_runs=recent_llm_runs,
        research_usage=research_usage,
        research_total_sessions=len(usage_rows),
        research_live_sessions=sum(1 for u in usage_rows if not u.is_fixture),
    )
