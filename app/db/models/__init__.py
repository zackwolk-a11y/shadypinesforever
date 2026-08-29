"""All ORM models for Phase 1.

Importing this package imports every model module, which is what registers the
tables on ``Base.metadata``. Alembic's ``env.py`` and ``scripts/inspect_schema.py``
both rely on that, so keep every new model module imported here.
"""

from __future__ import annotations

from app.db.base import Base
from app.db.models.agents import Agent, AgentBelief, AgentInterest, BeliefStatus, Relationship
from app.db.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationTrigger,
    Message,
)
from app.db.models.events import Event, EventType
from app.db.models.exposure import AgentExposure
from app.db.models.reports import DailyReport, FounderMessage
from app.db.models.memory import Memory, MemoryType
from app.db.models.rabbit_holes import (
    RabbitHole,
    RabbitHoleMember,
    RabbitHoleResearch,
    RabbitHoleStatus,
)
from app.db.models.telemetry import LLMRun
from app.db.models.research import (
    EvidenceStrength,
    FindingClassification,
    ResearchFinding,
    ResearchQuery,
    ResearchSession,
    ResearchSource,
    ResearchStatus,
)
from app.db.models.wall import ResearchWallPost, WallPostType
from app.db.models.world import CLUBHOUSE_LOCATIONS, Location, SimulationClock, WorldState

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
    "AgentExposure",
    # telemetry
    "LLMRun",
]
