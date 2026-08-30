"""RUN NEXT EVENT — one activation, start to finish.

The order is fixed and the whitelist is enforced at every step:

    scheduler picks an agent
      -> context builder renders a bounded prompt
      -> provider returns a structured decision
      -> schema validation (Pydantic)
      -> semantic validation (does this reference things that exist, and is it
         within budget?)
      -> whitelisted executor performs the state changes
      -> event log + telemetry, in the same transaction

A decision that fails validation gets at most one correction attempt. After
that the run is logged as INVALID_AGENT_DECISION and the agent does nothing —
no retry spiral, and no silently executing a decision nobody validated.

START_RESEARCH is executed like any other action, but what it does is a whole
pipeline (real search, real fetch, then interpretation) rather than a single
state change — see :mod:`app.services.research`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.models.agents import Agent
from app.db.models.conversations import Conversation, Message
from app.db.models.memory import Memory
from app.db.models.rabbit_holes import RabbitHole
from app.db.models.research import ResearchSession
from app.db.models.research_provenance import Claim
from app.db.models.wall import ResearchWallPost
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock
from app.domain.enums import (
    ConversationStatus,
    ConversationTrigger,
    EventType,
    ExposureType,
    MemoryType,
    RabbitHoleStatus,
    WallPostType,
)
from app.domain.ids import new_correlation_id
from app.providers.llm import LLMError, LLMProvider, get_llm_provider
from app.providers.llm.base import LLMResult
from app.providers.research import ResearchProviderError, get_research_provider
from app.schemas.actions import (
    CONTENT_ACTIONS,
    IN_CONVERSATION_ACTIONS,
    NOT_IN_CONVERSATION_ACTIONS,
    SINGLETON_ACTIONS,
    ActionType,
    AgentDecision,
)
from app.services import beliefs
from app.services import clock as clock_service
from app.services import conversations as convo
from app.services import founder, rabbit_holes as rh, research, scheduler, wall
from app.services.context_builder import build_agent_context
from app.services.events import record_event
from app.services.exposure import expose, has_been_exposed
from app.services.telemetry import record_llm_run

PROMPT_VERSION = "agent_decision.v1"

#: Every action currently implemented. Anything else is rejected.
ALLOWED_ACTIONS: tuple[ActionType, ...] = tuple(ActionType)


class DecisionRejected(Exception):
    """A decision failed semantic validation."""


@dataclass
class EventOutcome:
    """What one RUN NEXT EVENT produced."""

    activated_agent_id: str | None = None
    conversation_id: int | None = None
    spoke: bool = False
    clock_advance: str | None = None
    decision: AgentDecision | None = None
    executed: list[str] = field(default_factory=list)
    rejected_reason: str | None = None
    event_ids: list[int] = field(default_factory=list)
    llm_run_id: int | None = None
    correlation_id: str | None = None
    is_fixture: bool = True
    note: str | None = None
    research: research.ResearchOutcome | None = None

    @property
    def acted(self) -> bool:
        return self.decision is not None and self.rejected_reason is None


def validate_decision(
    decision: AgentDecision,
    *,
    agent: Agent,
    present_agent_ids: tuple[str, ...],
    in_conversation: bool = False,
    session: Session | None = None,
    clock: SimulationClock | None = None,
    settings: Settings | None = None,
) -> None:
    """Semantic validation, after the schema has already been satisfied.

    Schema validation proves the shape; this proves the decision refers to a
    world that exists and stays within budget. The research budget check only
    runs when ``session``/``clock``/``settings`` are supplied — callers that
    only exercise non-research actions may omit them.
    """
    if decision.location is not None and decision.location not in CLUBHOUSE_LOCATIONS:
        raise DecisionRejected(
            f"location {decision.location!r} is not a clubhouse location"
        )

    seen_singletons: set[ActionType] = set()
    for action in decision.actions:
        if action.type not in ALLOWED_ACTIONS:
            raise DecisionRejected(f"action {action.type} is not available in this packet")

        if action.type in IN_CONVERSATION_ACTIONS and not in_conversation:
            raise DecisionRejected(
                f"{action.type.value} requires being in an open conversation"
            )
        if action.type in NOT_IN_CONVERSATION_ACTIONS and in_conversation:
            raise DecisionRejected(f"cannot {action.type.value} while in a conversation")

        if action.type in SINGLETON_ACTIONS:
            if action.type in seen_singletons:
                raise DecisionRejected(f"at most one {action.type.value} action per decision")
            seen_singletons.add(action.type)

        if action.type is ActionType.START_CONVERSATION:
            if in_conversation:
                raise DecisionRejected("a conversation is already open")
            if not action.target_agent_id:
                raise DecisionRejected("START_CONVERSATION requires a target_agent_id")

        if action.type is ActionType.ASK_QUESTION and not action.target_agent_id:
            raise DecisionRejected("ASK_QUESTION requires a target_agent_id")

        if action.type is ActionType.START_RESEARCH:
            if session is not None and clock is not None and settings is not None:
                reason = research.check_research_budget(session, agent, clock, settings)
                if reason:
                    raise DecisionRejected(reason)

        if action.target_agent_id is not None:
            if action.target_agent_id == agent.agent_id:
                raise DecisionRejected("an agent cannot address itself")
            if action.target_agent_id not in present_agent_ids:
                raise DecisionRejected(
                    f"unknown target_agent_id {action.target_agent_id!r}"
                )

        if action.type in CONTENT_ACTIONS:
            if not (action.content or "").strip():
                raise DecisionRejected(f"{action.type.value} requires content")

        if session is not None:
            _validate_wall_and_rabbit_hole_action(session, agent, action)


def _validate_wall_and_rabbit_hole_action(session: Session, agent: Agent, action) -> None:
    """The part of semantic validation that needs a database: every id an
    action names must be real, and the anti-repetition guards live here."""

    # target_research_id is carried by several action types (POST_TO_WALL,
    # CREATE_RABBIT_HOLE, CONTRIBUTE_TO_RABBIT_HOLE); FORM_BELIEF and
    # REVISE_BELIEF apply their own stricter rules further down instead.
    if action.target_research_id is not None and action.type not in (
        ActionType.FORM_BELIEF,
        ActionType.REVISE_BELIEF,
    ):
        rs = session.scalars(
            select(ResearchSession).where(
                ResearchSession.research_id == action.target_research_id
            )
        ).first()
        if rs is None:
            raise DecisionRejected(f"unknown research session {action.target_research_id!r}")
        if rs.agent_id != agent.agent_id and not has_been_exposed(
            session, agent.agent_id, "research_session", action.target_research_id
        ):
            raise DecisionRejected(
                "no real exposure to that research session — read a wall post citing "
                "it, or join a rabbit hole it's linked into, first"
            )

    if action.type is ActionType.POST_TO_WALL:
        if action.wall_post_type is None:
            raise DecisionRejected("POST_TO_WALL requires wall_post_type")
        if action.wall_post_type is WallPostType.CONNECTION:
            if not action.target_wall_post_id:
                raise DecisionRejected("a CONNECTION post requires target_wall_post_id")
            if session.get(ResearchWallPost, action.target_wall_post_id) is None:
                raise DecisionRejected(f"unknown wall post {action.target_wall_post_id!r}")
            if wall.already_connected(session, agent.agent_id, action.target_wall_post_id):
                raise DecisionRejected(
                    "already posted a connection to this post — "
                    "recently explored connections are not repeated"
                )

    if action.type is ActionType.READ_WALL_POST:
        if not action.target_wall_post_id:
            raise DecisionRejected("READ_WALL_POST requires target_wall_post_id")
        if session.get(ResearchWallPost, action.target_wall_post_id) is None:
            raise DecisionRejected(f"unknown wall post {action.target_wall_post_id!r}")

    if action.type is ActionType.CREATE_RABBIT_HOLE:
        if not (action.title or "").strip():
            raise DecisionRejected("CREATE_RABBIT_HOLE requires a title")
        if rh.has_similar_active_title(session, action.title):
            raise DecisionRejected(
                f"a rabbit hole named {action.title!r} is already open — "
                "join or contribute to it instead of duplicating it"
            )
        if action.target_wall_post_id and session.get(ResearchWallPost, action.target_wall_post_id) is None:
            raise DecisionRejected(f"unknown wall post {action.target_wall_post_id!r}")

    if action.type in (
        ActionType.JOIN_RABBIT_HOLE,
        ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
        ActionType.LEAVE_RABBIT_HOLE,
        ActionType.RESOLVE_RABBIT_HOLE,
    ):
        if not action.target_rabbit_hole_id:
            raise DecisionRejected(f"{action.type.value} requires target_rabbit_hole_id")
        hole = session.get(RabbitHole, action.target_rabbit_hole_id)
        if hole is None:
            raise DecisionRejected(f"unknown rabbit hole {action.target_rabbit_hole_id!r}")
        if action.type is ActionType.JOIN_RABBIT_HOLE:
            if hole.status in (RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED):
                raise DecisionRejected(f"rabbit hole {hole.id} is {hole.status.value.lower()}")
            if rh.is_member(session, hole.id, agent.agent_id):
                raise DecisionRejected(f"already a member of rabbit hole {hole.id}")
        if action.type in (ActionType.CONTRIBUTE_TO_RABBIT_HOLE, ActionType.LEAVE_RABBIT_HOLE, ActionType.RESOLVE_RABBIT_HOLE):
            if not rh.is_member(session, hole.id, agent.agent_id):
                raise DecisionRejected(
                    f"not a member of rabbit hole {hole.id} — JOIN_RABBIT_HOLE first"
                )
        if action.type is ActionType.CONTRIBUTE_TO_RABBIT_HOLE:
            if hole.status in (RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED):
                raise DecisionRejected(f"rabbit hole {hole.id} is {hole.status.value.lower()}")

    if action.type is ActionType.CHALLENGE_CLAIM:
        if not action.target_claim_id:
            raise DecisionRejected("CHALLENGE_CLAIM requires target_claim_id")
        claim = session.get(Claim, action.target_claim_id)
        if claim is None:
            raise DecisionRejected(f"unknown claim {action.target_claim_id!r}")
        owner = session.scalars(
            select(ResearchSession.agent_id).where(
                ResearchSession.research_id == claim.research_session_id
            )
        ).first()
        if owner == agent.agent_id:
            raise DecisionRejected("cannot challenge your own claim")

    if action.type is ActionType.FORM_BELIEF:
        if not action.target_research_id:
            raise DecisionRejected("FORM_BELIEF requires target_research_id")
        rs = session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == action.target_research_id)
        ).first()
        if rs is None:
            raise DecisionRejected(f"unknown research session {action.target_research_id!r}")
        if rs.agent_id != agent.agent_id:
            raise DecisionRejected("can only FORM_BELIEF from your own research")
        if rs.status.value != "COMPLETED":
            raise DecisionRejected(f"research session {rs.research_id} is not completed")

    if action.type is ActionType.REVISE_BELIEF:
        if not action.target_belief_id:
            raise DecisionRejected("REVISE_BELIEF requires target_belief_id")
        if action.belief_relation is None:
            raise DecisionRejected("REVISE_BELIEF requires belief_relation")
        if beliefs.owned_by(session, agent.agent_id, action.target_belief_id) is None:
            raise DecisionRejected(f"no belief {action.target_belief_id!r} owned by {agent.agent_id}")
        basis_count = sum(
            1 for x in (action.target_research_id, action.target_wall_post_id, action.target_claim_id) if x
        )
        if basis_count != 1:
            raise DecisionRejected(
                "REVISE_BELIEF requires exactly one of target_research_id / "
                "target_wall_post_id / target_claim_id as the new evidence"
            )
        if action.target_research_id:
            rs = session.scalars(
                select(ResearchSession).where(
                    ResearchSession.research_id == action.target_research_id
                )
            ).first()
            if rs is None:
                raise DecisionRejected(f"unknown research session {action.target_research_id!r}")
            if rs.agent_id != agent.agent_id and not has_been_exposed(
                session, agent.agent_id, "research_session", action.target_research_id
            ):
                raise DecisionRejected("no real exposure to that research session")
        if action.target_wall_post_id:
            if session.get(ResearchWallPost, action.target_wall_post_id) is None:
                raise DecisionRejected(f"unknown wall post {action.target_wall_post_id!r}")
            if not has_been_exposed(session, agent.agent_id, "research_wall", action.target_wall_post_id):
                raise DecisionRejected("must READ_WALL_POST before citing it as belief evidence")
        if action.target_claim_id:
            if session.get(Claim, action.target_claim_id) is None:
                raise DecisionRejected(f"unknown claim {action.target_claim_id!r}")
            if not has_been_exposed(session, agent.agent_id, "claim", action.target_claim_id):
                raise DecisionRejected("no real exposure to that claim")

    if action.type is ActionType.RETIRE_BELIEF:
        if not action.target_belief_id:
            raise DecisionRejected("RETIRE_BELIEF requires target_belief_id")
        if beliefs.owned_by(session, agent.agent_id, action.target_belief_id) is None:
            raise DecisionRejected(f"no belief {action.target_belief_id!r} owned by {agent.agent_id}")


def execute_decision(
    session: Session,
    agent: Agent,
    decision: AgentDecision,
    clock: SimulationClock,
    correlation_id: str,
    conversation: Conversation | None,
    settings: Settings,
    llm_provider: LLMProvider,
) -> tuple[list[str], bool, research.ResearchOutcome | None]:
    """Perform the state changes a validated decision calls for.

    Returns what was performed, whether the agent spoke (for the conversation
    engine), and the research outcome if a START_RESEARCH action ran.
    """
    performed: list[str] = []
    spoke = False
    research_outcome: research.ResearchOutcome | None = None

    agent.current_activity = decision.activity
    if decision.location:
        agent.current_location = decision.location

    for action in decision.actions:
        if action.type is ActionType.WRITE_NOTE:
            session.add(
                Memory(
                    agent_id=agent.agent_id,
                    memory_type=MemoryType.EPISODIC,
                    content=action.content or "",
                    related_ids=[],
                )
            )
        elif action.type is ActionType.SPEAK and conversation is not None:
            convo.record_utterance(
                session,
                conversation,
                agent.agent_id,
                action.content or "",
                clock,
                correlation_id=correlation_id,
            )
            spoke = True
        elif action.type is ActionType.LEAVE_CONVERSATION and conversation is not None:
            convo.leave(session, conversation, agent.agent_id)
        elif action.type is ActionType.START_CONVERSATION:
            new_conversation = convo.start_conversation(
                session,
                trigger=ConversationTrigger.RANDOM_SOCIAL,
                participant_ids=[agent.agent_id, action.target_agent_id],
                clock=clock,
                correlation_id=correlation_id,
            )
            new_conversation.correlation_id = correlation_id
            convo.record_utterance(
                session,
                new_conversation,
                agent.agent_id,
                action.content or "",
                clock,
                correlation_id=correlation_id,
            )
            spoke = True
        elif action.type is ActionType.START_RESEARCH:
            try:
                research_provider = get_research_provider(settings)
            except ResearchProviderError as exc:
                research_outcome = research.record_unavailable_session(
                    session,
                    agent,
                    action.content or "",
                    clock,
                    correlation_id,
                    f"research provider unavailable: {exc}",
                )
            else:
                research_outcome = research.start_research(
                    session,
                    agent,
                    action.content or "",
                    clock,
                    correlation_id,
                    settings,
                    llm_provider,
                    research_provider,
                )
        elif action.type in (ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE):
            message = Message(
                sender_agent_id=agent.agent_id,
                recipient_agent_id=action.target_agent_id,
                content=action.content or "",
            )
            session.add(message)
            session.flush()
            expose(
                session,
                agent_id=agent.agent_id,
                entity_type="message",
                entity_id=message.id,
                exposure_type=ExposureType.CREATED,
            )
        elif action.type is ActionType.POST_TO_WALL:
            wall.post_to_wall(
                session, agent.agent_id, action.wall_post_type, action.content or "",
                clock, correlation_id,
                related_research_id=action.target_research_id,
                related_wall_post_id=action.target_wall_post_id,
                related_rabbit_hole_id=action.target_rabbit_hole_id,
            )
        elif action.type is ActionType.READ_WALL_POST:
            post = session.get(ResearchWallPost, action.target_wall_post_id)
            wall.read_wall_post(session, agent.agent_id, post, clock, correlation_id)
        elif action.type is ActionType.CREATE_RABBIT_HOLE:
            rh.create(
                session, agent.agent_id, action.title or "", action.content or "",
                clock, correlation_id,
                related_research_id=action.target_research_id,
                related_wall_post_id=action.target_wall_post_id,
            )
        elif action.type is ActionType.JOIN_RABBIT_HOLE:
            rh.join(session, action.target_rabbit_hole_id, agent.agent_id, clock, correlation_id)
        elif action.type is ActionType.CONTRIBUTE_TO_RABBIT_HOLE:
            rh.contribute(
                session, action.target_rabbit_hole_id, agent.agent_id, action.content or "",
                clock, correlation_id, research_id=action.target_research_id,
            )
        elif action.type is ActionType.LEAVE_RABBIT_HOLE:
            rh.leave(session, action.target_rabbit_hole_id, agent.agent_id, clock, correlation_id)
        elif action.type is ActionType.RESOLVE_RABBIT_HOLE:
            rh.resolve(
                session, action.target_rabbit_hole_id, agent.agent_id, action.content or "",
                clock, correlation_id,
            )
        elif action.type is ActionType.CHALLENGE_CLAIM:
            claim = session.get(Claim, action.target_claim_id)
            research.challenge_claim(
                session, agent.agent_id, claim, action.content or "", clock, correlation_id
            )
        elif action.type is ActionType.FORM_BELIEF:
            rs = session.scalars(
                select(ResearchSession).where(
                    ResearchSession.research_id == action.target_research_id
                )
            ).one()
            initial_confidence = rs.confidence if rs.confidence is not None else 50.0
            beliefs.form(
                session, agent.agent_id, action.content or "", action.target_research_id,
                initial_confidence, clock, correlation_id,
            )
        elif action.type is ActionType.REVISE_BELIEF:
            belief = beliefs.owned_by(session, agent.agent_id, action.target_belief_id)
            if action.target_research_id:
                basis_type, basis_id = "research_session", action.target_research_id
            elif action.target_wall_post_id:
                basis_type, basis_id = "wall_post", str(action.target_wall_post_id)
            else:
                basis_type, basis_id = "claim", str(action.target_claim_id)
            beliefs.revise(
                session, agent.agent_id, belief, action.belief_relation, basis_type, basis_id,
                action.content, clock, correlation_id,
            )
        elif action.type is ActionType.RETIRE_BELIEF:
            belief = beliefs.owned_by(session, agent.agent_id, action.target_belief_id)
            beliefs.retire(session, agent.agent_id, belief, action.content or "", clock, correlation_id)
        # REST / OBSERVE / LISTEN_TO_MUSIC / DRINK_COFFEE / DO_NOTHING are fully
        # expressed by the activity and location already applied above.
        agent.interaction_target = action.target_agent_id
        performed.append(action.type.value)

    if not decision.actions:
        agent.interaction_target = None

    return performed, spoke, research_outcome


def run_next_event(
    session: Session,
    *,
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    seed: str = "",
    auto_advance: bool = False,
) -> EventOutcome:
    """Activate one agent and carry its decision through to persisted state.

    The caller commits. Everything this writes — state, events, telemetry —
    belongs to one transaction.
    """
    settings = settings or get_settings()
    provider = provider or get_llm_provider(settings)

    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is None:
        return EventOutcome(note="No simulation clock. Run scripts/seed_agents.py first.")
    if clock.is_paused:
        return EventOutcome(note="Simulation is paused.")

    # The Founder's mail reaches people before anyone decides anything.
    founder.deliver_pending(session, clock)

    conversation = convo.active_conversation(session)

    # The day opens with everyone in the room and no agenda.
    if (
        conversation is None
        and clock.current_period == clock_service.FIRST_PERIOD
        and not convo.morning_gathering_held_today(session, clock)
    ):
        gathering_correlation = new_correlation_id()
        conversation = convo.start_morning_gathering(
            session, clock, correlation_id=gathering_correlation
        )
        conversation.correlation_id = gathering_correlation

    candidate = None
    if conversation is not None:
        speaker_id = convo.next_speaker(session, conversation)
        if speaker_id is None:
            convo.close(session, conversation, clock, "no participants left",
                        correlation_id=conversation.correlation_id)
            conversation = None
        else:
            agent = session.scalars(
                select(Agent).where(Agent.agent_id == speaker_id)
            ).one()
            correlation_id = conversation.correlation_id or new_correlation_id()
    if conversation is None:
        candidate = scheduler.next_agent(session, clock, settings, seed=seed)
        if candidate is None:
            if auto_advance:
                advance = clock_service.advance(session, clock)
                return EventOutcome(
                    clock_advance=str(advance),
                    note=f"Period spent; clock advanced {advance}.",
                )
            return EventOutcome(
                note=(
                    f"No agent is eligible to act in day {clock.current_day} "
                    f"{clock.current_period}. Everyone with a reason to act has "
                    "acted and the period is spent. Pass --advance (or use "
                    "run_day.py) to move the clock on."
                )
            )
        agent = session.scalars(
            select(Agent).where(Agent.agent_id == candidate.agent_id)
        ).one()
        correlation_id = new_correlation_id()

    outcome = EventOutcome(
        activated_agent_id=agent.agent_id,
        conversation_id=conversation.id if conversation is not None else None,
        correlation_id=correlation_id,
        is_fixture=provider.is_fixture,
    )

    context = build_agent_context(
        session,
        agent,
        clock,
        settings,
        available_actions=tuple(a.value for a in ALLOWED_ACTIONS),
        conversation=conversation,
    )

    # Showing a message to an agent is delivering it: mark it read so it stops
    # inflating this agent's activation score, and record the exposure that
    # says this agent — and only this agent — has now seen it.
    for message in context.delivered_messages:
        message.read_at = utcnow()
        expose(
            session,
            agent_id=agent.agent_id,
            entity_type="message",
            entity_id=message.id,
            exposure_type=ExposureType.DIRECT_MESSAGE,
        )

    woke = record_event(
        session,
        event_type=EventType.AGENT_WOKE,
        agent_id=agent.agent_id,
        payload={
            "activation_score": round(candidate.score, 3) if candidate else None,
            "components": (
                {k: round(v, 3) for k, v in candidate.components.items()}
                if candidate
                else {"conversation_turn": 1.0}
            ),
            "approx_context_tokens": context.approx_tokens,
            "conversation_id": conversation.id if conversation is not None else None,
        },
        correlation_id=correlation_id,
        clock=clock,
    )
    outcome.event_ids.append(woke.id)

    # One call, then at most one correction attempt.
    result: LLMResult | None = None
    rejection: str | None = None
    for attempt in range(2):
        try:
            result = provider.complete(
                system=context.system,
                user=context.user
                if attempt == 0
                else f"{context.user}\n\nYOUR PREVIOUS DECISION WAS REJECTED: {rejection}\nReturn a valid decision.",
                model=settings.agent_model,
                purpose="agent_decision",
                output_type=AgentDecision,
            )
        except LLMError as exc:
            outcome.rejected_reason = f"provider error: {exc}"
            break

        try:
            validate_decision(
                result.output,
                agent=agent,
                present_agent_ids=context.present_agent_ids,
                in_conversation=conversation is not None,
                session=session,
                clock=clock,
                settings=settings,
            )
        except DecisionRejected as exc:
            rejection = str(exc)
            record_llm_run(
                session, result, purpose="agent_decision", agent_id=agent.agent_id,
                prompt_version=PROMPT_VERSION,
            )
            if attempt == 1:
                outcome.rejected_reason = rejection
            continue

        run = record_llm_run(
            session, result, purpose="agent_decision", agent_id=agent.agent_id,
            prompt_version=PROMPT_VERSION,
        )
        outcome.llm_run_id = run.id
        outcome.decision = result.output
        break

    if outcome.decision is None:
        invalid = record_event(
            session,
            event_type=EventType.INVALID_AGENT_DECISION,
            agent_id=agent.agent_id,
            payload={"reason": outcome.rejected_reason or rejection or "unknown"},
            correlation_id=correlation_id,
            causation_id=woke.id,
            clock=clock,
        )
        outcome.event_ids.append(invalid.id)
        outcome.rejected_reason = outcome.rejected_reason or rejection
        # Falling back to doing nothing is itself the outcome; no state changes.
        # A rejected turn still counts as a pass in the room.
        if conversation is not None:
            _after_turn(session, conversation, clock, settings, spoke=False)
        return outcome

    outcome.executed, outcome.spoke, outcome.research = execute_decision(
        session, agent, outcome.decision, clock, correlation_id, conversation,
        settings, provider,
    )
    acted = record_event(
        session,
        event_type=EventType.AGENT_ACTED,
        agent_id=agent.agent_id,
        payload={
            "summary": outcome.decision.summary,
            "activity": outcome.decision.activity,
            "location": agent.current_location,
            "actions": outcome.executed,
            "public_dialogue": outcome.decision.public_dialogue,
            "is_fixture": provider.is_fixture,
            "research_id": outcome.research.research_id if outcome.research else None,
        },
        correlation_id=correlation_id,
        causation_id=woke.id,
        clock=clock,
    )
    outcome.event_ids.append(acted.id)

    if conversation is not None:
        _after_turn(session, conversation, clock, settings, spoke=outcome.spoke)
    return outcome


def _after_turn(
    session: Session,
    conversation: Conversation,
    clock: SimulationClock,
    settings: Settings,
    *,
    spoke: bool,
) -> None:
    """Track the room's energy and close the conversation when it runs out.

    Silence is not failure — it is how a conversation ends naturally instead of
    running to an arbitrary turn limit every time.
    """
    if spoke:
        conversation.consecutive_silences = 0
        if conversation.status is ConversationStatus.WINDING_DOWN:
            conversation.status = ConversationStatus.ACTIVE
    else:
        conversation.consecutive_silences += 1
        if (
            conversation.consecutive_silences >= convo.SILENCES_TO_WIND_DOWN
            and conversation.status is ConversationStatus.ACTIVE
        ):
            conversation.status = ConversationStatus.WINDING_DOWN

    reason = None
    if len(conversation.participant_ids or []) < 2:
        reason = "everyone left"
    elif convo.turn_count(session, conversation) >= settings.max_conversation_turns:
        reason = "turn cap reached"
    elif (
        conversation.status is ConversationStatus.WINDING_DOWN
        and conversation.consecutive_silences > convo.SILENCES_TO_WIND_DOWN
    ):
        reason = "the room went quiet"

    if reason:
        convo.close(
            session, conversation, clock, reason,
            correlation_id=conversation.correlation_id,
        )
