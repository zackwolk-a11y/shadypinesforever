"""The agent action envelope — the only shape a model may return.

An agent does not get a toolbox. It returns one structured decision, the
application validates it, and the application performs the state transitions.
No hidden chain-of-thought is requested or wanted.

Packet 6 adds the Research Wall, Rabbit Holes, and belief revision. Every new
action targets something the agent must already have real, exposed knowledge
of — a real wall post id, a real rabbit hole id, a real claim id, a real
belief id — never a name or description the model invents. Semantic
validation in the orchestrator checks every one of these against the database
before anything executes.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import BeliefBasisRelation, MemoryType, WallPostType

MAX_ACTIONS_PER_DECISION = 3


class ActionType(str, enum.Enum):
    """Every action an agent may take."""

    DO_NOTHING = "DO_NOTHING"
    REST = "REST"
    OBSERVE = "OBSERVE"
    LISTEN_TO_MUSIC = "LISTEN_TO_MUSIC"
    DRINK_COFFEE = "DRINK_COFFEE"
    WRITE_NOTE = "WRITE_NOTE"
    ASK_QUESTION = "ASK_QUESTION"
    SEND_MESSAGE = "SEND_MESSAGE"
    START_CONVERSATION = "START_CONVERSATION"
    SPEAK = "SPEAK"
    LEAVE_CONVERSATION = "LEAVE_CONVERSATION"
    #: Packet 5. ``content`` carries the research question — the agent's own,
    #: drawn from its interests, memories, conversations and what it has seen
    #: on the wall, never assigned.
    START_RESEARCH = "START_RESEARCH"

    # ---- Packet 6: Research Wall ----------------------------------------
    #: Pin a FINDING/SOURCE/QUESTION/HYPOTHESIS/DISAGREEMENT/CONNECTION/
    #: MYSTERY/RABBIT_HOLE_SUGGESTION. ``wall_post_type`` picks which;
    #: ``content`` is the post; ``target_research_id`` cites the agent's own
    #: research if any; ``target_wall_post_id`` is required for CONNECTION —
    #: the other agent's post this one draws a line to.
    POST_TO_WALL = "POST_TO_WALL"
    #: Read one wall post in full. ``target_wall_post_id`` required. Moves the
    #: agent from a headline glimpse to real exposure — including exposure to
    #: whatever research that post cites, if any.
    READ_WALL_POST = "READ_WALL_POST"

    # ---- Packet 6: Rabbit Holes ------------------------------------------
    #: ``title`` and ``content`` (the description) required.
    #: ``target_research_id`` or ``target_wall_post_id`` grounds why this
    #: deserves to be a shared investigation rather than one agent's finding.
    CREATE_RABBIT_HOLE = "CREATE_RABBIT_HOLE"
    JOIN_RABBIT_HOLE = "JOIN_RABBIT_HOLE"
    #: Add a note, and optionally link ``target_research_id`` into the hole —
    #: this is how a rabbit hole actually pulls in more than one agent's work.
    CONTRIBUTE_TO_RABBIT_HOLE = "CONTRIBUTE_TO_RABBIT_HOLE"
    LEAVE_RABBIT_HOLE = "LEAVE_RABBIT_HOLE"
    RESOLVE_RABBIT_HOLE = "RESOLVE_RABBIT_HOLE"

    # ---- Packet 6: challenge and belief revision --------------------------
    #: ``target_claim_id`` required — a specific atomic claim, not a whole
    #: finding or session, so the disagreement is about something concrete.
    CHALLENGE_CLAIM = "CHALLENGE_CLAIM"
    #: Form a new belief from the agent's own completed research.
    #: ``target_research_id`` required as its founding basis.
    FORM_BELIEF = "FORM_BELIEF"
    #: Revise an existing belief given new evidence — the agent's own new
    #: research, or research/a wall post it has been genuinely exposed to via
    #: reading or rabbit-hole membership. ``target_belief_id`` and
    #: ``belief_relation`` required; one of ``target_research_id`` /
    #: ``target_wall_post_id`` required as the evidence being weighed.
    REVISE_BELIEF = "REVISE_BELIEF"
    #: The agent simply no longer holds this belief — no new evidence needed.
    #: ``target_belief_id`` required.
    RETIRE_BELIEF = "RETIRE_BELIEF"


#: Actions that address another agent. ASK_QUESTION always needs a recipient;
#: SEND_MESSAGE may broadcast with a null target.
DIRECTED_ACTIONS = {ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE}

#: Actions whose content is the point of the action.
CONTENT_ACTIONS = {
    ActionType.WRITE_NOTE,
    ActionType.ASK_QUESTION,
    ActionType.SEND_MESSAGE,
    ActionType.START_CONVERSATION,
    ActionType.SPEAK,
    ActionType.START_RESEARCH,
    ActionType.POST_TO_WALL,
    ActionType.CREATE_RABBIT_HOLE,
    ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
    ActionType.CHALLENGE_CLAIM,
    ActionType.FORM_BELIEF,
}

#: Actions that only make sense inside an open conversation.
IN_CONVERSATION_ACTIONS = {ActionType.SPEAK, ActionType.LEAVE_CONVERSATION}

#: Actions that cannot happen while in a conversation — each needs the agent's
#: full attention on something outside the room (research, the wall, a rabbit
#: hole), the same way START_RESEARCH already does.
NOT_IN_CONVERSATION_ACTIONS = {
    ActionType.START_RESEARCH,
    ActionType.POST_TO_WALL,
    ActionType.READ_WALL_POST,
    ActionType.CREATE_RABBIT_HOLE,
    ActionType.JOIN_RABBIT_HOLE,
    ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
    ActionType.LEAVE_RABBIT_HOLE,
    ActionType.RESOLVE_RABBIT_HOLE,
    ActionType.CHALLENGE_CLAIM,
    ActionType.FORM_BELIEF,
    ActionType.REVISE_BELIEF,
    ActionType.RETIRE_BELIEF,
}

#: One action of each of these kinds per decision — the same reasoning as
#: START_RESEARCH's cap in Packet 5: a decision is one thing, not a batch job.
#: Every Packet 6 action qualifies too — each is a substantial act, and
#: capping them at one per decision also sidesteps same-decision duplicate
#: checks (e.g. two CONNECTION posts to the same target) ever needing to see
#: a sibling action's not-yet-flushed effect.
SINGLETON_ACTIONS = {
    ActionType.START_RESEARCH,
    ActionType.POST_TO_WALL,
    ActionType.READ_WALL_POST,
    ActionType.CREATE_RABBIT_HOLE,
    ActionType.JOIN_RABBIT_HOLE,
    ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
    ActionType.LEAVE_RABBIT_HOLE,
    ActionType.RESOLVE_RABBIT_HOLE,
    ActionType.CHALLENGE_CLAIM,
    ActionType.FORM_BELIEF,
    ActionType.REVISE_BELIEF,
    ActionType.RETIRE_BELIEF,
}


class AgentAction(BaseModel):
    """One thing an agent does.

    Not every field applies to every action type — semantic validation
    enforces which are required per :class:`ActionType`, exactly as it already
    does for ``target_agent_id`` on ``ASK_QUESTION``.
    """

    model_config = {"extra": "forbid"}

    type: ActionType
    target_agent_id: str | None = None
    content: str | None = None
    title: str | None = Field(default=None, description="Required for CREATE_RABBIT_HOLE.")
    wall_post_type: WallPostType | None = Field(
        default=None, description="Required for POST_TO_WALL."
    )
    target_research_id: str | None = None
    target_wall_post_id: int | None = None
    target_rabbit_hole_id: int | None = None
    target_claim_id: int | None = None
    target_belief_id: int | None = None
    belief_relation: BeliefBasisRelation | None = Field(
        default=None, description="Required for REVISE_BELIEF: STRENGTHENS, WEAKENS, or REJECTS."
    )
    #: Packet 7. Only meaningful for WRITE_NOTE — which kind of memory the
    #: agent means to lay down. Defaults to EPISODIC (app/services/memory.py)
    #: when omitted, since "I want to remember this" without further
    #: qualification is most often a specific moment.
    memory_type: MemoryType | None = Field(
        default=None, description="Optional for WRITE_NOTE: EPISODIC, SEMANTIC, SOCIAL, INTEREST, or PROJECT."
    )


class Reflection(BaseModel):
    """A short structured reflection after a significant event (Packet 7,
    §15). Every field is optional — most decisions warrant no reflection at
    all — and each one is a concise conclusion, never reasoning: this is not
    a place for chain-of-thought, and nothing here is stored except exactly
    what the agent reports.
    """

    model_config = {"extra": "forbid"}

    what_changed: str | None = Field(default=None, description="What is different now, if anything.")
    what_matters_now: str | None = Field(default=None, description="What matters most going forward.")
    what_i_want_to_revisit: str | None = Field(
        default=None, description="Something worth coming back to later, if anything."
    )


class AgentDecision(BaseModel):
    """What an activated agent decided to do.

    ``public_dialogue`` is what the agent says aloud in the room, if anything.
    Silence is a legal decision: an empty ``actions`` list with no dialogue is
    valid and common. ``reflection`` (Packet 7) is likewise optional and rare
    — most turns produce none.
    """

    model_config = {"extra": "forbid"}

    summary: str = Field(description="One sentence on what the agent is doing and why.")
    activity: str = Field(description="Short label for the agent's current activity.")
    location: str | None = Field(
        default=None, description="Clubhouse location the agent moves to, or null to stay put."
    )
    actions: list[AgentAction] = Field(default_factory=list)
    public_dialogue: str | None = None
    reflection: Reflection | None = None

    @field_validator("actions")
    @classmethod
    def _cap_actions(cls, value: list[AgentAction]) -> list[AgentAction]:
        if len(value) > MAX_ACTIONS_PER_DECISION:
            raise ValueError(
                f"at most {MAX_ACTIONS_PER_DECISION} actions per decision, got {len(value)}"
            )
        return value


def decision_json_schema() -> dict:
    """JSON schema for the decision envelope, for providers that need it raw."""
    return AgentDecision.model_json_schema()
