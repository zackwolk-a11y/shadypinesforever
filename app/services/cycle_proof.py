"""Does the Village actually function? — the one-cycle proof, read from rows.

The question is not "do the tests pass" but whether the database shows one
complete, causally linked chain:

    voluntary meeting -> meaningful conversation -> remembered experience
    -> executed action

Every link is judged only from persisted facts (events, conversation turns,
memories, intentions, produced entities), never from what an agent *said*
happened. Each link gets PROVEN / PARTIAL / MISSING with the reason and the
row ids behind it, and the whole chain is only called GENUINE when every
decision in it came from a live model (``is_fixture`` false). A fixture run
can prove the wiring; it can never prove the behaviour.

Read-only: nothing here writes to the database. Used by
``scripts/prove_cycle.py``; usable from the Fishbowl or the Director too.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import asdict, dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.conversations import Conversation, ConversationMessage
from app.db.models.conversations import Message
from app.db.models.events import Event
from app.db.models.exposure import AgentExposure
from app.db.models.intentions import AgentFeedback, Intention
from app.db.models.rabbit_holes import RabbitHole
from app.db.models.wall import ResearchWallPost
from app.db.models.memory import Memory
from app.db.models.research import ResearchFinding, ResearchSession
from app.db.models.telemetry import LLMRun
from app.domain.enums import ConversationTrigger, EventType, IntentionStatus

PROVEN, PARTIAL, MISSING = "PROVEN", "PARTIAL", "MISSING"

#: Actions whose result exists outside the actor's own head — something
#: another resident can read, receive, or join. A private note or a belief
#: change is real, but it isn't the Village *doing* something.
SHARED_EFFECT_ACTIONS = {
    "START_RESEARCH", "POST_TO_WALL", "CREATE_RABBIT_HOLE", "CONTRIBUTE_TO_RABBIT_HOLE",
    "RESOLVE_RABBIT_HOLE", "SEND_MESSAGE", "ASK_QUESTION", "CHALLENGE_CLAIM", "START_CONVERSATION",
}

#: "Meaningful" is deliberately mechanical and modest: a real back-and-forth
#: (at least two changes of speaker, so A -> B -> A at minimum), not one line
#: and a reply, and a concrete commitment made inside it.
MIN_TURNS = 3
MIN_SPEAKERS = 2
MIN_REPLIES = 2


@dataclass
class Link:
    name: str
    status: str
    why: str
    facts: dict = field(default_factory=dict)


@dataclass
class Cycle:
    intention_id: int
    owner: str
    links: list[Link]
    live: bool
    fixture_turns: int
    #: Why a complete chain still isn't genuine, if it isn't.
    not_live_because: str | None = None

    @property
    def score(self) -> int:
        weights = {PROVEN: 2, PARTIAL: 1, MISSING: 0}
        return sum(weights[link.status] for link in self.links)

    @property
    def complete(self) -> bool:
        return all(link.status == PROVEN for link in self.links)

    @property
    def verdict(self) -> str:
        if self.complete and self.live:
            return "GENUINE CYCLE PROVEN"
        if self.complete and self.fixture_turns == 0 and self.not_live_because:
            return f"CYCLE PROVEN ON LIVE DECISIONS, BUT {self.not_live_because.upper()}"
        if self.complete:
            return "CYCLE WIRING PROVEN (fixture provider — not evidence of real behaviour)"
        return "PARTIAL CYCLE"

    def as_dict(self) -> dict:
        return {
            "intention_id": self.intention_id, "owner": self.owner, "verdict": self.verdict,
            "live": self.live, "fixture_turns": self.fixture_turns, "score": self.score,
            "not_live_because": self.not_live_because,
            "links": [asdict(link) for link in self.links],
        }


def _acted(session: Session, correlation_id: str | None) -> list[Event]:
    if not correlation_id:
        return []
    return list(
        session.scalars(
            select(Event)
            .where(Event.correlation_id == correlation_id, Event.event_type == EventType.AGENT_ACTED)
            .order_by(Event.id)
        )
    )


def _clip(text: str | None, n: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


_WORD = re.compile(r"[a-z][a-z']{3,}")
_STOP = {
    "that", "this", "with", "have", "what", "about", "there", "their", "would", "could",
    "should", "from", "just", "like", "they", "them", "then", "than", "been", "were", "will",
    "into", "your", "also", "more", "some", "really", "think", "know", "want", "maybe", "after",
    "fixture", "said", "going", "it's", "i'll", "let's", "we're", "you're", "does", "here",
}


def _content_words(text: str | None) -> set[str]:
    """Crude, deliberately lenient overlap key: content words cut to 5
    letters, so "recover"/"recovery" and "garden"/"gardening" still meet. A
    mechanical proxy only — the report says when to check by eye."""
    return {w[:5] for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def _norm(text: str | None) -> str:
    return " ".join((text or "").split())


def _session_starts(session: Session) -> list[int]:
    return list(
        session.scalars(
            select(Event.id).where(Event.event_type == EventType.TRIAL_SESSION_STARTED).order_by(Event.id)
        )
    )


def _session_of(starts: list[int], event_id: int | None) -> int | None:
    if not starts or event_id is None:
        return None
    return bisect.bisect_right(starts, event_id)


def _meeting(session: Session, conv: Conversation, owner: str) -> tuple[Link, list[Event]]:
    turns = list(
        session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.turn_number)
        )
    )
    facts = {
        "conversation_id": conv.id, "trigger": conv.trigger_type.value,
        "started": f"day {conv.started_sim_day} {conv.started_sim_period}",
    }
    if conv.trigger_type is ConversationTrigger.MORNING_GATHERING:
        return Link("voluntary meeting", MISSING,
                    "the intention came from the compulsory morning gathering, which nobody chose",
                    facts), []
    initiating = [
        e for e in _acted(session, conv.correlation_id)
        if "START_CONVERSATION" in (e.payload.get("actions") or [])
    ]
    joined_by_owner = session.scalars(
        select(Event.id).where(
            Event.event_type == EventType.CONVERSATION_JOINED, Event.agent_id == owner,
            Event.payload["conversation_id"].as_integer() == conv.id,
        )
    ).first()
    if not initiating:
        return Link("voluntary meeting", MISSING, "no agent decision started this conversation", facts), []
    start = initiating[0]
    initiator = start.agent_id
    invitees = [p for p in {t.agent_id for t in turns} if p != initiator]
    first_reply = next((t for t in turns if t.agent_id != initiator), None)
    facts.update({
        "initiator": initiator,
        "initiator_reason": _clip(start.payload.get("summary"), 200),
        "opener": _clip(turns[0].content if turns else None, 200),
        "target_chosen_by": "engine" if (start.payload.get("normalized") or {}).get("target_inferred") else "agent",
        "replied": sorted(invitees),
        "first_reply": _clip(first_reply.content if first_reply else None, 200),
        "owner_joined_midway": bool(joined_by_owner),
        "agent_acted_event_id": start.id,
    })
    if facts["target_chosen_by"] == "engine":
        return Link("voluntary meeting", PARTIAL,
                    "an agent started it, but the engine picked who it was with", facts), [start]
    if not invitees:
        return Link("voluntary meeting", PARTIAL,
                    "an agent reached out, but nobody chose to answer", facts), [start]
    return Link(
        "voluntary meeting", PROVEN,
        f"{initiator} chose to start it and {', '.join(sorted(invitees))} chose to reply", facts,
    ), [start]


def _conversation(session: Session, conv: Conversation, intention: Intention) -> tuple[Link, list[Event]]:
    turns = list(
        session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.turn_number)
        )
    )
    speakers = {t.agent_id for t in turns}
    replies = sum(1 for a, b in zip(turns, turns[1:]) if a.agent_id != b.agent_id)
    # Reciprocity, per the Healthy Village evidence rule: each response must
    # have had access to what it answers (an exposure row for the previous
    # line — a hard check) and should engage its content (shared words — a
    # soft check, listed for review rather than failed, since a real reply
    # can paraphrase).
    reply_pairs = [(a, b) for a, b in zip(turns, turns[1:]) if a.agent_id != b.agent_id]
    without_access = [
        b.turn_number for a, b in reply_pairs
        if session.scalars(
            select(AgentExposure.id).where(
                AgentExposure.agent_id == b.agent_id,
                AgentExposure.entity_type == "conversation_message",
                AgentExposure.entity_id == str(a.id),
            ).limit(1)
        ).first() is None
    ]
    to_review = [
        b.turn_number for a, b in reply_pairs
        if not (_content_words(a.content) & _content_words(b.content))
    ]
    forming = [
        e for e in _acted(session, conv.correlation_id)
        if (e.payload.get("intentions") or {}).get("formed") == intention.id
    ]
    facts = {
        "turns": len(turns), "speakers": sorted(speakers), "replies_to_someone_else": replies,
        "ended": conv.ending_reason, "intention_said": _clip(intention.description, 200),
        "intention_planned_action": intention.planned_action,
        "intention_to": intention.with_agent_id,
        "replies_without_access_to_what_they_answer": without_access,
        "replies_sharing_no_words_with_what_they_answer (check by eye)": to_review,
        "transcript": [f"{t.turn_number}. {t.agent_id}: {_clip(t.content, 220)}" for t in turns][:12],
    }
    if without_access:
        return Link(
            "meaningful conversation", PARTIAL,
            f"turn(s) {without_access} answered a line the speaker had no record of hearing", facts,
        ), forming
    if len(turns) >= MIN_TURNS and len(speakers) >= MIN_SPEAKERS and replies >= MIN_REPLIES:
        return Link(
            "meaningful conversation", PROVEN,
            f"{len(turns)} turns between {len(speakers)} residents, and {intention.agent_id} "
            f"committed to something concrete in it [I{intention.id}]", facts,
        ), forming
    return Link(
        "meaningful conversation", PARTIAL,
        f"a commitment was made, but the exchange was thin ({len(turns)} turns, "
        f"{len(speakers)} speakers, {replies} changes of speaker)", facts,
    ), forming


def _memory(session: Session, conv: Conversation, intention: Intention) -> Link:
    owned = list(
        session.scalars(
            select(Memory).where(Memory.agent_id == intention.agent_id).order_by(Memory.id)
        )
    )
    about = [m for m in owned if conv.id in (m.related_conversation_ids or [])]
    carrying = [m for m in about if f"[I{intention.id}]" in (m.content or "")]
    fulfilled = session.get(Event, intention.closed_event_id) if intention.closed_event_id else None
    woke = None
    used_ids: list[int] = []
    if fulfilled is not None and fulfilled.correlation_id:
        woke = session.scalars(
            select(Event).where(
                Event.correlation_id == fulfilled.correlation_id, Event.event_type == EventType.AGENT_WOKE,
            )
        ).first()
        for used in session.scalars(
            select(Event).where(
                Event.correlation_id == fulfilled.correlation_id, Event.event_type == EventType.MEMORY_USED,
            )
        ):
            used_ids += used.payload.get("memory_ids") or []
    shown_ids = set((woke.payload.get("shown_memory_ids") or []) if woke is not None else [])
    cited = [m for m in about if m.id in used_ids]
    shown = [m for m in about if m.id in shown_ids]

    # Accuracy: every quotation in the memory must be something actually said
    # in that conversation (or the promise / subject text itself) — the guard
    # against invented memories.
    sayable = [_norm(t.content) for t in session.scalars(
        select(ConversationMessage).where(ConversationMessage.conversation_id == conv.id)
    )]
    sayable += [_norm(conv.current_subject)]
    sayable += [_norm(i.description) for i in session.scalars(
        select(Intention).where(Intention.source_conversation_id == conv.id)
    )]
    def _unverified(m: Memory) -> list[str]:
        bad = []
        for quote in re.findall(r'"([^"]+)"', m.content or ""):
            q = _norm(quote).rstrip("…").strip()
            if q and not any(q in s for s in sayable):
                bad.append(_clip(quote, 80))
        return bad
    chosen = (cited or shown or carrying or about)[:1]
    unverified = _unverified(chosen[0]) if chosen else []

    # Survival: when the trial records sessions, the act must come in a later
    # session than the conversation, so the memory provably outlived a break.
    starts = _session_starts(session)
    ended = session.scalars(
        select(Event.id).where(
            Event.event_type == EventType.CONVERSATION_ENDED, Event.entity_id == str(conv.id),
        )
    ).first()
    talk_session = _session_of(starts, ended)
    act_session = _session_of(starts, fulfilled.id if fulfilled is not None else None)
    facts = {
        "conversation_memory_ids": [m.id for m in about],
        "memory_text": _clip(chosen[0].content, 400) if chosen else None,
        "quotes_not_found_in_the_conversation": unverified,
        "shown_in_follow_through_turn": [m.id for m in shown],
        "cited_by_follow_through_decision": [m.id for m in cited],
        "all_memories_cited_that_turn": used_ids,
        "conversation_session": talk_session,
        "follow_through_session": act_session,
    }
    if about and unverified:
        return Link("remembered experience", PARTIAL,
                    f"the memory quotes words that weren't said in the conversation: {unverified}", facts)
    if cited and starts and (talk_session is None or act_session is None or act_session <= talk_session):
        return Link("remembered experience", PARTIAL,
                    "the memory was cited, but in the same session as the conversation — it hasn't been "
                    "shown to survive into a later session", facts)
    if cited:
        later = f" in session {act_session}, after the conversation in session {talk_session}" if starts else ""
        return Link("remembered experience", PROVEN,
                    f"{intention.agent_id} kept an accurate memory of the conversation [M{cited[0].id}] and "
                    f"its decision to act cited it{later}", facts)
    if shown:
        return Link("remembered experience", PARTIAL,
                    "the memory was in front of the agent when it acted, but its decision didn't cite it",
                    facts)
    if about:
        return Link("remembered experience", PARTIAL,
                    "the conversation was remembered, but that memory wasn't part of the decision to act",
                    facts)
    return Link("remembered experience", MISSING, "no memory of this conversation exists", facts)


def _action(session: Session, intention: Intention) -> tuple[Link, list[Event]]:
    fulfilled = session.get(Event, intention.closed_event_id) if intention.closed_event_id else None
    entity = intention.fulfilled_entity or {}
    facts = {
        "action": intention.fulfilled_by_action, "explicit_link": intention.fulfilled_explicitly,
        "formed": f"day {intention.created_sim_day} {intention.created_sim_period}",
        "done": f"day {intention.closed_sim_day} {intention.closed_sim_period}",
        "entity": entity,
    }
    acting = _acted(session, fulfilled.correlation_id if fulfilled is not None else None)
    if acting:
        facts["agent_acted_event_id"] = acting[0].id
        facts["decision_summary"] = _clip(acting[0].payload.get("summary"), 200)
    if entity.get("type") == "research_session" and entity.get("id"):
        rs = session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == entity["id"])
        ).first()
        if rs is not None:
            facts["research_question"] = _clip(rs.question, 200)
            facts["research_status"] = rs.status.value
            facts["research_findings"] = session.scalar(
                select(func.count()).select_from(ResearchFinding)
                .where(ResearchFinding.research_session_id == rs.research_id)
            ) or 0
            facts["research_interpretation"] = _clip(rs.interpretation, 300)
            facts["research_on_fixture_search"] = bool(rs.is_fixture)
    if fulfilled is None or intention.status is not IntentionStatus.FULFILLED:
        return Link("executed action", MISSING, "nothing was carried out", facts), []
    same_turn = intention.source_event_id is not None and fulfilled.correlation_id and (
        session.get(Event, intention.source_event_id).correlation_id == fulfilled.correlation_id
    )
    if same_turn:
        return Link("executed action", PARTIAL, "formed and 'fulfilled' in the same turn", facts), acting
    if intention.fulfilled_by_action not in SHARED_EFFECT_ACTIONS:
        return Link("executed action", PARTIAL,
                    f"carried out privately ({intention.fulfilled_by_action}) — nothing another "
                    "resident can see", facts), acting
    if facts.get("research_status") not in (None, "COMPLETED"):
        return Link("executed action", PARTIAL,
                    f"research was started but ended {facts['research_status']}", facts), acting
    if not intention.fulfilled_explicitly:
        return Link("executed action", PARTIAL,
                    "a matching action happened later, but the agent didn't say it was this intention",
                    facts), acting
    # Effect matches the promise: the right recipient, and content about the
    # same thing (Healthy Village evidence rule for an executed action).
    produced_text, recipients = _produced(session, entity, facts)
    facts["produced_text"] = _clip(produced_text, 240)
    if recipients is not None:
        facts["recipients"] = recipients
    if intention.with_agent_id and recipients is not None and intention.with_agent_id not in recipients \
            and intention.planned_action in ("SEND_MESSAGE", "ASK_QUESTION", "START_CONVERSATION"):
        return Link("executed action", PARTIAL,
                    f"promised to {intention.with_agent_id}, but it went to {', '.join(recipients) or 'no one'}",
                    facts), acting
    shared = sorted(_content_words(intention.description) & _content_words(produced_text))
    facts["words_shared_with_the_promise"] = shared
    if produced_text and not shared:
        return Link("executed action", PARTIAL,
                    "the action's content shares no words with what was promised — check by eye", facts), acting
    return Link(
        "executed action", PROVEN,
        f"in a later turn {intention.agent_id} did {intention.fulfilled_by_action} and linked it to "
        f"[I{intention.id}]", facts,
    ), acting


def _produced(session: Session, entity: dict, facts: dict) -> tuple[str, list[str] | None]:
    """The text the follow-through action actually put into the world, and
    who received it (for directed actions)."""
    kind, ident = entity.get("type"), entity.get("id")
    if kind == "message" and ident:
        msg = session.get(Message, int(ident))
        if msg is not None:
            return msg.content, [msg.recipient_agent_id] if msg.recipient_agent_id else []
    if kind == "wall_post" and ident:
        post = session.get(ResearchWallPost, int(ident))
        if post is not None:
            return post.content, None
    if kind == "rabbit_hole" and ident:
        hole = session.get(RabbitHole, int(ident))
        if hole is not None:
            return f"{hole.title} {hole.description or ''}", None
    if kind == "conversation" and ident:
        convo = session.get(Conversation, int(ident))
        first = session.scalars(
            select(ConversationMessage).where(ConversationMessage.conversation_id == int(ident))
            .order_by(ConversationMessage.turn_number).limit(1)
        ).first()
        if convo is not None:
            return (first.content if first else ""), list(convo.participant_ids or [])
    if kind == "research_session":
        return facts.get("research_question") or "", None
    if kind == "memory" and ident:
        mem = session.get(Memory, int(ident))
        if mem is not None:
            return mem.content, None
    return "", None


def evaluate(session: Session) -> list[Cycle]:
    """Every candidate chain, best first."""
    cycles: list[Cycle] = []
    for intention in session.scalars(
        select(Intention).where(Intention.source_conversation_id.is_not(None)).order_by(Intention.id)
    ):
        conv = session.get(Conversation, intention.source_conversation_id)
        if conv is None:
            continue
        meeting, start_events = _meeting(session, conv, intention.agent_id)
        talk, forming_events = _conversation(session, conv, intention)
        remembered = _memory(session, conv, intention)
        action, acting_events = _action(session, intention)
        chain = [*start_events, *forming_events, *acting_events]
        fixture_turns = sum(1 for e in chain if e.payload.get("is_fixture"))
        not_live = None
        if not chain:
            not_live = "no decisions found for the chain"
        elif fixture_turns:
            not_live = f"{fixture_turns} decision(s) came from the fixture provider"
        elif action.facts.get("research_on_fixture_search"):
            not_live = "the research ran on the fixture search provider (set RESEARCH_PROVIDER=tavily)"
        cycles.append(Cycle(
            intention_id=intention.id, owner=intention.agent_id,
            links=[meeting, talk, remembered, action],
            live=not_live is None, fixture_turns=fixture_turns, not_live_because=not_live,
        ))
    cycles.sort(key=lambda c: (not c.complete, not c.live, -c.score, c.intention_id))
    return cycles


def village_metrics(session: Session) -> dict:
    """The surrounding numbers a reader needs to judge one cycle in context."""
    def count(event_type: EventType) -> int:
        return session.scalar(
            select(func.count()).select_from(Event).where(Event.event_type == event_type)
        ) or 0

    statuses = dict(
        session.execute(select(Intention.status, func.count()).group_by(Intention.status)).all()
    )
    judged = list(session.scalars(select(AgentFeedback).where(AgentFeedback.addressed.is_not(None))))
    by_kind: dict[str, dict] = {}
    for row in judged:
        bucket = by_kind.setdefault(row.kind, {"judged": 0, "addressed": 0})
        bucket["judged"] += 1
        bucket["addressed"] += 1 if row.addressed else 0
    agent_started = 0
    for conv in session.scalars(select(Conversation)):
        if conv.trigger_type is not ConversationTrigger.MORNING_GATHERING:
            agent_started += 1
    live_runs = session.scalar(
        select(func.count()).select_from(LLMRun).where(LLMRun.is_fixture.is_(False))
    ) or 0
    fixture_runs = session.scalar(
        select(func.count()).select_from(LLMRun).where(LLMRun.is_fixture.is_(True))
    ) or 0
    tokens = session.execute(
        select(func.coalesce(func.sum(LLMRun.input_tokens), 0), func.coalesce(func.sum(LLMRun.output_tokens), 0))
    ).one()
    # The explainer's "needs continued scrutiny" list, counted rather than
    # eyeballed: repetitive dialogue, ignored refusals, invented memories.
    lines: dict[tuple[str, str], int] = {}
    for msg in session.scalars(select(ConversationMessage)):
        key = (msg.agent_id, _norm(msg.content).lower())
        lines[key] = lines.get(key, 0) + 1
    repeated = sum(n - 1 for n in lines.values() if n > 1)
    declined = 0
    for left in session.scalars(select(Event).where(Event.event_type == EventType.CONVERSATION_LEFT)):
        conv_id = left.payload.get("conversation_id")
        spoke = session.scalars(
            select(ConversationMessage.id).where(
                ConversationMessage.conversation_id == conv_id, ConversationMessage.agent_id == left.agent_id,
            ).limit(1)
        ).first()
        declined += 0 if spoke else 1
    invented = 0
    for mem in session.scalars(select(Memory).where(Memory.content.contains("Talked with"))):
        for conv_id in mem.related_conversation_ids or []:
            conv = session.get(Conversation, conv_id)
            if conv is None:
                continue
            said = [_norm(t.content) for t in session.scalars(
                select(ConversationMessage).where(ConversationMessage.conversation_id == conv_id))]
            said += [_norm(conv.current_subject)] + [_norm(i.description) for i in session.scalars(
                select(Intention).where(Intention.source_conversation_id == conv_id))]
            quotes = [_norm(q).rstrip("…").strip() for q in re.findall(r'"([^"]+)"', mem.content or "")]
            if any(q and not any(q in s for s in said) for q in quotes):
                invented += 1
                break
    return {
        "trial_sessions": len(_session_starts(session)),
        "activations": count(EventType.AGENT_WOKE),
        "decisions_executed": count(EventType.AGENT_ACTED),
        "invalid_decisions": count(EventType.INVALID_AGENT_DECISION),
        "conversations_started_by_agents": agent_started,
        "conversation_turns": session.scalar(select(func.count()).select_from(ConversationMessage)) or 0,
        "intentions": {s.value: n for s, n in statuses.items()},
        "memory_used_events": count(EventType.MEMORY_USED),
        "feedback_notes": session.scalar(select(func.count()).select_from(AgentFeedback)) or 0,
        "feedback_judged": by_kind,
        "repeated_lines": repeated,
        "invitations_declined_without_speaking": declined,
        "conversation_memories_with_unverified_quotes": invented,
        "provider_pauses": count(EventType.SIMULATION_PAUSED_PROVIDER_ERROR)
        + count(EventType.SIMULATION_PAUSED_RATE_LIMIT),
        "llm_runs_live": live_runs,
        "llm_runs_fixture": fixture_runs,
        "tokens_in": int(tokens[0]), "tokens_out": int(tokens[1]),
    }


def render_markdown(cycle: Cycle | None, metrics: dict, header: dict) -> str:
    lines = ["# Village cycle proof", ""]
    for key, value in header.items():
        lines.append(f"- **{key}:** {value}")
    lines.append("")
    if cycle is None:
        lines += ["## Verdict: NO CYCLE YET", "",
                  "No resident has yet formed an intention inside a conversation. Nothing to trace."]
    else:
        lines += [f"## Verdict: {cycle.verdict}", ""]
        for i, link in enumerate(cycle.links, 1):
            lines.append(f"### {i}. {link.name.capitalize()} — {link.status}")
            lines.append(link.why)
            lines.append("")
            for key, value in link.facts.items():
                if key == "transcript":
                    lines.append("- transcript:")
                    lines += [f"    - {t}" for t in value]
                else:
                    lines.append(f"- {key}: {value}")
            lines.append("")
    lines += ["## Village metrics", ""]
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)
