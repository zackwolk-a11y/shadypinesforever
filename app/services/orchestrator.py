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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.models.agents import Agent
from app.db.models.conversations import Conversation, Message
from app.db.models.events import Event
from app.db.models.rabbit_holes import RabbitHole
from app.db.models.research import ResearchSession
from app.db.models.research_provenance import Claim
from app.db.models.wall import ResearchWallPost
from app.db.models.world import CLUBHOUSE_LOCATIONS, SimulationClock
from app.domain.enums import (
    ConversationStatus,
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
from app.services import daily_synthesis
from app.services import dialogue, founder, memory, rabbit_holes as rh, reflection, research, scheduler, wall
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
    open_conversation_id: int | None = None,
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

        if action.type in (ActionType.SPEAK, ActionType.START_CONVERSATION) and session is not None:
            if dialogue.has_generic_filler_opener(action.content or ""):
                raise DecisionRejected(
                    "opens with a generic filler phrase (\"that's fascinating\", \"great "
                    "point\", ...) — respond to what was actually said instead"
                )
            if dialogue.is_repetitive(session, agent.agent_id, action.content or ""):
                raise DecisionRejected(
                    "repeats one of your own recent utterances verbatim — say something new"
                )

        if action.type is ActionType.JOIN_CONVERSATION:
            if open_conversation_id is None:
                raise DecisionRejected("no open conversation to join")
            elif session is not None:
                open_convo = session.get(Conversation, open_conversation_id)
                if open_convo is None or open_convo.status is ConversationStatus.ENDED:
                    raise DecisionRejected("that conversation has already ended")
                if len(open_convo.participant_ids or []) >= dialogue.MAX_SPONTANEOUS_PARTICIPANTS:
                    raise DecisionRejected("that conversation is already full")

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

    if action.type is ActionType.SPEAK:
        # target_research_id already validated generically above. Wall posts
        # and rabbit holes referenced in dialogue get the same treatment as
        # everywhere else: a real id, actually exposed — never invented.
        if action.target_wall_post_id is not None:
            if session.get(ResearchWallPost, action.target_wall_post_id) is None:
                raise DecisionRejected(f"unknown wall post {action.target_wall_post_id!r}")
            if not has_been_exposed(session, agent.agent_id, "research_wall", action.target_wall_post_id):
                raise DecisionRejected("no real exposure to that wall post")
        if action.target_rabbit_hole_id is not None:
            if session.get(RabbitHole, action.target_rabbit_hole_id) is None:
                raise DecisionRejected(f"unknown rabbit hole {action.target_rabbit_hole_id!r}")

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


def _link_conversation_references(conversation: Conversation, action) -> None:
    """A SPEAK that cites real research/a wall post/a rabbit hole records
    that connection on the conversation itself (§ "cross-pollination... a
    conversation may lead to a Research Wall post... a Rabbit Hole..." and
    the reverse: dialogue should be traceable back to what it drew on)."""
    if action.target_research_id and action.target_research_id not in conversation.related_research_ids:
        conversation.related_research_ids = [*conversation.related_research_ids, action.target_research_id]
    if action.target_wall_post_id and action.target_wall_post_id not in conversation.related_wall_post_ids:
        conversation.related_wall_post_ids = [*conversation.related_wall_post_ids, action.target_wall_post_id]
    if action.target_rabbit_hole_id and action.target_rabbit_hole_id not in conversation.related_rabbit_hole_ids:
        conversation.related_rabbit_hole_ids = [*conversation.related_rabbit_hole_ids, action.target_rabbit_hole_id]


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
            memory.write_note(
                session, agent.agent_id, action.content or "", clock, correlation_id,
                memory_type=action.memory_type or MemoryType.EPISODIC,
            )
        elif action.type is ActionType.SPEAK and conversation is not None:
            convo.record_utterance(
                session,
                conversation,
                agent.agent_id,
                action.content or "",
                clock,
                correlation_id=correlation_id,
                move=action.conversational_move,
            )
            if action.conversational_move == dialogue.MOVE_CHANGE_SUBJECT and action.new_subject:
                conversation.current_subject = action.new_subject[:200]
            _link_conversation_references(conversation, action)
            spoke = True
        elif action.type is ActionType.LEAVE_CONVERSATION and conversation is not None:
            convo.leave(session, conversation, agent.agent_id, clock, correlation_id=correlation_id)
        elif action.type is ActionType.JOIN_CONVERSATION and conversation is not None:
            convo.join(session, conversation, agent.agent_id, clock, correlation_id=correlation_id)
        elif action.type is ActionType.START_CONVERSATION:
            reason = dialogue.pick_trigger(session, agent.agent_id, action.target_agent_id, clock)
            new_conversation = convo.start_conversation(
                session,
                trigger=reason.trigger,
                participant_ids=[agent.agent_id, action.target_agent_id],
                clock=clock,
                correlation_id=correlation_id,
            )
            new_conversation.correlation_id = correlation_id
            new_conversation.location = agent.current_location
            new_conversation.current_subject = reason.subject[:200]
            new_conversation.initiating_reason = reason.reason
            if reason.related_research_id:
                new_conversation.related_research_ids = [reason.related_research_id]
            if reason.related_wall_post_id:
                new_conversation.related_wall_post_ids = [reason.related_wall_post_id]
            if reason.related_rabbit_hole_id:
                new_conversation.related_rabbit_hole_ids = [reason.related_rabbit_hole_id]
            if reason.related_memory_id:
                new_conversation.related_memory_ids = [reason.related_memory_id]
            convo.record_utterance(
                session,
                new_conversation,
                agent.agent_id,
                action.content or "",
                clock,
                correlation_id=correlation_id,
                move=dialogue.MOVE_OPEN,
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
                    provider_name=settings.research_provider,
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
    force_agent_id: str | None = None,
) -> EventOutcome:
    """Activate one agent and carry its decision through to persisted state.

    The caller commits. Everything this writes — state, events, telemetry —
    belongs to one transaction.

    ``force_agent_id`` (Packet 11, Part J) bypasses ``scheduler.next_agent``
    to activate one named agent instead of whoever the activation scheduler
    would otherwise pick — for a bounded single-agent developer test
    (``scripts/run_live_agent_once.py``), never for ordinary simulation.
    Everything downstream of the pick — context building, the real provider
    call, validation, execution, memory/reflection/telemetry — is the exact
    same path any other activation takes; this is not a parallel decision
    architecture, only a different way to choose whose turn it is.
    """
    settings = settings or get_settings()
    provider = provider or get_llm_provider(settings)

    clock = session.scalars(select(SimulationClock).limit(1)).first()
    if clock is None:
        return EventOutcome(note="No simulation clock. Run scripts/seed_agents.py first.")
    if clock.is_paused:
        return EventOutcome(note="Simulation is paused.")

    # The Founder's mail reaches people before anyone decides anything.
    delivered = founder.deliver_pending(session, clock)
    if delivered:
        memory.consider_founder_delivery(session, delivered, clock)

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

    # Packet 8: every few activations, check whether someone outside this
    # conversation has a real reason to be pulled into it. Gated on the
    # global event id, not on this conversation's own turn_count: turn_count
    # only advances when someone actually speaks, so a candidate offered the
    # slot and declining (or joining without immediately speaking) would
    # otherwise leave turn_count unchanged — making a turn_count-based gate
    # stay permanently true and the *same* joiner-check win every single
    # subsequent activation forever, starving the real participants (a
    # genuine runaway/monopolization bug caught by
    # scripts/smoke_test_dialogue.py). The last event id strictly increases
    # every activation regardless of what happens, so this gate always moves.
    joiner = None
    if conversation is not None:
        last_event_id = session.scalar(select(func.max(Event.id))) or 0
        if last_event_id % 4 == 0:
            joiner = dialogue.find_joiner(session, conversation, clock, settings, seed=seed)

    # ``conversation`` is always the one real open conversation, if any —
    # needed later for execute_decision regardless of who gets this turn.
    # ``context_conversation`` is only set when the acting agent is actually
    # a participant in it right now: that's what governs whether this turn
    # sees the transcript, may SPEAK, and whether _after_turn applies.
    candidate = None
    context_conversation = conversation
    if force_agent_id is not None:
        agent = session.scalars(select(Agent).where(Agent.agent_id == force_agent_id)).one()
        correlation_id = new_correlation_id()
        context_conversation = (
            conversation
            if conversation is not None and force_agent_id in (conversation.participant_ids or [])
            else None
        )
    elif joiner is not None:
        agent = session.scalars(select(Agent).where(Agent.agent_id == joiner.agent_id)).one()
        correlation_id = new_correlation_id()
        context_conversation = None
    elif conversation is not None:
        speaker_id = convo.next_speaker(session, conversation, clock, settings)
        if speaker_id is None:
            # Empty room and "everyone present is already out of activations
            # for today" are both real, distinct reasons next_speaker can
            # come back empty — see its own docstring.
            reason = (
                "no participants left"
                if not (conversation.participant_ids or [])
                else "everyone present has reached today's activation limit"
            )
            convo.close(session, conversation, clock, reason,
                        correlation_id=conversation.correlation_id)
            _finalize_conversation(session, conversation, clock)
            conversation = None
            context_conversation = None
        else:
            agent = session.scalars(
                select(Agent).where(Agent.agent_id == speaker_id)
            ).one()
            correlation_id = conversation.correlation_id or new_correlation_id()
    if conversation is None and joiner is None and force_agent_id is None:
        candidate = scheduler.next_agent(session, clock, settings, seed=seed)
        if candidate is None:
            if auto_advance:
                advance = clock_service.advance(session, clock)
                if advance.crossed_day_boundary:
                    daily_synthesis.generate_report(
                        session, advance.from_day, clock, settings, provider,
                    )
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
        conversation=context_conversation,
        nearby_conversation=conversation if context_conversation is None else None,
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
                max_tokens=settings.max_tokens_agent_decision,
            )
        except LLMError as exc:
            outcome.rejected_reason = f"provider error: {exc}"
            break

        try:
            validate_decision(
                result.output,
                agent=agent,
                present_agent_ids=context.present_agent_ids,
                in_conversation=context_conversation is not None,
                open_conversation_id=conversation.id if conversation is not None else None,
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
        if context_conversation is not None:
            _after_turn(session, context_conversation, clock, settings, spoke=False)
        return outcome

    outcome.executed, outcome.spoke, outcome.research = execute_decision(
        session, agent, outcome.decision, clock, correlation_id, conversation,
        settings, provider,
    )

    # Memory selection (Packet 7): every event this turn's actions produced —
    # research, wall, rabbit-hole, claim, belief — gets a chance to become a
    # memory for whoever it concerns. Re-queried by correlation_id rather
    # than threaded through execute_decision's return value, so none of the
    # dozen call sites inside wall/rabbit_holes/beliefs/research need to know
    # memory consolidation exists — see app/services/memory.py.
    turn_event_ids = list(
        session.scalars(
            select(Event.id).where(
                Event.correlation_id == correlation_id, Event.id != woke.id
            )
        )
    )
    memory.consider_turn_events(session, turn_event_ids, clock)
    if outcome.decision.reflection is not None:
        memory.consider_reflection(
            session, agent.agent_id, outcome.decision.reflection, clock, correlation_id
        )
    # Packet 9: the reflection engine's expensive half — see
    # app/services/reflection.py's module docstring for why this only checks
    # the acting agent, and why the cheap accumulation happens elsewhere
    # (app.services.memory._upsert, on every memory formed this turn above).
    reflection.maybe_reflect(session, agent, clock, correlation_id, settings, provider)

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

    if context_conversation is not None:
        _after_turn(session, context_conversation, clock, settings, spoke=outcome.spoke)
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
        _finalize_conversation(session, conversation, clock)


def _finalize_conversation(session: Session, conversation: Conversation, clock: SimulationClock) -> None:
    """Once, right after a conversation closes: nudge the relationships of
    everyone who was in it (§ "conversations should gradually influence
    relationships"), and — only if this exchange actually cleared the bar —
    lay down one memory per participant (§ "meaningful conversations should
    be candidates ... do NOT store every utterance").
    """
    dialogue.update_relationship_dimensions(session, conversation, clock)
    worthy, reason = dialogue.conversation_worthy(session, conversation)
    if worthy:
        memory.consider_conversation_ended(session, conversation, reason, clock)
