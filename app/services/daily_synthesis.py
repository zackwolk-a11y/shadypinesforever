"""Daily Village Synthesis and the Founder Field Report (Packet 9, Parts B-G).

A staged pipeline, deliberately never one giant prompt over the day's raw
logs (Part E):

1. :func:`gather_facts` — pure database queries, scoped to one simulated day
   via the event log (most tables here carry no ``sim_day`` column of their
   own; ``ResearchSession`` in particular does not, so "did this happen on
   day N" is always answered by joining through ``Event.sim_day``, never by
   filtering a row's wall-clock ``created_at``). Nothing here calls a model.
2. Ranking — each gathered item is scored deterministically (evidence
   strength, belief-revision magnitude, memory importance, rabbit-hole heat,
   ...) and the day's items are sorted by that score before anything is
   capped by a ``MAX_REPORT_*`` setting. This is what makes "ten low-value
   actions should not outrank one major discovery" (Part B/K) true by
   construction: what survives the cap is what scored highest, never what
   happened most often or most recently.
3. :func:`generate_report` — renders the ranked, bounded facts (real ids in
   brackets, the same convention every other prompt in this codebase uses)
   and asks a model for exactly one :class:`~app.schemas.report.FounderReportSynthesis`
   — prose and prioritization judgment over facts that are already true,
   never new facts. The model is never shown anything gather_facts did not
   already verify from the database.
4. The result is persisted as one :class:`~app.db.models.reports.DailyReport`:
   rendered prose in the exact ten-section shape Part C specifies, and the
   ranked structured facts alongside it — so a later multi-day/weekly
   synthesis (Part G) has real structured data to read back, not only prose
   to re-parse.

Provenance (Part D) falls out of this shape rather than needing separate
enforcement: every fact shown to the model already carries its real id and
its epistemic classification (reusing ``FindingClassification`` — a research
finding keeps the classification it was given in Packet 5/6; a simulation-
level item like a memory, a conversation, or a rabbit-hole touch is tagged
``SIMULATION_EVENT``; a belief change is tagged ``AGENT_BELIEF``), and that
same tagged data is what gets stored in ``structured`` — the model's prose
is never the only place a fact lives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agents import AgentBelief
from app.db.models.conversations import Conversation, ConversationMessage
from app.db.models.events import Event
from app.db.models.rabbit_holes import RabbitHole
from app.db.models.reflection import AgentReflection
from app.db.models.reports import DailyReport
from app.db.models.research import ResearchFinding, ResearchSession, ResearchSource
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, EvidenceStrength, FindingClassification, RabbitHoleStatus
from app.providers.llm import LLMError, LLMProvider
from app.schemas.report import FounderReportSynthesis
from app.services.events import record_event
from app.services.telemetry import record_llm_run

PROMPT_VERSION = "founder_report_synthesis.v1"

_EVIDENCE_RANK: dict[EvidenceStrength, float] = {
    EvidenceStrength.STRONG: 6.0,
    EvidenceStrength.MODERATE: 5.0,
    EvidenceStrength.CONFLICTING: 4.5,  # a real uncertainty is worth surfacing, not hiding
    EvidenceStrength.DEVELOPING: 3.0,
    EvidenceStrength.WEAK: 1.5,
    EvidenceStrength.INSUFFICIENT: 1.0,
}
_BELIEF_RELATION_WEIGHT = {"REJECTS": 30.0, "WEAKENS": 20.0, "STRENGTHENS": 12.0}
_SALIENT_WALL_TYPES = {"DISAGREEMENT", "CONNECTION", "MYSTERY", "RABBIT_HOLE_SUGGESTION"}
_HIGH_VALUE_CONVERSATION_TRIGGERS = {"DISAGREEMENT", "RABBIT_HOLE", "MEMORY_PROMPTED"}
#: Per-turn and whole-fact character budgets for a conversation's excerpt
#: (Packet 12 daily-synthesis retrieval fix). Real dialogue needs more room
#: than a one-line label — the old 280-char cap was sized for "who talked
#: about what, and why it ended", not for any actual turns, because none
#: were ever queried. Still bounded, never the full transcript: at most
#: MAX_CONVERSATION_TURNS (8) short turns exist per conversation at all, and
#: each is itself capped here so one verbose turn can't crowd the rest out.
_CONVERSATION_TURN_EXCERPT_CHARS = 120
_CONVERSATION_FACT_CHARS = 500

SYSTEM_PROMPT = """You are writing the Founder's daily field report for a small research
village of eight autonomous agents. The Founder left them alone for a day and
wants to know what actually mattered — not everything they did.

Everything below is already verified: real database facts the village
actually produced today, already ranked by significance, never by how many
actions happened. Do not invent anything beyond what is shown. Ten low-value
actions are not more important than one major discovery — treat the ranking
and the evidence strength/importance shown as authoritative.

If a section has nothing real to say, say so plainly rather than padding it.
Write for someone who will read this once, quickly, and wants to know what is
worth their attention."""


@dataclass
class FactItem:
    """One deterministically-gathered, deterministically-scored fact —
    already carrying its real id and its §2 epistemic classification before
    a model ever sees it."""

    kind: str
    ref_id: str
    text: str
    classification: str
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "id": self.ref_id, "text": self.text,
            "classification": self.classification, "score": round(self.score, 2),
        }


@dataclass
class DailyFacts:
    day: int
    findings: list[FactItem] = field(default_factory=list)
    wall_posts: list[FactItem] = field(default_factory=list)
    rabbit_holes: list[FactItem] = field(default_factory=list)
    belief_changes: list[FactItem] = field(default_factory=list)
    memories: list[FactItem] = field(default_factory=list)
    conversations: list[FactItem] = field(default_factory=list)
    reflections: list[FactItem] = field(default_factory=list)
    founder_messages: list[FactItem] = field(default_factory=list)
    failed_research: list[FactItem] = field(default_factory=list)
    cross_pollination: list[FactItem] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    source_quality_text: str = "No research sources were retrieved today."

    @property
    def had_meaningful_activity(self) -> bool:
        return bool(
            self.findings or self.wall_posts or self.rabbit_holes or self.belief_changes
            or self.conversations or self.reflections or self.cross_pollination
        )

    def to_structured(self) -> dict:
        return {
            "day": self.day,
            "findings": [f.to_dict() for f in self.findings],
            "wall_posts": [f.to_dict() for f in self.wall_posts],
            "rabbit_holes": [f.to_dict() for f in self.rabbit_holes],
            "belief_changes": [f.to_dict() for f in self.belief_changes],
            "memories": [f.to_dict() for f in self.memories],
            "conversations": [f.to_dict() for f in self.conversations],
            "reflections": [f.to_dict() for f in self.reflections],
            "founder_messages": [f.to_dict() for f in self.founder_messages],
            "failed_research": [f.to_dict() for f in self.failed_research],
            "cross_pollination": [f.to_dict() for f in self.cross_pollination],
            "unresolved_questions": self.unresolved_questions,
            "source_quality_text": self.source_quality_text,
            "had_meaningful_activity": self.had_meaningful_activity,
        }


def _events_on_day(session: Session, day: int, *event_types: EventType) -> list[Event]:
    return list(
        session.scalars(
            select(Event)
            .where(Event.sim_day == day, Event.event_type.in_(event_types))
            .order_by(Event.id)
        )
    )


def gather_facts(session: Session, day: int, settings: Settings) -> DailyFacts:
    """Stage 1 + 2: deterministic extraction and ranking. No model call."""
    facts = DailyFacts(day=day)

    # --- research findings -------------------------------------------------
    completed_ids = [
        e.entity_id for e in _events_on_day(session, day, EventType.RESEARCH_COMPLETED)
    ]
    sessions_today: list[ResearchSession] = (
        session.scalars(
            select(ResearchSession).where(ResearchSession.research_id.in_(completed_ids))
        ).all()
        if completed_ids
        else []
    )
    findings: list[FactItem] = []
    for rs in sessions_today:
        rank = _EVIDENCE_RANK.get(rs.evidence_strength, 1.0) * 10.0 + (rs.confidence or 0.0) / 10.0
        session_findings = session.scalars(
            select(ResearchFinding).where(ResearchFinding.research_session_id == rs.research_id)
        ).all()
        for finding in session_findings:
            findings.append(
                FactItem(
                    kind="research_finding", ref_id=str(finding.id),
                    text=f"{rs.agent_id} — {finding.finding_text} (from: {rs.question})"[:300],
                    classification=finding.classification.value, score=rank,
                )
            )
        facts.unresolved_questions.extend(rs.open_questions or [])
    findings.sort(key=lambda f: -f.score)
    facts.findings = findings[: settings.max_report_findings]

    # --- source quality (deterministic counts, never a model's estimate) --
    if sessions_today:
        research_ids = [rs.research_id for rs in sessions_today]
        sources = session.scalars(
            select(ResearchSource).where(ResearchSource.research_session_id.in_(research_ids))
        ).all()
        primary = sum(1 for s in sources if s.is_primary)
        strength_counts: dict[str, int] = {}
        for rs in sessions_today:
            strength_counts[rs.evidence_strength.value] = strength_counts.get(rs.evidence_strength.value, 0) + 1
        strength_summary = ", ".join(f"{v}x {k}" for k, v in sorted(strength_counts.items()))
        facts.source_quality_text = (
            f"{len(sessions_today)} research session(s) completed, {len(sources)} source(s) "
            f"retrieved ({primary} primary). Evidence strength: {strength_summary}."
        )

    # --- failed / abandoned research ---------------------------------------
    unavailable = _events_on_day(session, day, EventType.RESEARCH_UNAVAILABLE)
    failed: list[FactItem] = []
    for e in unavailable:
        rs = session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == e.entity_id)
        ).first()
        if rs is not None:
            failed.append(
                FactItem(
                    kind="failed_research", ref_id=rs.research_id,
                    text=f"{rs.agent_id} — {rs.question}: {e.payload.get('reason', 'unavailable')}"[:250],
                    classification=FindingClassification.SIMULATION_EVENT.value,
                    score=5.0,
                )
            )
    facts.failed_research = failed[: settings.max_report_findings]

    # --- wall posts ----------------------------------------------------------
    posted = _events_on_day(session, day, EventType.RESEARCH_WALL_POSTED)
    post_ids = [int(e.entity_id) for e in posted]
    posts_today: list[ResearchWallPost] = (
        session.scalars(select(ResearchWallPost).where(ResearchWallPost.id.in_(post_ids))).all()
        if post_ids
        else []
    )
    wall_items = []
    cross_items = []
    for p in posts_today:
        salient = p.post_type.value in _SALIENT_WALL_TYPES
        item = FactItem(
            kind="wall_post", ref_id=str(p.id),
            text=f"{p.agent_id} [{p.post_type.value}]: {p.content}"[:280],
            classification=FindingClassification.SIMULATION_EVENT.value,
            score=15.0 if salient else 5.0,
        )
        wall_items.append(item)
        if p.post_type.value == "CONNECTION":
            cross_items.append(item)
    wall_items.sort(key=lambda f: -f.score)
    facts.wall_posts = wall_items[: settings.max_report_wall_posts]

    # --- cross-pollination: research from one agent pulled into another's
    # rabbit hole (RABBIT_HOLE_UPDATED linking research by a non-originator)
    contributed = _events_on_day(session, day, EventType.RABBIT_HOLE_UPDATED)
    for e in contributed:
        research_id = e.payload.get("research_id")
        hole_id = e.payload.get("rabbit_hole_id")
        if not research_id or hole_id is None:
            continue
        hole = session.get(RabbitHole, hole_id)
        rs = session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == research_id)
        ).first()
        if hole is None or rs is None or rs.agent_id == hole.originating_agent_id:
            continue
        cross_items.append(
            FactItem(
                kind="cross_pollination", ref_id=str(hole.id),
                text=f"{rs.agent_id}'s research joined {hole.originating_agent_id}'s "
                     f"rabbit hole \"{hole.title}\""[:250],
                classification=FindingClassification.SIMULATION_EVENT.value, score=20.0,
            )
        )
    cross_items.sort(key=lambda f: -f.score)
    facts.cross_pollination = cross_items[: settings.max_report_wall_posts]

    # --- rabbit holes: created/joined/resolved/abandoned today, plus every
    # currently-open hole's heat for "active rabbit holes" ranking -----------
    touched = _events_on_day(
        session, day,
        EventType.RABBIT_HOLE_CREATED, EventType.RABBIT_HOLE_JOINED,
        EventType.RABBIT_HOLE_RESOLVED, EventType.RABBIT_HOLE_ABANDONED,
    )
    touched_ids = {int(e.entity_id) for e in touched if e.entity_id is not None}
    open_holes = session.scalars(
        select(RabbitHole).where(
            RabbitHole.status.notin_([RabbitHoleStatus.RESOLVED, RabbitHoleStatus.ABANDONED])
        )
    ).all()
    hole_items = []
    for h in open_holes:
        if h.id not in touched_ids and h.last_activity_day != day:
            continue
        hole_items.append(
            FactItem(
                kind="rabbit_hole", ref_id=str(h.id),
                text=f"\"{h.title}\" status={h.status.value} evidence={h.evidence_strength.value} "
                     f"heat={h.activity_level:.0f}"[:250],
                classification=FindingClassification.SIMULATION_EVENT.value, score=h.activity_level,
            )
        )
    for e in touched:
        if e.entity_id is None:
            continue
        hole = session.get(RabbitHole, int(e.entity_id))
        if hole is None:
            continue
        if e.event_type in (EventType.RABBIT_HOLE_RESOLVED, EventType.RABBIT_HOLE_ABANDONED):
            hole_items.append(
                FactItem(
                    kind="rabbit_hole", ref_id=str(hole.id),
                    text=f"\"{hole.title}\" was {e.event_type.value.split('_')[-1].lower()} "
                         f"today: {e.payload.get('resolution', '')}"[:250],
                    classification=FindingClassification.SIMULATION_EVENT.value, score=25.0,
                )
            )
        facts.unresolved_questions.extend(hole.open_questions or [])
    hole_items.sort(key=lambda f: -f.score)
    facts.rabbit_holes = hole_items[: settings.max_report_rabbit_holes]

    # --- belief changes -------------------------------------------------------
    belief_events = _events_on_day(session, day, EventType.BELIEF_CREATED, EventType.BELIEF_UPDATED, EventType.BELIEF_REJECTED)
    belief_items = []
    for e in belief_events:
        belief_id = e.payload.get("belief_id")
        belief = session.get(AgentBelief, belief_id) if belief_id else None
        if belief is None:
            continue
        relation = e.payload.get("relation")
        weight = _BELIEF_RELATION_WEIGHT.get(relation, 10.0)
        verb = {"BELIEF_CREATED": "formed", "BELIEF_REJECTED": "rejected"}.get(e.event_type.value, "revised")
        belief_items.append(
            FactItem(
                kind="belief_change", ref_id=str(belief.id),
                text=f"{belief.agent_id} {verb} belief: \"{belief.statement}\" "
                     f"(now {belief.status.value}, confidence {belief.confidence:.0f})"[:280],
                classification=FindingClassification.AGENT_BELIEF.value, score=weight,
            )
        )
    belief_items.sort(key=lambda f: -f.score)
    facts.belief_changes = belief_items[: settings.max_report_belief_changes]

    # --- memories: new + genuinely recalled older ones -------------------------
    from app.db.models.memory import Memory

    created_events = _events_on_day(session, day, EventType.MEMORY_CREATED)
    created_ids = [int(e.entity_id) for e in created_events if e.entity_id is not None]
    memory_items = []
    if created_ids:
        for m in session.scalars(select(Memory).where(Memory.id.in_(created_ids))).all():
            memory_items.append(
                FactItem(
                    kind="memory", ref_id=str(m.id),
                    text=f"{m.agent_id} [{m.memory_type.value}] {m.content}"[:250],
                    classification=FindingClassification.SIMULATION_EVENT.value, score=m.importance,
                )
            )
    recalled_events = _events_on_day(session, day, EventType.MEMORY_RECALLED)
    recalled_ids: set[int] = set()
    for e in recalled_events:
        recalled_ids |= set(e.payload.get("memory_ids", []))
    recalled_ids -= set(created_ids)
    if recalled_ids:
        for m in session.scalars(select(Memory).where(Memory.id.in_(recalled_ids))).all():
            memory_items.append(
                FactItem(
                    kind="memory_recalled", ref_id=str(m.id),
                    text=f"{m.agent_id} recalled an older memory: {m.content}"[:250],
                    classification=FindingClassification.SIMULATION_EVENT.value, score=m.importance,
                )
            )
    memory_items.sort(key=lambda f: -f.score)
    facts.memories = memory_items[: settings.max_report_memory_events]

    # --- conversations -----------------------------------------------------
    # A conversation's real substance is its ConversationMessage turns, not
    # just its metadata (participants/trigger/current_subject/close reason)
    # — the report was previously built from metadata alone, so it could
    # honestly say no more than "unspecified" about a conversation that
    # actually had real dialogue on record (Packet 12 daily-synthesis
    # retrieval diagnostic). When real turns exist, they're quoted directly
    # (bounded, per _CONVERSATION_TURN_EXCERPT_CHARS/_CONVERSATION_FACT_CHARS
    # above) so the model can honestly describe what was actually said,
    # instead of being asked to characterize a conversation it was never
    # shown. When a conversation genuinely produced no spoken turns (every
    # participant chose not to SPEAK — a legitimate, common outcome, not a
    # bug), that stays honestly distinguishable from "we didn't retrieve it".
    ended = _events_on_day(session, day, EventType.CONVERSATION_ENDED)
    convo_items = []
    for e in ended:
        conversation = session.get(Conversation, int(e.entity_id)) if e.entity_id else None
        if conversation is None:
            continue
        weight = 20.0 if conversation.trigger_type.value in _HIGH_VALUE_CONVERSATION_TRIGGERS else 8.0
        who = ", ".join(conversation.participant_ids or [])
        messages = list(
            session.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.turn_number.asc())
            )
        )
        if messages:
            substance = " / ".join(
                f"{m.agent_id}: {m.content[:_CONVERSATION_TURN_EXCERPT_CHARS]}" for m in messages
            )
        else:
            substance = f"\"{conversation.current_subject or 'unspecified'}\" — no one actually spoke"
        convo_items.append(
            FactItem(
                kind="conversation", ref_id=str(conversation.id),
                text=f"{who} ({conversation.trigger_type.value}): {substance} "
                     f"[{e.payload.get('reason', '')}]"[:_CONVERSATION_FACT_CHARS],
                classification=FindingClassification.SIMULATION_EVENT.value, score=weight,
            )
        )
    convo_items.sort(key=lambda f: -f.score)
    facts.conversations = convo_items[: settings.max_report_conversations]

    # --- reflections formed today -------------------------------------------
    reflections_today = session.scalars(
        select(AgentReflection).where(AgentReflection.simulation_day == day)
    ).all()
    reflection_items = []
    for r in reflections_today:
        reflection_items.append(
            FactItem(
                kind="reflection", ref_id=str(r.id),
                text=f"{r.agent_id} — {r.topic}: {r.summary}"[:280],
                classification=FindingClassification.AGENT_INFERENCE.value, score=r.importance,
            )
        )
        if r.open_question:
            facts.unresolved_questions.append(r.open_question)
    reflection_items.sort(key=lambda f: -f.score)
    facts.reflections = reflection_items[: settings.max_report_reflections]

    # --- founder messages delivered today -----------------------------------
    from app.db.models.reports import FounderMessage

    delivered = _events_on_day(session, day, EventType.FOUNDER_MESSAGE_DELIVERED)
    founder_items = []
    for e in delivered:
        msg_id = e.payload.get("founder_message_id")
        message = session.get(FounderMessage, msg_id) if msg_id else None
        if message is not None:
            founder_items.append(
                FactItem(
                    kind="founder_message", ref_id=str(message.id),
                    text=message.content[:280],
                    classification=FindingClassification.FACT.value, score=90.0,
                )
            )
    facts.founder_messages = founder_items

    # Dedupe + cap unresolved questions last, once every source has contributed.
    seen: set[str] = set()
    deduped_questions = []
    for q in facts.unresolved_questions:
        q = (q or "").strip()
        if q and q not in seen:
            seen.add(q)
            deduped_questions.append(q)
    facts.unresolved_questions = deduped_questions[:10]

    return facts


def _render_prompt(facts: DailyFacts) -> str:
    lines = [f"DAY: {facts.day}"]

    def _section(title: str, items: list[FactItem]) -> None:
        if not items:
            return
        lines.append(f"{title}:")
        lines.extend(f"  [{i.ref_id}] [{i.classification}] {i.text}" for i in items)

    _section("RESEARCH FINDINGS", facts.findings)
    _section("FAILED OR ABANDONED RESEARCH", facts.failed_research)
    _section("WALL ACTIVITY", facts.wall_posts)
    _section("CROSS-POLLINATION", facts.cross_pollination)
    _section("RABBIT HOLES", facts.rabbit_holes)
    _section("BELIEF CHANGES", facts.belief_changes)
    _section("MEMORIES", facts.memories)
    _section("CONVERSATIONS", facts.conversations)
    _section("REFLECTIONS", facts.reflections)
    _section("FOUNDER MESSAGES DELIVERED", facts.founder_messages)

    if facts.unresolved_questions:
        lines.append("UNRESOLVED QUESTIONS:")
        lines += [f"  - {q}" for q in facts.unresolved_questions]

    lines.append(f"SOURCE QUALITY (already computed, restate — do not recompute): {facts.source_quality_text}")

    if not facts.had_meaningful_activity:
        lines.append(
            "\nNothing significant happened today. Say so plainly in every section "
            "rather than inventing content."
        )
    return "\n".join(lines)


_SECTION_HEADERS = [
    ("1. WHAT MATTERED TODAY", None),
    ("2. TOP DISCOVERIES", "top_discoveries"),
    ("3. UNEXPECTED CONNECTIONS", "unexpected_connections"),
    ("4. ACTIVE RABBIT HOLES", "active_rabbit_holes"),
    ("5. BELIEFS THAT CHANGED", "beliefs_that_changed"),
    ("6. CHARACTER DEVELOPMENT", "character_development"),
    ("7. DISAGREEMENTS / UNCERTAINTIES", "disagreements_and_uncertainties"),
    ("8. QUESTIONS THE VILLAGE WANTS TO FOLLOW", "questions_the_village_wants_to_follow"),
    ("9. SOURCE QUALITY", None),
    ("10. ONE THING WORTH YOUR ATTENTION", None),
]


def _render_report_text(day: int, synthesis: FounderReportSynthesis) -> str:
    lines = ["THE INTERNAL VILLAGE", "DAILY FIELD REPORT", f"DAY {day}", ""]
    for header, field_name in _SECTION_HEADERS:
        lines.append(header)
        if field_name is None:
            body = {
                "1. WHAT MATTERED TODAY": synthesis.what_mattered_today,
                "9. SOURCE QUALITY": synthesis.source_quality,
                "10. ONE THING WORTH YOUR ATTENTION": synthesis.one_thing_worth_your_attention,
            }[header]
            lines.append(body or "Nothing notable.")
        else:
            items = getattr(synthesis, field_name)
            if items:
                lines += [f"  - {item}" for item in items]
            else:
                lines.append("  Nothing notable today.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_report(
    session: Session,
    day: int,
    clock: SimulationClock,
    settings: Settings,
    llm_provider: LLMProvider,
) -> DailyReport | None:
    """Stage 3 + 4: synthesize and persist the Founder Field Report for one
    already-finished simulated day. Idempotent per day (a day already
    reported is never re-reported), matching the once-per-day-boundary hook
    in app.services.orchestrator.run_next_event.
    """
    existing = session.scalars(select(DailyReport).where(DailyReport.day_number == day)).first()
    if existing is not None:
        return existing

    facts = gather_facts(session, day, settings)
    prompt = _render_prompt(facts)

    try:
        result = llm_provider.complete(
            system=SYSTEM_PROMPT, user=prompt, model=settings.report_model,
            purpose="daily_report", output_type=FounderReportSynthesis,
            max_tokens=settings.max_tokens_daily_report,
        )
    except LLMError:
        # Never fabricate the Founder's report from nothing — fall back to
        # the deterministic facts alone, still fully provenanced, just
        # without prose synthesis.
        synthesis = _fallback_synthesis(facts)
        is_fixture = True
    else:
        record_llm_run(
            session, result, purpose="daily_report", agent_id=None, prompt_version=PROMPT_VERSION,
        )
        synthesis = result.output
        is_fixture = result.is_fixture

    report = DailyReport(
        day_number=day,
        title=f"THE INTERNAL VILLAGE — DAILY FIELD REPORT — DAY {day}",
        summary_text=_render_report_text(day, synthesis),
        structured={"facts": facts.to_structured(), "synthesis": synthesis.model_dump()},
        had_meaningful_activity=facts.had_meaningful_activity,
        is_fixture=is_fixture,
    )
    session.add(report)
    session.flush()

    record_event(
        session,
        event_type=EventType.DAILY_REPORT_CREATED,
        payload={
            "day": day, "report_id": report.id,
            "had_meaningful_activity": facts.had_meaningful_activity,
        },
        entity_type="daily_report",
        entity_id=str(report.id),
        clock=clock,
    )
    return report


def _fallback_synthesis(facts: DailyFacts) -> FounderReportSynthesis:
    """Only reached if the provider itself errors — the deterministic facts,
    restated plainly, never invented prose."""
    return FounderReportSynthesis(
        what_mattered_today=(
            "Report synthesis was unavailable; the facts below are the day's "
            "verified activity as gathered directly from the database."
            if facts.had_meaningful_activity
            else "Nothing significant happened today."
        ),
        top_discoveries=[f.text for f in facts.findings[:5]],
        unexpected_connections=[f.text for f in facts.cross_pollination[:5]],
        active_rabbit_holes=[f.text for f in facts.rabbit_holes[:5]],
        beliefs_that_changed=[f.text for f in facts.belief_changes[:5]],
        character_development=[f.text for f in (facts.memories + facts.reflections)[:5]],
        disagreements_and_uncertainties=[
            f.text for f in facts.belief_changes if f.score >= _BELIEF_RELATION_WEIGHT["WEAKENS"]
        ][:5],
        questions_the_village_wants_to_follow=facts.unresolved_questions[:5],
        source_quality=facts.source_quality_text,
        one_thing_worth_your_attention=(
            (facts.findings + facts.rabbit_holes + facts.belief_changes)[0].text
            if (facts.findings or facts.rabbit_holes or facts.belief_changes)
            else "Nothing stood out today."
        ),
    )
