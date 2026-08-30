"""The research pipeline: a question in, real sources out, evidence-grounded
findings after — or a clean RESEARCH_UNAVAILABLE if any of that fails.

The order is fixed and never reordered for convenience:

    validate budget
      -> research_provider.search()          (real, independent retrieval)
      -> persist the query and every source's metadata
      -> research_provider.fetch_source()     (bounded, exact text)
      -> persist each passage, with its sha256
      -> llm_provider.complete(ResearchSynthesis)  (interpret ONLY what was retrieved)
      -> persist findings, atomic claims, and claim -> passage evidence links
      -> update the session; log the causation chain

If search fails, returns nothing, or every fetch fails, the pipeline stops
before the LLM is ever called. A model is never asked to "pretend you searched
the web" — that instruction is not in this codebase anywhere, and the one
place an LLM sees anything at all is the synthesis call below, which only ever
receives passages this same function already persisted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import utcnow
from app.db.models.agents import Agent
from app.db.models.events import Event
from app.db.models.research import ResearchFinding, ResearchQuery, ResearchSession, ResearchSource
from app.db.models.research_provenance import Claim, ClaimEvidence, ResearchSourcePassage
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, ExposureType, ResearchStatus
from app.domain.ids import new_research_id
from app.providers.llm.base import LLMError, LLMProvider
from app.providers.research.base import ResearchProvider, ResearchProviderError
from app.schemas.research import ResearchSynthesis, SourceCandidate
from app.services.events import record_event
from app.services.exposure import expose
from app.services.telemetry import record_llm_run

#: How many of the search results are actually worth reading in full. Every
#: result's metadata is persisted regardless — this only bounds the (real,
#: retrieved) text sent on to the interpreting model, per the build bible's
#: "search cheaply, extract narrowly, synthesize expensively once".
MAX_SOURCES_TO_FETCH = 3

#: Rough chars-per-token, used only to keep the evidence bundle under budget —
#: never for billing (real token counts come from the provider's usage block).
CHARS_PER_TOKEN_ESTIMATE = 4

RESEARCH_SYNTHESIS_PROMPT_VERSION = "research_synthesis.v1"

RESEARCH_SYSTEM_PROMPT = """You are interpreting evidence that has already been retrieved by an \
independent search system. You did not search the web yourself: the numbered \
passages below are exactly what was found and shown to you, verbatim, with \
nothing added or removed. Never claim to have searched, browsed, or read \
anything beyond these passages.

Ground every finding in the passages given, and cite the passages a claim \
rests on by number. Classify each claim honestly using its true epistemic \
status:
- REAL_WORLD_FACT: something you are confident is simply true
- SOURCE_CLAIM: what a specific source asserts, which may or may not be true
- RESEARCH_FINDING: a conclusion this session's evidence itself supports
- AGENT_INFERENCE: something you infer from the evidence, but it isn't stated directly
- AGENT_BELIEF: a belief you already hold, brought to bear here
- HYPOTHESIS: a testable guess the evidence prompts
- SPECULATION: an idea that goes beyond what the evidence supports
Do not use SIMULATION_EVENT or CREATIVE_CONTENT here; they do not apply to research.

If the evidence is thin, weak, or contradictory, say so plainly in \
evidence_strength and confidence rather than overstating it. If the passages \
do not actually answer the question, return few or no findings and explain \
why in interpretation — an honest "the evidence doesn't say" is a better \
outcome than a manufactured one."""


class ResearchBudgetExceeded(Exception):
    """This agent has already used today's research opportunities."""


@dataclass
class ResearchOutcome:
    """What one START_RESEARCH action produced."""

    research_id: str | None = None
    status: ResearchStatus | None = None
    unavailable: bool = False
    reason: str | None = None
    sources_found: int = 0
    sources_fetched: int = 0
    findings_created: int = 0
    claims_created: int = 0
    llm_run_id: int | None = None
    event_ids: list[int] = field(default_factory=list)


def research_sessions_started_today(session: Session, agent_id: str, clock: SimulationClock) -> int:
    """How many research sessions this agent has already started today.

    Counted from the event log (mirrors how the activation scheduler counts a
    day's activations) rather than ``research_sessions.created_at``, since the
    clock's day is simulated time, not wall-clock time.
    """
    return (
        session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.event_type == EventType.AGENT_RESEARCH_STARTED,
                Event.agent_id == agent_id,
                Event.sim_day == clock.current_day,
            )
        )
        or 0
    )


def check_research_budget(
    session: Session, agent: Agent, clock: SimulationClock, settings: Settings
) -> str | None:
    """Return a rejection reason if this agent is over budget, else ``None``.

    Called from decision validation, before anything is executed — a
    over-budget START_RESEARCH is rejected the same way an unknown recipient
    is, not silently downgraded to a no-op after the fact.
    """
    used = research_sessions_started_today(session, agent.agent_id, clock)
    if used >= settings.max_research_sessions_per_agent_per_day:
        return (
            f"{agent.agent_id} has already started {used} research session(s) "
            f"today (limit {settings.max_research_sessions_per_agent_per_day})"
        )
    return None


def record_unavailable_session(
    session: Session,
    agent: Agent,
    question: str,
    clock: SimulationClock,
    correlation_id: str,
    reason: str,
) -> ResearchOutcome:
    """Record a research attempt that never got as far as calling a provider.

    Distinct from the failure paths inside :func:`start_research`: those run
    after a session and an AGENT_RESEARCH_STARTED event already exist. This is
    for the case one level further out — the provider itself could not even be
    constructed (no key, no dependency installed, unknown provider name) — so
    it creates both here, then immediately marks the session unavailable. The
    outcome is the same either way: no fabricated research, ever.
    """
    outcome = ResearchOutcome()
    research_session = ResearchSession(
        research_id=new_research_id(),
        agent_id=agent.agent_id,
        question=question,
        status=ResearchStatus.FAILED,
        interpretation=f"RESEARCH_UNAVAILABLE: {reason}",
        is_fixture=False,
        updated_at=utcnow(),
    )
    session.add(research_session)
    session.flush()
    outcome.research_id = research_session.research_id

    started = record_event(
        session,
        event_type=EventType.AGENT_RESEARCH_STARTED,
        agent_id=agent.agent_id,
        payload={"research_id": research_session.research_id, "question": question},
        entity_type="research_session",
        entity_id=research_session.research_id,
        correlation_id=correlation_id,
        clock=clock,
    )
    outcome.event_ids.append(started.id)

    unavailable = record_event(
        session,
        event_type=EventType.RESEARCH_UNAVAILABLE,
        agent_id=agent.agent_id,
        payload={"research_id": research_session.research_id, "reason": reason},
        entity_type="research_session",
        entity_id=research_session.research_id,
        correlation_id=correlation_id,
        causation_id=started.id,
        clock=clock,
    )
    outcome.event_ids.append(unavailable.id)

    outcome.status = ResearchStatus.FAILED
    outcome.unavailable = True
    outcome.reason = reason
    return outcome


def start_research(
    session: Session,
    agent: Agent,
    question: str,
    clock: SimulationClock,
    correlation_id: str,
    settings: Settings,
    llm_provider: LLMProvider,
    research_provider: ResearchProvider,
) -> ResearchOutcome:
    """Run one research session end to end. The caller commits."""
    outcome = ResearchOutcome()

    research_session = ResearchSession(
        research_id=new_research_id(),
        agent_id=agent.agent_id,
        question=question,
        status=ResearchStatus.IN_PROGRESS,
        is_fixture=research_provider.is_fixture,
    )
    session.add(research_session)
    session.flush()
    outcome.research_id = research_session.research_id

    started = record_event(
        session,
        event_type=EventType.AGENT_RESEARCH_STARTED,
        agent_id=agent.agent_id,
        payload={"research_id": research_session.research_id, "question": question},
        entity_type="research_session",
        entity_id=research_session.research_id,
        correlation_id=correlation_id,
        clock=clock,
    )
    outcome.event_ids.append(started.id)
    expose(
        session,
        agent_id=agent.agent_id,
        entity_type="research_session",
        entity_id=research_session.research_id,
        exposure_type=ExposureType.CREATED,
        source_event_id=started.id,
    )

    def fail(reason: str, *, event_type: EventType = EventType.RESEARCH_UNAVAILABLE) -> ResearchOutcome:
        research_session.status = ResearchStatus.FAILED
        research_session.interpretation = f"RESEARCH_UNAVAILABLE: {reason}"
        research_session.updated_at = utcnow()
        evt = record_event(
            session,
            event_type=event_type,
            agent_id=agent.agent_id,
            payload={"research_id": research_session.research_id, "reason": reason},
            entity_type="research_session",
            entity_id=research_session.research_id,
            correlation_id=correlation_id,
            causation_id=started.id,
            clock=clock,
        )
        outcome.event_ids.append(evt.id)
        outcome.status = ResearchStatus.FAILED
        outcome.unavailable = True
        outcome.reason = reason
        return outcome

    # --- retrieval: real search, never simulated -------------------------
    try:
        search_response = research_provider.search(
            question, max_results=settings.max_sources_per_query
        )
    except ResearchProviderError as exc:
        return fail(f"search failed: {exc}")

    if not search_response.results:
        return fail("search returned no results")

    query_row = ResearchQuery(
        research_session_id=research_session.research_id,
        query_text=question,
        sequence_number=1,
    )
    session.add(query_row)
    session.flush()
    searched = record_event(
        session,
        event_type=EventType.SEARCH_EXECUTED,
        agent_id=agent.agent_id,
        payload={
            "research_id": research_session.research_id,
            "provider": search_response.provider,
            "result_count": len(search_response.results),
            "is_fixture": search_response.is_fixture,
        },
        entity_type="research_query",
        entity_id=str(query_row.id),
        correlation_id=correlation_id,
        causation_id=started.id,
        clock=clock,
    )
    outcome.event_ids.append(searched.id)

    source_rows: list[ResearchSource] = []
    for candidate in search_response.results:
        row = _persist_source(session, research_session, candidate)
        source_rows.append(row)
        outcome.sources_found += 1
        discovered = record_event(
            session,
            event_type=EventType.SOURCE_DISCOVERED,
            agent_id=agent.agent_id,
            payload={"url": candidate.url, "provider": candidate.provider},
            entity_type="research_source",
            entity_id=str(row.id),
            correlation_id=correlation_id,
            causation_id=searched.id,
            clock=clock,
        )
        outcome.event_ids.append(discovered.id)
        expose(
            session,
            agent_id=agent.agent_id,
            entity_type="research_source",
            entity_id=row.id,
            exposure_type=ExposureType.CREATED,
            source_event_id=discovered.id,
        )

    # --- bounded extraction: fetch a few, brutally bound the text --------
    budget_chars = settings.max_evidence_tokens_per_research_session * CHARS_PER_TOKEN_ESTIMATE
    spent_chars = 0
    passages: list[ResearchSourcePassage] = []
    passage_sources: list[ResearchSource] = []

    to_fetch = min(MAX_SOURCES_TO_FETCH, len(source_rows), settings.max_sources_per_query)
    for row, candidate in list(zip(source_rows, search_response.results))[:to_fetch]:
        if spent_chars >= budget_chars:
            break
        remaining = budget_chars - spent_chars
        try:
            document = research_provider.fetch_source(
                candidate, query=question, max_chars=remaining
            )
        except ResearchProviderError:
            continue  # one source failing to fetch does not sink the session

        passage = ResearchSourcePassage(
            source_id=row.id,
            research_query_id=query_row.id,
            excerpt_text=document.excerpt,
            excerpt_sha256=document.excerpt_sha256
            or hashlib.sha256(document.excerpt.encode()).hexdigest(),
            retrieved_at=document.retrieved_at,
            provider_metadata=document.provider_metadata,
        )
        session.add(passage)
        session.flush()
        passages.append(passage)
        passage_sources.append(row)
        spent_chars += len(document.excerpt)
        outcome.sources_fetched += 1

    if not passages:
        return fail("every source failed to fetch; no evidence to interpret")

    # --- interpretation: only ever sees what was just persisted -----------
    prompt = _render_synthesis_prompt(agent, question, passages, passage_sources)
    try:
        result = llm_provider.complete(
            system=RESEARCH_SYSTEM_PROMPT,
            user=prompt,
            model=settings.research_model,
            purpose="research_synthesis",
            output_type=ResearchSynthesis,
        )
    except LLMError as exc:
        return fail(f"synthesis failed: {exc}")

    run = record_llm_run(
        session,
        result,
        purpose="research_synthesis",
        agent_id=agent.agent_id,
        prompt_version=RESEARCH_SYNTHESIS_PROMPT_VERSION,
    )
    outcome.llm_run_id = run.id
    synthesis: ResearchSynthesis = result.output

    # --- persist the interpretation, atomic claim by atomic claim --------
    research_session.status = ResearchStatus.COMPLETED
    research_session.evidence_strength = synthesis.evidence_strength
    research_session.confidence = synthesis.confidence
    research_session.interpretation = synthesis.interpretation
    research_session.open_questions = list(synthesis.open_questions)
    research_session.follow_ups = list(synthesis.follow_up_questions)
    research_session.updated_at = utcnow()

    completed = record_event(
        session,
        event_type=EventType.RESEARCH_COMPLETED,
        agent_id=agent.agent_id,
        payload={
            "research_id": research_session.research_id,
            "evidence_strength": synthesis.evidence_strength.value,
            "confidence": synthesis.confidence,
            "finding_count": len(synthesis.findings),
            "is_fixture": result.is_fixture,
        },
        entity_type="research_session",
        entity_id=research_session.research_id,
        correlation_id=correlation_id,
        causation_id=searched.id,
        clock=clock,
    )
    outcome.event_ids.append(completed.id)

    for synth_finding in synthesis.findings:
        finding = ResearchFinding(
            research_session_id=research_session.research_id,
            finding_text=synth_finding.text,
            classification=synth_finding.classification,
        )
        session.add(finding)
        session.flush()
        outcome.findings_created += 1

        created = record_event(
            session,
            event_type=EventType.FINDING_CREATED,
            agent_id=agent.agent_id,
            payload={"finding_text": synth_finding.text, "classification": synth_finding.classification.value},
            entity_type="research_finding",
            entity_id=str(finding.id),
            correlation_id=correlation_id,
            causation_id=completed.id,
            clock=clock,
        )
        outcome.event_ids.append(created.id)
        expose(
            session,
            agent_id=agent.agent_id,
            entity_type="research_finding",
            entity_id=finding.id,
            exposure_type=ExposureType.CREATED,
            source_event_id=created.id,
        )

        for synth_claim in synth_finding.claims:
            claim = Claim(
                research_session_id=research_session.research_id,
                finding_id=finding.id,
                claim_text=synth_claim.text,
                classification=synth_claim.classification,
                confidence=synth_claim.confidence,
            )
            session.add(claim)
            session.flush()
            outcome.claims_created += 1
            expose(
                session,
                agent_id=agent.agent_id,
                entity_type="claim",
                entity_id=claim.id,
                exposure_type=ExposureType.CREATED,
                source_event_id=created.id,
            )

            for link in synth_claim.evidence:
                # 1-based index into the same ordered list the prompt enumerated.
                if not (1 <= link.passage_index <= len(passages)):
                    continue  # a bad citation is dropped, not trusted
                passage = passages[link.passage_index - 1]
                session.add(
                    ClaimEvidence(claim_id=claim.id, passage_id=passage.id, relation=link.relation)
                )

    for question_text in synthesis.follow_up_questions:
        followup = record_event(
            session,
            event_type=EventType.FOLLOWUP_QUESTION_CREATED,
            agent_id=agent.agent_id,
            payload={"research_id": research_session.research_id, "question": question_text},
            entity_type="research_session",
            entity_id=research_session.research_id,
            correlation_id=correlation_id,
            causation_id=completed.id,
            clock=clock,
        )
        outcome.event_ids.append(followup.id)

    outcome.status = ResearchStatus.COMPLETED
    return outcome


def find_claim(session: Session, claim_id: int) -> Claim | None:
    return session.get(Claim, claim_id)


def challenge_claim(
    session: Session,
    challenger_agent_id: str,
    claim: Claim,
    argument: str,
    clock: SimulationClock,
    correlation_id: str,
) -> int:
    """Record a disagreement with a specific atomic claim.

    Disagreement is ordinary intellectual friction, not manufactured drama —
    this only ever fires when an agent (or a live model prompted the same way)
    chooses to challenge something, with its own real argument as
    ``argument``. Nothing here scores agents against each other or resolves
    who was "right"; it is a fact on the record that the researcher who owns
    the claim can see and choose to respond to, including by revising a belief
    that rested on it (Packet 6's cross-pollination chain).
    """
    event = record_event(
        session,
        event_type=EventType.CLAIM_CHALLENGED,
        agent_id=challenger_agent_id,
        payload={
            "claim_id": claim.id,
            "claim_text": claim.claim_text,
            "argument": argument,
            "research_session_id": claim.research_session_id,
        },
        entity_type="claim",
        entity_id=str(claim.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    # The challenge itself is exposed to the challenger (obviously) and to the
    # original researcher, whose claim this is — that is what lets them see it
    # next time they are activated, without exposing it to anyone else who
    # hasn't otherwise encountered this research.
    original_researcher = session.scalars(
        select(ResearchSession.agent_id).where(
            ResearchSession.research_id == claim.research_session_id
        )
    ).first()
    for agent_id in {challenger_agent_id, original_researcher} - {None}:
        expose(
            session, agent_id=agent_id, entity_type="claim", entity_id=claim.id,
            exposure_type=ExposureType.CREATED, source_event_id=event.id,
        )
    return event.id


def _persist_source(
    session: Session, research_session: ResearchSession, candidate: SourceCandidate
) -> ResearchSource:
    row = ResearchSource(
        research_session_id=research_session.research_id,
        url=candidate.url,
        title=candidate.title,
        publication=candidate.publication,
        author=candidate.author,
        source_type=candidate.source_type,
        pub_date=candidate.published_at.date() if candidate.published_at else None,
        retrieved_at=candidate.retrieved_at,
        excerpt=candidate.snippet,
        provider=candidate.provider,
        provider_result_id=candidate.provider_result_id,
        domain=candidate.domain,
    )
    session.add(row)
    session.flush()
    return row


def _render_synthesis_prompt(
    agent: Agent,
    question: str,
    passages: list[ResearchSourcePassage],
    sources: list[ResearchSource],
) -> str:
    lines = [
        f"QUESTION: {question}",
        f"AGENT_ID: {agent.agent_id}",
        f"AGENT_VOICE: {agent.voice}",
        "",
        "PASSAGES (numbered; cite by number in each claim's evidence):",
    ]
    for i, (passage, source) in enumerate(zip(passages, sources), start=1):
        lines.append(f"[{i}] {source.title} — {source.url}")
        if source.publication:
            lines.append(f"    publication: {source.publication}")
        if source.pub_date:
            lines.append(f"    published: {source.pub_date}")
        lines.append(f"    retrieved: {passage.retrieved_at}")
        lines.append(f"    text: {passage.excerpt_text}")
    lines.append("")
    lines.append(
        "Return findings and claims grounded only in the passages above. "
        "Do not describe searching or reading anything beyond them."
    )
    return "\n".join(lines)
