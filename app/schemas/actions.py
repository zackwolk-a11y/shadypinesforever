"""The agent action envelope — the only shape a model may return.

An agent does not get a toolbox. It returns one structured decision, the
application validates it, and the application performs the state transitions.
No hidden chain-of-thought is requested or wanted.

Packet 3 implements the non-research actions only. Later action types
(START_RESEARCH, SHARE_FINDING, …) arrive with their own packets; a decision
naming one now fails validation rather than being silently dropped.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field, field_validator

MAX_ACTIONS_PER_DECISION = 3


class ActionType(str, enum.Enum):
    """Every action an agent may take in Packet 3."""

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
}

#: Actions that only make sense inside an open conversation.
IN_CONVERSATION_ACTIONS = {ActionType.SPEAK, ActionType.LEAVE_CONVERSATION}


class AgentAction(BaseModel):
    """One thing an agent does."""

    model_config = {"extra": "forbid"}

    type: ActionType
    target_agent_id: str | None = None
    content: str | None = None


class AgentDecision(BaseModel):
    """What an activated agent decided to do.

    ``public_dialogue`` is what the agent says aloud in the room, if anything.
    Silence is a legal decision: an empty ``actions`` list with no dialogue is
    valid and common.
    """

    model_config = {"extra": "forbid"}

    summary: str = Field(description="One sentence on what the agent is doing and why.")
    activity: str = Field(description="Short label for the agent's current activity.")
    location: str | None = Field(
        default=None, description="Clubhouse location the agent moves to, or null to stay put."
    )
    actions: list[AgentAction] = Field(default_factory=list)
    public_dialogue: str | None = None

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
