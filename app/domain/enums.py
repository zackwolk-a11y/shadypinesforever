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
    """What kind of memory this is (§9, Packet 7).

    Five kinds, deliberately kept distinct rather than collapsed into one
    generic "note": an EPISODIC memory of a specific moment, a SEMANTIC
    conclusion that survives the moment that produced it, a SOCIAL read on
    how another agent thinks or collaborates, an INTEREST shift in what an
    agent is curious about, and PROJECT context accumulated by returning to
    the same rabbit hole over time. Mixing these would blur exactly the
    distinction that makes retrieval useful — "what happened" and "what I
    now believe" and "what I know about Dex" are different kinds of recall.
    """

    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    SOCIAL = "SOCIAL"
    INTEREST = "INTEREST"
    PROJECT = "PROJECT"


class InterestOrigin(str, enum.Enum):
    """Why an agent came to hold an interest (§9, Packet 7).

    Stored as plain text on ``AgentInterest.origin`` (unchanged since Packet 1
    — a free-text column, not a DB enum), so this is a vocabulary for the
    application layer to use consistently, not a schema constraint. Founding
    interests keep using the literal string ``seed_agents.py`` already writes
    (``"§3 founding roster"``); everything an agent develops afterward uses
    one of these.
    """

    #: The literal string ``scripts/seed_agents.py`` has always written for
    #: the Founding Eight's starting interests (§3) — kept unchanged here so
    #: an existing seeded database's rows still match.
    FOUNDING = "§3 founding roster"
    RESEARCH_DISCOVERY = "research discovery"
    RABBIT_HOLE = "rabbit hole participation"
    AGENT_INFLUENCE = "another agent's influence"
    CONVERSATION = "conversation"
    FOUNDER_SUGGESTION = "founder suggestion"
    UNRESOLVED_QUESTION = "unresolved question"
    REPEATED_EXPOSURE = "repeated exposure"


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


class EvidenceRelation(str, enum.Enum):
    """How one piece of evidence bears on one claim (§6's provenance chain)."""

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CONTEXT = "CONTEXT"


class BeliefBasisRelation(str, enum.Enum):
    """How one piece of new evidence moved a belief (Packet 6).

    Deliberately a separate vocabulary from :class:`EvidenceRelation`: a claim
    is supported/contradicted/given-context *by a passage*, which is a fact
    about the evidence; a belief is strengthened/weakened/rejected *by an
    agent's judgment* of what new evidence means, which is an epistemic act.
    Collapsing the two would blur exactly the distinction §2 exists to keep —
    "the source says X" is not the same claim as "I now believe X less".
    """

    STRENGTHENS = "STRENGTHENS"
    WEAKENS = "WEAKENS"
    REJECTS = "REJECTS"


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
    """Why a conversation started at all (§12).

    Packet 8 makes this a real, computed choice (``app/services/dialogue.py``)
    rather than the placeholder every conversation used before — see
    ``dialogue.pick_trigger``. RABBIT_HOLE and MEMORY_PROMPTED are new:
    "following a Rabbit Hole" and "remembering a previous conversation" are
    both explicit reasons the spec lists that the original seven values had
    no honest way to name.
    """

    RESEARCH_SHARING = "RESEARCH_SHARING"
    WALL_ACTIVITY = "WALL_ACTIVITY"
    DISAGREEMENT = "DISAGREEMENT"
    SIMILAR_DISCOVERY = "SIMILAR_DISCOVERY"
    MORNING_GATHERING = "MORNING_GATHERING"
    RANDOM_SOCIAL = "RANDOM_SOCIAL"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"
    RABBIT_HOLE = "RABBIT_HOLE"
    MEMORY_PROMPTED = "MEMORY_PROMPTED"


class ConversationStatus(str, enum.Enum):
    """Where a conversation is in its short life.

    WINDING_DOWN is the grace state: someone has gone quiet, and the
    conversation will close unless it picks back up. Conversations are meant to
    be short — four people and a handful of turns, not eight paragraphs.
    """

    ACTIVE = "ACTIVE"
    WINDING_DOWN = "WINDING_DOWN"
    ENDED = "ENDED"


class SourceQualityTier(str, enum.Enum):
    """A rough, mechanical read on what kind of source this is (Packet 10,
    Part D) — never itself an unsupported factual claim, and never asked of
    a model. ``app.services.source_quality`` classifies purely from a
    source's domain/TLD; anything it cannot place with real confidence is
    ``UNKNOWN``, which is an entirely acceptable, honest answer, not a
    failure."""

    PRIMARY = "PRIMARY"
    OFFICIAL = "OFFICIAL"
    NEWS = "NEWS"
    ACADEMIC = "ACADEMIC"
    INDUSTRY = "INDUSTRY"
    BLOG = "BLOG"
    COMMUNITY = "COMMUNITY"
    UNKNOWN = "UNKNOWN"


class ReflectionStatus(str, enum.Enum):
    """Lifecycle of an agent's higher-level reflection (§15, Packet 9).

    Deliberately smaller than :class:`BeliefStatus`: a reflection is "a
    pattern I think I am noticing", not a proposition to be
    supported/contested/rejected the way a belief is. ACTIVE is every
    reflection's starting and ordinary state; SUPERSEDED is set mechanically,
    only on the specific prior reflection a later one names via
    ``supersedes_reflection_id`` — never inferred by topic similarity.
    """

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class AgentQuestionStatus(str, enum.Enum):
    """Lifecycle of one agent's persistent, personal unresolved curiosity.

    Deliberately the same five states across the whole feature, never more:
    OPEN is where every question starts and where explicit abandonment or
    revival lands it back. RESEARCHING marks it as the current target of a
    START_RESEARCH action — set only when an agent explicitly links a
    question to research it starts (never inferred from a research
    question's wording matching). Completing that research does NOT by
    itself move a question to RESOLVED: only a later reflection judging the
    actual intellectual outcome does that, or the question simply returns to
    OPEN/stays RESEARCHING/gets reformulated — see app.services.agent_questions.
    DORMANT is set only by time-based decay (never chosen by a model) and is
    always revivable by a genuine later engagement, never deleted. ABANDONED
    is the one status a model may set directly with no further evidence
    required — the agent simply said it is done with this question.
    """

    OPEN = "OPEN"
    RESEARCHING = "RESEARCHING"
    RESOLVED = "RESOLVED"
    DORMANT = "DORMANT"
    ABANDONED = "ABANDONED"


class ExposureType(str, enum.Enum):
    """How an agent came to know about something.

    Knowledge in the Village is partial by design. An exposure row is the only
    reason an agent may be shown a piece of information: the research wall makes
    things *discoverable*, not known.
    """

    CREATED = "CREATED"
    DIRECT_MESSAGE = "DIRECT_MESSAGE"
    CONVERSATION = "CONVERSATION"
    SHARED_FINDING = "SHARED_FINDING"
    WALL_GLIMPSE = "WALL_GLIMPSE"
    WALL_READ = "WALL_READ"
    SOURCE_READ = "SOURCE_READ"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"


class EventType(str, enum.Enum):
    """Every kind of thing the village records (§18)."""

    AGENT_WOKE = "AGENT_WOKE"
    # Beyond the build bible's §18 list: the action loop needs to record that a
    # decision was executed, and that one was rejected.
    AGENT_ACTED = "AGENT_ACTED"
    INVALID_AGENT_DECISION = "INVALID_AGENT_DECISION"
    PERIOD_ADVANCED = "PERIOD_ADVANCED"
    DAY_ADVANCED = "DAY_ADVANCED"
    FOUNDER_MESSAGE_DELIVERED = "FOUNDER_MESSAGE_DELIVERED"
    # Also beyond §18: retrieval failed or returned nothing, and the research
    # service stopped rather than let a model invent findings from nothing.
    RESEARCH_UNAVAILABLE = "RESEARCH_UNAVAILABLE"
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
    # Beyond §18: the wall and rabbit holes need finer-grained events than the
    # base list gives them — posting and reading are different acts, and a
    # rabbit hole's ending needs to say which ending.
    WALL_POST_READ = "WALL_POST_READ"
    RABBIT_HOLE_LEFT = "RABBIT_HOLE_LEFT"
    RABBIT_HOLE_RESOLVED = "RABBIT_HOLE_RESOLVED"
    RABBIT_HOLE_ABANDONED = "RABBIT_HOLE_ABANDONED"
    INTEREST_INCREASED = "INTEREST_INCREASED"
    INTEREST_DECREASED = "INTEREST_DECREASED"
    MEMORY_CREATED = "MEMORY_CREATED"
    FOUNDER_MESSAGE = "FOUNDER_MESSAGE"
    DAILY_REPORT_CREATED = "DAILY_REPORT_CREATED"
    # Packet 7: memory reinforcement/recall and the rest of interest evolution.
    # Creation is common enough (every new emerging interest) to log plainly;
    # reinforcement and recall are deliberately only logged when they reflect
    # a genuine repeat signal, never on routine context-building reads — see
    # app/services/memory.py.
    MEMORY_REINFORCED = "MEMORY_REINFORCED"
    MEMORY_RECALLED = "MEMORY_RECALLED"
    INTEREST_CREATED = "INTEREST_CREATED"
    INTEREST_DORMANT = "INTEREST_DORMANT"
    INTEREST_REVIVED = "INTEREST_REVIVED"
    # Packet 8: joining/leaving weren't separately logged before — joining
    # didn't exist as an action, and LEAVE_CONVERSATION silently mutated
    # participant_ids with no event at all.
    CONVERSATION_JOINED = "CONVERSATION_JOINED"
    CONVERSATION_LEFT = "CONVERSATION_LEFT"
    # Packet 9: the reflection engine and the daily Founder report. Recall is
    # only logged for a genuine gap, the same discipline as MEMORY_RECALLED.
    REFLECTION_CREATED = "REFLECTION_CREATED"
    REFLECTION_RECALLED = "REFLECTION_RECALLED"
    # Persistent unresolved curiosity (AgentQuestion): a personal, decaying,
    # agent-owned question, distinct from a Rabbit Hole (shared/collaborative)
    # and from ResearchSession.open_questions/follow_ups (which this feature
    # reads from, at creation time, rather than duplicating). See
    # app.services.agent_questions.
    QUESTION_CREATED = "QUESTION_CREATED"
    QUESTION_REVISITED = "QUESTION_REVISITED"
    QUESTION_LINKED_TO_RESEARCH = "QUESTION_LINKED_TO_RESEARCH"
    QUESTION_STATUS_CHANGED = "QUESTION_STATUS_CHANGED"
    QUESTION_DORMANT = "QUESTION_DORMANT"
    QUESTION_REFORMULATED = "QUESTION_REFORMULATED"
