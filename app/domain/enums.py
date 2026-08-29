"""Every enumerated value in the Village.

Centralised so the database, the action schemas and the services all name the
same things. The SQL type names these map to are fixed by the initial migration
and must not be renamed casually — a rename is a migration, not an edit.
"""

from __future__ import annotations

import enum


class BeliefStatus(str, enum.Enum):
    """Lifecycle of an agent-held belief (§2, §9)."""

    PROVISIONAL = "PROVISIONAL"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class MemoryType(str, enum.Enum):
    """What kind of memory this is (§9)."""

    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    SOCIAL = "SOCIAL"
    INTEREST = "INTEREST"


class ResearchStatus(str, enum.Enum):
    """Where a research session got to."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class EvidenceStrength(str, enum.Enum):
    """How well-supported a conclusion is (§6). Reused by rabbit holes."""

    WEAK = "WEAK"
    DEVELOPING = "DEVELOPING"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"


class FindingClassification(str, enum.Enum):
    """Epistemic status of a finding (§2) — the build bible's reality classes.

    These nine values are deliberately distinct and must never be collapsed into
    a coarser set: the whole point of §2 is that a real-world fact, a source's
    claim, an agent's inference, and a piece of creative content stay
    distinguishable forever. Phase 1 may only populate a few of them.
    """

    REAL_WORLD_FACT = "REAL_WORLD_FACT"
    SOURCE_CLAIM = "SOURCE_CLAIM"
    RESEARCH_FINDING = "RESEARCH_FINDING"
    AGENT_INFERENCE = "AGENT_INFERENCE"
    AGENT_BELIEF = "AGENT_BELIEF"
    HYPOTHESIS = "HYPOTHESIS"
    SPECULATION = "SPECULATION"
    SIMULATION_EVENT = "SIMULATION_EVENT"
    CREATIVE_CONTENT = "CREATIVE_CONTENT"


class WallPostType(str, enum.Enum):
    """What kind of thing an agent pinned to the research wall."""

    FINDING = "FINDING"
    SOURCE = "SOURCE"
    QUESTION = "QUESTION"
    HYPOTHESIS = "HYPOTHESIS"
    DISAGREEMENT = "DISAGREEMENT"
    CONNECTION = "CONNECTION"
    MYSTERY = "MYSTERY"
    RABBIT_HOLE_SUGGESTION = "RABBIT_HOLE_SUGGESTION"


class RabbitHoleStatus(str, enum.Enum):
    """How alive a rabbit hole currently is."""

    NEW = "NEW"
    ACTIVE = "ACTIVE"
    HOT = "HOT"
    COOLING = "COOLING"
    DORMANT = "DORMANT"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class ConversationTrigger(str, enum.Enum):
    """Why a conversation started at all (§12)."""

    RESEARCH_SHARING = "RESEARCH_SHARING"
    WALL_ACTIVITY = "WALL_ACTIVITY"
    DISAGREEMENT = "DISAGREEMENT"
    SIMILAR_DISCOVERY = "SIMILAR_DISCOVERY"
    MORNING_GATHERING = "MORNING_GATHERING"
    RANDOM_SOCIAL = "RANDOM_SOCIAL"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"


class ConversationStatus(str, enum.Enum):
    """Whether a conversation is still running."""

    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class EventType(str, enum.Enum):
    """Every kind of thing the village records (§18)."""

    AGENT_WOKE = "AGENT_WOKE"
    # Beyond the build bible's §18 list: the action loop needs to record that a
    # decision was executed, and that one was rejected.
    AGENT_ACTED = "AGENT_ACTED"
    INVALID_AGENT_DECISION = "INVALID_AGENT_DECISION"
    AGENT_RESEARCH_STARTED = "AGENT_RESEARCH_STARTED"
    SEARCH_EXECUTED = "SEARCH_EXECUTED"
    SOURCE_DISCOVERED = "SOURCE_DISCOVERED"
    RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
    FINDING_CREATED = "FINDING_CREATED"
    FINDING_SHARED = "FINDING_SHARED"
    RESEARCH_WALL_POSTED = "RESEARCH_WALL_POSTED"
    RABBIT_HOLE_CREATED = "RABBIT_HOLE_CREATED"
    RABBIT_HOLE_JOINED = "RABBIT_HOLE_JOINED"
    RABBIT_HOLE_UPDATED = "RABBIT_HOLE_UPDATED"
    CONVERSATION_STARTED = "CONVERSATION_STARTED"
    CONVERSATION_MESSAGE = "CONVERSATION_MESSAGE"
    CONVERSATION_ENDED = "CONVERSATION_ENDED"
    CLAIM_CHALLENGED = "CLAIM_CHALLENGED"
    FOLLOWUP_QUESTION_CREATED = "FOLLOWUP_QUESTION_CREATED"
    BELIEF_CREATED = "BELIEF_CREATED"
    BELIEF_UPDATED = "BELIEF_UPDATED"
    BELIEF_REJECTED = "BELIEF_REJECTED"
    INTEREST_INCREASED = "INTEREST_INCREASED"
    INTEREST_DECREASED = "INTEREST_DECREASED"
    MEMORY_CREATED = "MEMORY_CREATED"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"
    DAILY_REPORT_CREATED = "DAILY_REPORT_CREATED"
