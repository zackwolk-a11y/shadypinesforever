"""RUN NEXT EVENT — one activation, start to finish.

The order is fixed and the whitelist is enforced at every step:

    scheduler picks an agent
      -> context builder renders a bounded prompt
      -> provider returns a structured decision
      -> schema validation (Pydantic)
      -> semantic validation (does this reference things that exist?)
      -> whitelisted executor performs the state changes
      -> event log + telemetry, in the same transaction

A decision that fails validation gets at most one correction attempt. After
that the run is logged as INVALID_AGENT_DECISION and the agent does nothing —
no retry spiral, and no silently executing a decision nobody validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import MODEL_PRICES_USD_PER_MTOK, Settings, get_settings
from app.db.models.agents import Agent
from app.db.models.conversations import Message
from app.db.models.memory import Memory
from app.db.models.telemetry import LLMRun
from app.db.base import utcnow
from app.db.models.conversations import Conversation
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock
from app.domain.enums import (
    ConversationStatus,
    ConversationTrigger,
    EventType,
    ExposureType,
    MemoryType,
)
from app.domain.ids import new_correlation_id
from app.providers.llm import LLMError, LLMProvider, get_llm_provider
from app.providers.llm.base import LLMResult
from app.schemas.actions import (
    CONTENT_ACTIONS,
    IN_CONVERSATION_ACTIONS,
    ActionType,
    AgentDecision,
)
from app.services import clock as clock_service
from app.services import conversations as convo
from app.services import founder, scheduler
from app.services.context_builder import build_agent_context
from app.services.events import record_event
from app.services.exposure import expose

PROMPT_VERSION = "agent_decision.v1"

#: The only actions Packet 3 will execute. Anything else is rejected.
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

    @property
    def acted(self) -> bool:
        return self.decision is not None and self.rejected_reason is None


def estimate_cost_usd(model: str, usage) -> float:
    """Rough spend for one call, from the operator-maintained price table.

    Fixture runs cost nothing and are reported as zero — never as what the same
    tokens would have cost live, which would make a fixture day look like a
    priced one. An unrecognised live model also returns zero; check the model
    against MODEL_PRICES_USD_PER_MTOK before reading a cost report as complete.
    """
    if model.startswith("fixture:"):
        return 0.0
    prices = MODEL_PRICES_USD_PER_MTOK.get(model)
    if not prices:
        return 0.0
    inp, out = prices
    return (usage.input_tokens * inp + usage.output_tokens * out) / 1_000_000


def validate_decision(
    decision: AgentDecision,
    *,
    agent: Agent,
    present_agent_ids: tuple[str, ...],
    in_conversation: bool = False,
) -> None:
    """Semantic validation, after the schema has already been satisfied.

    Schema validation proves the shape; this proves the decision refers to a
    world that exists.
    """
    if decision.location is not None and decision.location not in CLUBHOUSE_LOCATIONS:
        raise DecisionRejected(
            f"location {decision.location!r} is not a clubhouse location"
        )

    for action in decision.actions:
        if action.type not in ALLOWED_ACTIONS:
            raise DecisionRejected(f"action {action.type} is not available in this packet")

        if action.type in IN_CONVERSATION_ACTIONS and not in_conversation:
            raise DecisionRejected(
                f"{action.type.value} requires being in an open conversation"
            )

        if action.type is ActionType.START_CONVERSATION:
            if in_conversation:
                raise DecisionRejected("a conversation is already open")
            if not action.target_agent_id:
                raise DecisionRejected("START_CONVERSATION requires a target_agent_id")

        if action.type is ActionType.ASK_QUESTION and not action.target_agent_id:
            raise DecisionRejected("ASK_QUESTION requires a target_agent_id")

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


def execute_decision(
    session: Session,
    agent: Agent,
    decision: AgentDecision,
    clock: SimulationClock,
    correlation_id: str,
    conversation: Conversation | None = None,
) -> tuple[list[str], bool]:
    """Perform the state changes a validated decision calls for.

    Returns what was performed and whether the agent spoke, which is what the
    conversation engine needs to know to decide if the room has gone quiet.
    """
    performed: list[str] = []
    spoke = False

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
        # REST / OBSERVE / LISTEN_TO_MUSIC / DRINK_COFFEE / DO_NOTHING are fully
        # expressed by the activity and location already applied above.
        agent.interaction_target = action.target_agent_id
        performed.append(action.type.value)

    if not decision.actions:
        agent.interaction_target = None

    return performed, spoke


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

    if conversation is not None:
        speaker_id = convo.next_speaker(session, conversation)
        if speaker_id is None:
            convo.close(session, conversation, clock, "no participants left",
                        correlation_id=conversation.correlation_id)
            conversation = None
        else:
            candidate = None
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
            result = provider.decide(
                system=context.system,
                user=context.user
                if attempt == 0
                else f"{context.user}\n\nYOUR PREVIOUS DECISION WAS REJECTED: {rejection}\nReturn a valid decision.",
                model=settings.agent_model,
                purpose="agent_decision",
            )
        except LLMError as exc:
            outcome.rejected_reason = f"provider error: {exc}"
            break

        try:
            validate_decision(
                result.decision,
                agent=agent,
                present_agent_ids=context.present_agent_ids,
                in_conversation=conversation is not None,
            )
        except DecisionRejected as exc:
            rejection = str(exc)
            _record_run(session, result, agent.agent_id, outcome)
            if attempt == 1:
                outcome.rejected_reason = rejection
            continue

        _record_run(session, result, agent.agent_id, outcome)
        outcome.decision = result.decision
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

    outcome.executed, outcome.spoke = execute_decision(
        session, agent, outcome.decision, clock, correlation_id, conversation
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


def _record_run(
    session: Session, result: LLMResult, agent_id: str, outcome: EventOutcome
) -> None:
    """Persist one model call's telemetry."""
    run = LLMRun(
        purpose="agent_decision",
        agent_id=agent_id,
        provider=result.provider,
        model=result.model,
        is_fixture=result.is_fixture,
        prompt_version=PROMPT_VERSION,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
        cache_read_input_tokens=result.usage.cache_read_input_tokens,
        estimated_cost_usd=estimate_cost_usd(result.model, result.usage),
        latency_ms=result.latency_ms,
        stop_reason=result.usage.stop_reason,
    )
    session.add(run)
    session.flush()
    outcome.llm_run_id = run.id
