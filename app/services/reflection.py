"""The reflection engine: recognizing a pattern, not summarizing a day (§15,
Packet 9).

A memory records "this happened"; a reflection is a step of abstraction above
several of those — "several recent things seem to point toward the same
unresolved question" — and is never generated as hidden chain-of-thought:
only the concise conclusion itself is ever requested or stored.

Two halves, deliberately split across a cheap and an expensive path:

- :func:`accumulate_pressure` is called from ``app.services.memory._upsert``
  every time a memory is created or reinforced — cheap, session+clock only,
  no model call. Nearly every signal the spec lists as a reflection trigger
  ("several related memories accumulate", "a belief changes substantially",
  "repeated Rabbit Hole activity", "an important contradiction appears", "a
  major Founder message arrives", ...) already flows through a memory being
  formed with an importance that reflects exactly that significance
  (app.services.memory's per-handler importance tables) — so reusing that
  already-computed signal, rather than re-deriving significance from the
  event log a second time, is what keeps this mechanical and covers nearly
  the whole listed trigger set from one hook point.
- :func:`maybe_reflect` is called once per activation, from
  ``app.services.orchestrator.run_next_event`` (which has the settings and
  provider a model call needs), right after memory selection for that turn.
  It only checks whether the *acting* agent's accumulated pressure has
  crossed the threshold — a bystander's pressure waits for that bystander's
  own next activation, the same way Packet 7's memory/interest bookkeeping
  already only touches the activating agent's turn.

Retrieval (:func:`retrieve_relevant`) is the read side: a small, scored slice
of an agent's own reflections shown in its context, using the same
RECENCY + IMPORTANCE (+ a keyword-relevance bonus) principles
``app.services.memory.retrieve_relevant`` already established — never the
whole table.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agents import Agent, AgentBelief
from app.db.models.conversations import Conversation
from app.db.models.rabbit_holes import RabbitHole, RabbitHoleMember
from app.db.models.reflection import AgentReflection
from app.db.models.research import ResearchSession
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.enums import ConversationStatus, EventType, ReflectionStatus, ResearchStatus
from app.providers.llm import LLMError, LLMProvider
from app.schemas.reflection import ReflectionSynthesis
from app.services.events import record_event
from app.services.exposure import exposed_entity_ids
from app.services.telemetry import record_llm_run
from app.services.wall import keywords as _keywords

PROMPT_VERSION = "reflection_synthesis.v1"

#: How much of a touched memory's importance (0-100) becomes reflection
#: pressure. A single founder-message memory (importance 80) alone
#: contributes 40 — a real nudge but not an instant trigger; two or three
#: ordinary significant memories (importance ~45-60) accumulated across a
#: handful of turns is what actually crosses the default threshold of 100 —
#: "several related memories accumulate", not "one thing happened".
_MEMORY_PRESSURE_SCALE = 0.5

#: At most one reflection fires per agent per simulated day, regardless of
#: how much pressure has accumulated — the mechanical half of "avoid
#: reflection spam". Pressure keeps accumulating past the threshold rather
#: than being capped, so a very significant day still reflects promptly the
#: next time this agent is checked.
_MAX_REFLECTIONS_PER_AGENT_PER_DAY = 1

#: Retrieval scoring weights, mirroring app.services.memory's — importance
#: and recency dominate, with a flat bonus for genuinely matching the topic
#: in play this turn.
_IMPORTANCE_WEIGHT = 0.55
_RECENCY_WEIGHT = 0.35
_KEYWORD_BONUS_PER_WORD = 0.15

#: A reflection surfaced this recently was not really "recalled" — only a
#: genuine gap is worth a REFLECTION_RECALLED event, mirroring
#: app.services.memory._RECALL_LOG_GAP_DAYS.
_RECALL_LOG_GAP_DAYS = 2

#: How many of each kind of real prior experience a reflection is grounded
#: in — small and bounded on purpose (§ Part F token efficiency): a
#: reflection is a compact conclusion over a compact, relevant slice, never
#: the agent's whole history.
_CANDIDATE_LIMIT = 6
_REFLECTION_CANDIDATE_LIMIT = 4

SYSTEM_PROMPT = """You are forming a reflection: a short, higher-level pattern you are
noticing across several of your own real experiences below — not a summary of
any one of them, and not a restatement of what already happened.

A good reflection says something that was not explicit in any single item
below — a connection, a recurring question, a shift in what seems to matter.
A bad reflection just restates one item, or lists several without noticing
anything about them together.

Cite only real ids shown below in [brackets], in the matching source_*_ids
list — never invent one. Do not narrate your reasoning; return only the
conclusion itself."""


def accumulate_pressure(session: Session, agent_id: str, importance: float, clock: SimulationClock) -> None:
    """Nudge one agent's reflection pressure from one memory being formed or
    reinforced. Called from app.services.memory._upsert — see module
    docstring for why that single hook point covers nearly every listed
    trigger signal."""
    agent = session.scalars(select(Agent).where(Agent.agent_id == agent_id)).first()
    if agent is None:
        return
    agent.reflection_pressure += importance * _MEMORY_PRESSURE_SCALE


def maybe_reflect(
    session: Session,
    agent: Agent,
    clock: SimulationClock,
    correlation_id: str,
    settings: Settings,
    llm_provider: LLMProvider,
) -> AgentReflection | None:
    """Check whether this agent's accumulated significance has crossed the
    threshold and, if so, actually form a reflection.

    Mechanical and testable per the spec: a real float compared to a real
    Settings threshold, nothing here asks a model whether it "feels" like
    reflecting.
    """
    if agent.reflection_pressure < settings.reflection_significance_threshold:
        return None
    if agent.last_reflection_sim_day == clock.current_day:
        return None  # _MAX_REFLECTIONS_PER_AGENT_PER_DAY

    candidates = _gather_candidates(session, agent.agent_id, clock, settings)
    if not any(candidates.values()):
        return None  # pressure crossed but nothing real to ground a reflection in yet

    reflection = _generate(session, agent, clock, correlation_id, settings, llm_provider, candidates)
    if reflection is None:
        return None  # model failed to cite anything real — do not fabricate provenance

    agent.reflection_pressure = max(0.0, agent.reflection_pressure - settings.reflection_significance_threshold)
    agent.last_reflection_sim_day = clock.current_day
    return reflection


def _gather_candidates(
    session: Session, agent_id: str, clock: SimulationClock, settings: Settings
) -> dict[str, list]:
    """A compact, relevant slice of this agent's own real prior experience —
    RECENCY + IMPORTANCE, the same principles memory retrieval already uses,
    never the agent's whole history (§ Part A/F)."""
    from app.services.memory import retrieve_relevant as retrieve_memories

    memories = retrieve_memories(
        session, agent_id, clock=clock, limit=_CANDIDATE_LIMIT, mark_recalled=False
    )

    research = session.scalars(
        select(ResearchSession)
        .where(ResearchSession.agent_id == agent_id, ResearchSession.status == ResearchStatus.COMPLETED)
        .order_by(ResearchSession.created_at.desc(), ResearchSession.id.desc())
        .limit(_CANDIDATE_LIMIT)
    ).all()

    beliefs = session.scalars(
        select(AgentBelief)
        .where(AgentBelief.agent_id == agent_id)
        .order_by(AgentBelief.updated_at.desc().nulls_last(), AgentBelief.created_at.desc())
        .limit(_CANDIDATE_LIMIT)
    ).all()

    convo_ids = exposed_entity_ids(session, agent_id, "conversation_message")
    conversations: list[Conversation] = []
    if convo_ids:
        conversations = session.scalars(
            select(Conversation)
            .where(
                Conversation.status == ConversationStatus.ENDED,
                Conversation.participant_ids.isnot(None),
            )
            .order_by(Conversation.id.desc())
            .limit(30)
        ).all()
        conversations = [c for c in conversations if agent_id in (c.participant_ids or [])][
            :_CANDIDATE_LIMIT
        ]

    member_hole_ids = list(
        session.scalars(
            select(RabbitHoleMember.rabbit_hole_id).where(
                RabbitHoleMember.agent_id == agent_id, RabbitHoleMember.left_at.is_(None)
            )
        )
    )
    rabbit_holes = (
        session.scalars(
            select(RabbitHole)
            .where(RabbitHole.id.in_(member_hole_ids))
            .order_by(RabbitHole.last_activity.desc().nulls_last(), RabbitHole.id.desc())
            .limit(_CANDIDATE_LIMIT)
        ).all()
        if member_hole_ids
        else []
    )

    wall_posts = session.scalars(
        select(ResearchWallPost)
        .where(ResearchWallPost.agent_id == agent_id)
        .order_by(ResearchWallPost.created_at.desc(), ResearchWallPost.id.desc())
        .limit(_CANDIDATE_LIMIT)
    ).all()

    prior_reflections = session.scalars(
        select(AgentReflection)
        .where(AgentReflection.agent_id == agent_id, AgentReflection.status == ReflectionStatus.ACTIVE)
        .order_by(AgentReflection.id.desc())
        .limit(min(_REFLECTION_CANDIDATE_LIMIT, settings.max_context_reflections + 2))
    ).all()

    return {
        "memories": memories,
        "research": research,
        "beliefs": beliefs,
        "conversations": conversations,
        "rabbit_holes": rabbit_holes,
        "wall_posts": wall_posts,
        "reflections": prior_reflections,
    }


def _render_prompt(agent: Agent, clock: SimulationClock, candidates: dict[str, list]) -> str:
    lines = [f"AGENT_ID: {agent.agent_id}", f"DAY: {clock.current_day}"]

    memories = candidates["memories"]
    if memories:
        lines.append("RECENT MEMORIES:")
        lines += [f"  [{m.id}] [{m.memory_type.value}] {_clip(m.content, 180)}" for m in memories]

    research = candidates["research"]
    if research:
        lines.append("RECENT RESEARCH:")
        lines += [
            f"  [{r.research_id}] ({r.evidence_strength.value}) {_clip(r.question, 140)}: "
            f"{_clip(r.interpretation or '', 140)}"
            for r in research
        ]

    beliefs = candidates["beliefs"]
    if beliefs:
        lines.append("YOUR BELIEFS:")
        lines += [
            f"  [{b.id}] ({b.status.value}, confidence={b.confidence:.0f}) {_clip(b.statement, 140)}"
            for b in beliefs
        ]

    conversations = candidates["conversations"]
    if conversations:
        lines.append("RECENT CONVERSATIONS:")
        lines += [
            f"  [{c.id}] ({c.trigger_type.value}) about \"{_clip(c.current_subject or '', 100)}\""
            for c in conversations
        ]

    holes = candidates["rabbit_holes"]
    if holes:
        lines.append("RABBIT HOLES YOU ARE PART OF:")
        lines += [
            f"  [{h.id}] \"{_clip(h.title, 100)}\" status={h.status.value} evidence={h.evidence_strength.value}"
            for h in holes
        ]

    posts = candidates["wall_posts"]
    if posts:
        lines.append("YOUR OWN WALL ACTIVITY:")
        lines += [f"  [{p.id}] [{p.post_type.value}] {_clip(p.content, 140)}" for p in posts]

    prior = candidates["reflections"]
    if prior:
        lines.append("YOUR EARLIER REFLECTIONS:")
        lines += [f"  [{r.id}] {r.topic}: {_clip(r.summary, 140)}" for r in prior]

    lines.append(
        "\nForm one reflection: a pattern across two or more of the above, not a "
        "restatement of just one item. Cite only real ids shown above."
    )
    return "\n".join(lines)


def _generate(
    session: Session,
    agent: Agent,
    clock: SimulationClock,
    correlation_id: str,
    settings: Settings,
    llm_provider: LLMProvider,
    candidates: dict[str, list],
) -> AgentReflection | None:
    prompt = _render_prompt(agent, clock, candidates)
    try:
        result = llm_provider.complete(
            system=SYSTEM_PROMPT,
            user=prompt,
            model=settings.research_model,
            purpose="reflection",
            output_type=ReflectionSynthesis,
        )
    except LLMError:
        return None

    record_llm_run(
        session, result, purpose="reflection", agent_id=agent.agent_id, prompt_version=PROMPT_VERSION,
    )
    synthesis: ReflectionSynthesis = result.output

    valid_memory_ids = {m.id for m in candidates["memories"]}
    valid_research_ids = {r.research_id for r in candidates["research"]}
    valid_belief_ids = {b.id for b in candidates["beliefs"]}
    valid_conversation_ids = {c.id for c in candidates["conversations"]}
    valid_hole_ids = {h.id for h in candidates["rabbit_holes"]}
    valid_wall_ids = {p.id for p in candidates["wall_posts"]}
    valid_reflection_ids = {r.id for r in candidates["reflections"]}

    source_memory_ids = [i for i in synthesis.source_memory_ids if i in valid_memory_ids]
    source_research_ids = [i for i in synthesis.source_research_ids if i in valid_research_ids]
    source_belief_ids = [i for i in synthesis.source_belief_ids if i in valid_belief_ids]
    source_conversation_ids = [i for i in synthesis.source_conversation_ids if i in valid_conversation_ids]
    source_rabbit_hole_ids = [i for i in synthesis.source_rabbit_hole_ids if i in valid_hole_ids]
    source_wall_post_ids = [i for i in synthesis.source_wall_post_ids if i in valid_wall_ids]
    source_reflection_ids = [i for i in synthesis.source_reflection_ids if i in valid_reflection_ids]

    has_provenance = any((
        source_memory_ids, source_research_ids, source_belief_ids, source_conversation_ids,
        source_rabbit_hole_ids, source_wall_post_ids, source_reflection_ids,
    ))
    if not has_provenance:
        # A reflection with no real, verifiable source is exactly the
        # "untraceable fact" §2/§6 forbid — never persisted, fabricated
        # citations included.
        return None

    supersedes_id = (
        synthesis.supersedes_reflection_id
        if synthesis.supersedes_reflection_id in valid_reflection_ids
        else None
    )

    reflection = AgentReflection(
        agent_id=agent.agent_id,
        simulation_day=clock.current_day,
        topic=synthesis.topic[:200],
        summary=synthesis.summary[:1000],
        importance=min(100.0, agent.reflection_pressure),
        confidence=max(0.0, min(100.0, synthesis.confidence if synthesis.confidence is not None else 50.0)),
        status=ReflectionStatus.ACTIVE,
        open_question=(synthesis.open_question or None),
        suggested_follow_up=(synthesis.suggested_follow_up or None),
        supersedes_reflection_id=supersedes_id,
        source_memory_ids=source_memory_ids,
        source_research_ids=source_research_ids,
        source_belief_ids=source_belief_ids,
        source_conversation_ids=source_conversation_ids,
        source_rabbit_hole_ids=source_rabbit_hole_ids,
        source_wall_post_ids=source_wall_post_ids,
        source_reflection_ids=source_reflection_ids,
        is_fixture=result.is_fixture,
    )
    session.add(reflection)
    session.flush()

    if supersedes_id is not None:
        superseded = session.get(AgentReflection, supersedes_id)
        if superseded is not None:
            superseded.status = ReflectionStatus.SUPERSEDED

    record_event(
        session,
        event_type=EventType.REFLECTION_CREATED,
        agent_id=agent.agent_id,
        payload={
            "reflection_id": reflection.id,
            "topic": reflection.topic,
            "pressure_at_trigger": round(agent.reflection_pressure, 2),
            "threshold": settings.reflection_significance_threshold,
            "source_counts": {
                "memories": len(source_memory_ids),
                "research": len(source_research_ids),
                "beliefs": len(source_belief_ids),
                "conversations": len(source_conversation_ids),
                "rabbit_holes": len(source_rabbit_hole_ids),
                "wall_posts": len(source_wall_post_ids),
                "reflections": len(source_reflection_ids),
            },
        },
        entity_type="reflection",
        entity_id=str(reflection.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    return reflection


# --------------------------------------------------------------------------
# Retrieval — the read side, shown in an agent's own context
# --------------------------------------------------------------------------


def retrieve_relevant(
    session: Session,
    agent_id: str,
    *,
    clock: SimulationClock,
    limit: int = 3,
    keywords: set[str] | None = None,
    mark_recalled: bool = True,
) -> list[AgentReflection]:
    """The bounded, scored slice of an agent's own reflections shown this
    turn — never the whole table, and never another agent's reflections:
    a reflection is this agent's own pattern-recognition, not shared
    knowledge (unlike the Research Wall, nothing here is public)."""
    active = session.scalars(
        select(AgentReflection)
        .where(AgentReflection.agent_id == agent_id, AgentReflection.status == ReflectionStatus.ACTIVE)
        .order_by(AgentReflection.id.desc())
        .limit(50)
    ).all()
    if not active:
        return []

    keywords = keywords or set()
    scored: list[tuple[float, AgentReflection]] = []
    for r in active:
        days_old = max(0, clock.current_day - r.simulation_day)
        recency = 1.0 / (1.0 + days_old)
        score = (r.importance / 100.0) * _IMPORTANCE_WEIGHT + recency * _RECENCY_WEIGHT
        if keywords:
            overlap = len(keywords & (_keywords(r.topic) | _keywords(r.summary)))
            score += overlap * _KEYWORD_BONUS_PER_WORD
        scored.append((score, r))

    scored.sort(key=lambda pair: (-pair[0], -pair[1].id))
    chosen = [r for _, r in scored[:limit]]

    if mark_recalled and chosen:
        _mark_recalled(session, agent_id, chosen, clock)
    return chosen


def _mark_recalled(
    session: Session, agent_id: str, reflections: list[AgentReflection], clock: SimulationClock
) -> None:
    genuinely_recalled = []
    for r in reflections:
        last_day = r.last_accessed_sim_day
        is_stale = last_day is None or (clock.current_day - last_day) >= _RECALL_LOG_GAP_DAYS
        if is_stale and (clock.current_day - r.simulation_day) >= _RECALL_LOG_GAP_DAYS:
            genuinely_recalled.append(r.id)
        r.last_accessed_sim_day = clock.current_day

    if genuinely_recalled:
        record_event(
            session,
            event_type=EventType.REFLECTION_RECALLED,
            agent_id=agent_id,
            payload={"reflection_ids": genuinely_recalled},
            clock=clock,
        )


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
