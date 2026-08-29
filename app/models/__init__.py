"""All ORM models for Phase 1.

Importing this package imports every model module, which is what registers the
tables on ``Base.metadata``. Alembic's ``env.py`` and ``scripts/inspect_schema.py``
both rely on that, so keep every new model module imported here.
"""

from __future__ import annotations

from app.db import Base
from app.models.agent import Agent, AgentBelief, AgentInterest, BeliefStatus, Relationship
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationTrigger,
    Message,
)
from app.models.event import Event, EventType
from app.models.founder import DailyReport, FounderMessage
from app.models.memory import Memory, MemoryType
from app.models.rabbit_hole import (
    RabbitHole,
    RabbitHoleMember,
    RabbitHoleResearch,
    RabbitHoleStatus,
)
from app.models.research import (
    EvidenceStrength,
    FindingClassification,
    ResearchFinding,
    ResearchQuery,
    ResearchSession,
    ResearchSource,
    ResearchStatus,
)
from app.models.wall import ResearchWallPost, WallPostType
from app.models.world import CLUBHOUSE_LOCATIONS, Location, SimulationClock, WorldState

__all__ = [
    "Base",
    # agent
    "Agent",
    "AgentBelief",
    "AgentInterest",
    "BeliefStatus",
    "Relationship",
    # memory
    "Memory",
    "MemoryType",
    # research
    "EvidenceStrength",
    "FindingClassification",
    "ResearchFinding",
    "ResearchQuery",
    "ResearchSession",
    "ResearchSource",
    "ResearchStatus",
    # wall
    "ResearchWallPost",
    "WallPostType",
    # rabbit holes
    "RabbitHole",
    "RabbitHoleMember",
    "RabbitHoleResearch",
    "RabbitHoleStatus",
    # conversation
    "Conversation",
    "ConversationMessage",
    "ConversationStatus",
    "ConversationTrigger",
    "Message",
    # world
    "CLUBHOUSE_LOCATIONS",
    "Location",
    "SimulationClock",
    "WorldState",
    # founder
    "DailyReport",
    "FounderMessage",
    # events
    "Event",
    "EventType",
]
