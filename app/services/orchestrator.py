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
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock
from app.domain.enums import EventType, MemoryType
from app.domain.ids import new_correlation_id
from app.providers.llm import LLMError, LLMProvider, get_llm_provider
from app.providers.llm.base import LLMResult
from app.schemas.actions import ActionType, AgentDecision
from app.services import scheduler
from app.services.context_builder import build_agent_context
from app.services.events import record_event

PROMPT_VERSION = "agent_decision.v1"

#: The only actions Packet 3 will execute. Anything else is rejected.
ALLOWED_ACTIONS: tuple[ActionType, ...] = tuple(ActionType)


class DecisionRejected(Exception):
    """A decision failed semantic validation."""


@dataclass
class EventOutcome:
    """What one RUN NEXT EVENT produced."""

    activated_agent_id: str | None = None
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

        if action.type is ActionType.ASK_QUESTION and not action.target_agent_id:
            raise DecisionRejected("ASK_QUESTION requires a target_agent_id")

        if action.target_agent_id is not None:
            if action.target_agent_id == agent.agent_id:
                raise DecisionRejected("an agent cannot address itself")
            if action.target_agent_id not in present_agent_ids:
                raise DecisionRejected(
                    f"unknown target_agent_id {action.target_agent_id!r}"
                )

        if action.type in (ActionType.WRITE_NOTE, ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE):
            if not (action.content or "").strip():
                raise DecisionRejected(f"{action.type.value} requires content")


def execute_decision(
    session: Session,
    agent: Agent,
    decision: AgentDecision,
    clock: SimulationClock,
    correlation_id: str,
) -> list[str]:
    """Perform the state changes a validated decision calls for."""
    performed: list[str] = []

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
        elif action.type in (ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE):
            session.add(
                Message(
                    sender_agent_id=agent.agent_id,
                    recipient_agent_id=action.target_agent_id,
                    content=action.content or "",
                )
            )
        # REST / OBSERVE / LISTEN_TO_MUSIC / DRINK_COFFEE / DO_NOTHING are fully
        # expressed by the activity and location already applied above.
        agent.interaction_target = action.target_agent_id
        performed.append(action.type.value)

    if not decision.actions:
        agent.interaction_target = None

    return performed


def run_next_event(
    session: Session,
    *,
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    seed: str = "",
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

    candidate = scheduler.next_agent(session, clock, settings, seed=seed)
    if candidate is None:
        return EventOutcome(
            note=(
                f"No agent is eligible to act in day {clock.current_day} "
                f"{clock.current_period}. Everyone with a reason to act has acted "
                "and the period is spent. Advancing the period or day is the day "
                "engine's job, which is a later packet."
            )
        )

    agent = session.scalars(
        select(Agent).where(Agent.agent_id == candidate.agent_id)
    ).one()
    correlation_id = new_correlation_id()
    outcome = EventOutcome(
        activated_agent_id=agent.agent_id,
        correlation_id=correlation_id,
        is_fixture=provider.is_fixture,
    )

    context = build_agent_context(
        session,
        agent,
        clock,
        settings,
        available_actions=tuple(a.value for a in ALLOWED_ACTIONS),
    )

    # Showing a message to an agent is delivering it.
    for message in context.delivered_messages:
        message.read_at = utcnow()

    woke = record_event(
        session,
        event_type=EventType.AGENT_WOKE,
        agent_id=agent.agent_id,
        payload={
            "activation_score": round(candidate.score, 3),
            "components": {k: round(v, 3) for k, v in candidate.components.items()},
            "approx_context_tokens": context.approx_tokens,
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
                result.decision, agent=agent, present_agent_ids=context.present_agent_ids
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
        return outcome

    outcome.executed = execute_decision(
        session, agent, outcome.decision, clock, correlation_id
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
    return outcome


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
