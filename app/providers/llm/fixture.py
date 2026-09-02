"""A deterministic stand-in for a model.

Lets the whole loop — activation, context building, validation, execution, the
event log, telemetry — be exercised with no API key, no network and no spend.
Its output is plausible but mechanical, and every run it records is flagged
``is_fixture``, so a fixture day can never be mistaken for a live one.

Dispatch is by requested ``output_type`` rather than a method per purpose, so
adding a new structured call (a daily report, say) only means adding a
generator function here and registering it in ``_GENERATORS`` — this file
never needs a new public method.

Packet 6: every wall/rabbit-hole/belief action this generator picks references
a *real* id extracted from the rendered context (the same ``[N]`` bracket
convention Packet 5 established for research passages) — never an invented
one. That is what lets this fixture exercise the full Research Wall / Rabbit
Hole / belief-revision pipeline end to end, the same way live model output
eventually will.
"""

from __future__ import annotations

import hashlib
import random
import re
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from app.domain.characters import CHARACTER_PROFILES, CharacterProfile, Verbosity
from app.domain.enums import (
    BeliefBasisRelation,
    EvidenceStrength,
    FindingClassification,
    MemoryType,
    WallPostType,
)
from app.domain.moves import (
    MOVE_ADMIT_UNCERTAINTY,
    MOVE_ANECDOTE,
    MOVE_ANSWER,
    MOVE_CHALLENGE,
    MOVE_CHANGE_SUBJECT,
    MOVE_CLARIFY,
    MOVE_CONNECT,
    MOVE_EXTEND,
    MOVE_JOKE,
    MOVE_OPEN,
    MOVE_PROPOSE_RESEARCH,
    MOVE_QUESTION,
)
from app.providers.llm.base import LLMResult, LLMSchemaError, LLMUsage
from app.schemas.actions import ActionType, AgentAction, AgentDecision, Reflection
from app.schemas.reflection import QuestionUpdate, ReflectionSynthesis
from app.schemas.report import FounderReportSynthesis
from app.schemas.research import (
    ResearchSynthesis,
    SearchQueryPlan,
    SynthesizedClaim,
    SynthesizedEvidenceLink,
    SynthesizedFinding,
)

T = TypeVar("T", bound=BaseModel)

#: In a conversation the weights change: people mostly talk when spoken to, and
#: a conversation that nobody ever leaves would never end.
_WEIGHTED_CONVERSATION_ACTIONS: tuple[tuple[ActionType, int], ...] = (
    (ActionType.SPEAK, 6),
    (ActionType.DO_NOTHING, 3),
    (ActionType.LEAVE_CONVERSATION, 1),
)

#: Packet 8. A default profile for anything not in the canonical eight (never
#: expected in practice, but keeps this generator from crashing on an
#: unrecognized agent_id rather than silently reading None everywhere).
_DEFAULT_PROFILE = CharacterProfile(
    agent_id="unknown",
    communication_style="plainspoken",
    conversational_tendencies=(), intellectual_tendencies=(),
    humor_style="mild", disagreement_style="direct", curiosity_style="general",
    verbosity=Verbosity.MODERATE,
    notices=(), questions=(),
)

#: Base weights for a reply turn's conversational move — multiplied by the
#: speaking agent's numeric bias fields (app.domain.characters) below, so
#: which move wins varies by who's talking, not just by topic.
_MOVE_BASE_WEIGHTS: dict[str, float] = {
    MOVE_ANSWER: 4.0,
    MOVE_QUESTION: 3.0,
    MOVE_CHALLENGE: 2.0,
    MOVE_CLARIFY: 1.5,
    MOVE_EXTEND: 3.0,
    MOVE_CONNECT: 2.0,
    MOVE_JOKE: 1.5,
    MOVE_ANECDOTE: 2.0,
    MOVE_ADMIT_UNCERTAINTY: 1.0,
    MOVE_PROPOSE_RESEARCH: 1.0,
    MOVE_CHANGE_SUBJECT: 0.7,
}


def _move_weights(profile: CharacterProfile, relationship: dict | None) -> dict[str, float]:
    w = dict(_MOVE_BASE_WEIGHTS)
    w[MOVE_CHALLENGE] *= profile.challenge_bias
    w[MOVE_JOKE] *= profile.humor_bias
    w[MOVE_QUESTION] *= profile.question_bias
    w[MOVE_ANECDOTE] *= profile.anecdote_bias
    w[MOVE_ADMIT_UNCERTAINTY] *= profile.uncertainty_bias
    if relationship is not None:
        # A close, trusted relationship makes disagreement lower-stakes and
        # more comfortable, not less likely — friends push back on friends.
        # A brand-new relationship leans toward lower-risk moves instead.
        # This is the mechanical half of "Optimisto talking with Vince
        # should not feel identical to Optimisto talking with Dex."
        if relationship["trust"] >= 70:
            w[MOVE_CHALLENGE] *= 1.3
            w[MOVE_ANECDOTE] *= 1.2
        elif relationship["familiarity"] < 10:
            w[MOVE_CHALLENGE] *= 0.7
            w[MOVE_QUESTION] *= 1.2
        if relationship["intellectual_affinity"] >= 65:
            w[MOVE_EXTEND] *= 1.3
            w[MOVE_CONNECT] *= 1.3
    return w


_DEX_LABELS = ("SPECULATION", "SPECULATION", "INFERENCE", "INFERENCE", "ESTIMATE", "FACT")


def _dex_label(rng: random.Random) -> str:
    """Dex must distinguish FACT/MARKET DATA/ESTIMATE/INFERENCE/SPECULATION
    (§ Dex's character spec) and never fabricate a market price or
    probability — so this fixture leans heavily toward the labels that carry
    no invented number (SPECULATION/INFERENCE/ESTIMATE) and only rarely
    claims FACT; MARKET DATA never appears here at all, since the fixture
    has no real market feed to cite and citing one anyway would be exactly
    the fabrication the spec forbids."""
    return rng.choice(_DEX_LABELS)


def _reply_templates(move: str, speaker_kw: str, topic: str) -> tuple[str, ...]:
    """Several phrasings per move, so the same move doesn't read identically
    turn to turn — the main defense against synthetic-sounding repetition,
    alongside the exact-duplicate and filler-opener guards in
    app.services.dialogue."""
    if move == MOVE_ANSWER:
        return (
            f"Yeah — the {speaker_kw} part tracks with what I've seen.",
            f"I think so, especially about {speaker_kw}.",
        )
    if move == MOVE_QUESTION:
        return (
            f"What makes you say that about {speaker_kw}?",
            f"Wait, how does {speaker_kw} actually work here?",
        )
    if move == MOVE_CHALLENGE:
        return (
            f"I don't think that follows — what's the evidence for {speaker_kw}?",
            f"Maybe, but there's another explanation for {speaker_kw}.",
            f"I used to think that too, but {speaker_kw} doesn't quite hold up.",
        )
    if move == MOVE_CLARIFY:
        return (
            f"Wait, do you mean {speaker_kw} specifically, or the whole thing?",
            f"Hold on — say more about {speaker_kw}?",
        )
    if move == MOVE_EXTEND:
        return (
            f"Right, and it connects to {topic} too.",
            f"That, plus {topic} — same underlying thing, maybe.",
        )
    if move == MOVE_CONNECT:
        return (
            f"That actually reminds me of {topic}.",
            f"Huh — that's not unlike {topic}.",
        )
    if move == MOVE_JOKE:
        return (
            f"(laughs) Only you'd connect {speaker_kw} to this.",
            f"That's either brilliant or completely made up — {speaker_kw}.",
        )
    if move == MOVE_ANECDOTE:
        return (
            f"Reminds me of something — {topic}, actually.",
            f"Had something like that happen once, around {topic}.",
        )
    if move == MOVE_ADMIT_UNCERTAINTY:
        return (
            f"Honestly, I'm not sure about {speaker_kw}. Could be wrong.",
            f"That sounds plausible, but we're guessing on {speaker_kw}.",
        )
    if move == MOVE_PROPOSE_RESEARCH:
        return (
            f"Someone should actually look into {speaker_kw}.",
            f"I might dig into {speaker_kw} properly later.",
        )
    if move == MOVE_CHANGE_SUBJECT:
        return (f"Different question — what about {topic}?",)
    return (f"{topic}, maybe.",)  # MOVE_OPEN fallback, overridden below

#: Weighted so most activations are quiet. A village where everyone acts every
#: time they are activated is the failure mode, not the goal. Packet 6 actions
#: are only offered when their precondition data actually exists in context
#: (see ``_available_extra_actions``), so these weights are the *ceiling*, not
#: a guarantee any one of them fires this turn.
_BASE_WEIGHTED_ACTIONS: tuple[tuple[ActionType, int], ...] = (
    (ActionType.DO_NOTHING, 4),
    (ActionType.OBSERVE, 4),
    (ActionType.DRINK_COFFEE, 2),
    (ActionType.REST, 2),
    (ActionType.LISTEN_TO_MUSIC, 2),
    (ActionType.WRITE_NOTE, 3),
    (ActionType.ASK_QUESTION, 3),
    (ActionType.SEND_MESSAGE, 2),
    (ActionType.START_CONVERSATION, 3),
    (ActionType.START_RESEARCH, 3),
)

#: Packet 6 actions and the weight each gets *when its precondition is met*.
_EXTRA_WEIGHTED_ACTIONS: dict[ActionType, int] = {
    ActionType.POST_TO_WALL: 3,
    ActionType.READ_WALL_POST: 4,
    ActionType.CREATE_RABBIT_HOLE: 2,
    ActionType.JOIN_RABBIT_HOLE: 3,
    ActionType.CONTRIBUTE_TO_RABBIT_HOLE: 3,
    ActionType.LEAVE_RABBIT_HOLE: 1,
    ActionType.RESOLVE_RABBIT_HOLE: 1,
    ActionType.CHALLENGE_CLAIM: 3,
    ActionType.FORM_BELIEF: 2,
    ActionType.REVISE_BELIEF: 3,
    ActionType.RETIRE_BELIEF: 1,
}

_DIRECTED = {ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE, ActionType.START_CONVERSATION}

#: Packet 7. A reflection (§15) is rare and only follows something actually
#: significant — forming or moving a belief, resolving a shared
#: investigation, or challenging someone's claim — never routine actions.
_REFLECTION_TRIGGERS = {
    ActionType.FORM_BELIEF,
    ActionType.REVISE_BELIEF,
    ActionType.RESOLVE_RABBIT_HOLE,
    ActionType.CHALLENGE_CLAIM,
}
_REFLECTION_PROBABILITY = 0.4

_WALL_POST_TYPES_FOR_FINDING = [WallPostType.FINDING, WallPostType.HYPOTHESIS]
_WALL_POST_TYPES_STANDALONE = [
    WallPostType.QUESTION,
    WallPostType.MYSTERY,
    WallPostType.HYPOTHESIS,
]


class FixtureLLMProvider:
    """Deterministic output seeded by the prompt itself."""

    name = "fixture"
    is_fixture = True

    def __init__(self, seed: str = "village") -> None:
        self._seed = seed

    def _rng(self, *parts: str) -> random.Random:
        digest = hashlib.sha256("|".join((self._seed, *parts)).encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
        output_type: type[T],
        max_tokens: int | None = None,
    ) -> LLMResult:
        # max_tokens (Packet 11) is a live-provider output budget; fixture
        # output size is fixed by the schema and generator, not a token
        # count, so it is accepted for interface parity and otherwise unused.
        del max_tokens
        started = time.perf_counter()
        rng = self._rng(purpose, _stable_seed_text(user))

        generator = _GENERATORS.get(output_type)
        if generator is None:
            raise LLMSchemaError(
                f"[fixture] no generator registered for {output_type.__name__}"
            )
        output = generator(rng, user)

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        return LLMResult(
            output=output,
            usage=LLMUsage(
                input_tokens=_rough_tokens(system) + _rough_tokens(user),
                output_tokens=_rough_tokens(output.model_dump_json()),
                stop_reason="end_turn",
            ),
            provider=self.name,
            model=f"fixture:{model}",
            is_fixture=True,
            latency_ms=latency_ms,
        )


# --------------------------------------------------------------------------
# Context extraction — parsing the same rendered prompt a live model reads,
# so the ids this generator cites are exactly the ids the agent was shown.
# --------------------------------------------------------------------------


class _Context:
    """Every id and fact this generator can legitimately act on, pulled out
    of the rendered prompt text rather than the database directly — a live
    model has no other way in either."""

    def __init__(self, user: str) -> None:
        self.agent_id = _extract(user, "AGENT_ID:") or "unknown_agent"
        self.interests = [i for i in (_extract(user, "INTERESTS:") or "").split("; ") if i]
        self.peers = [
            p for p in (_extract(user, "PRESENT:") or "").split(", ") if p and p != self.agent_id
        ]
        self.locations = [le for le in (_extract(user, "LOCATIONS:") or "").split(", ") if le]
        self.in_conversation = "YOU ARE IN A CONVERSATION" in user

        self.wall_headlines = _extract_wall_posts(user, "RESEARCH WALL HEADLINES")
        self.wall_read = _extract_wall_posts(user, "WALL POSTS YOU HAVE READ IN FULL")
        self.cross_pollination_id = _extract_bracket_id(user, "YOU MAY FIND THIS RELEVANT —")

        self.own_research_ids = _extract_own_research_ids(user)
        self.own_claim_ids = _extract_bracket_ids(user, "YOUR RECENT CLAIMS")
        self.others_claim_ids = _extract_bracket_ids(user, "CLAIMS FROM OTHERS' RESEARCH YOU'VE SEEN")
        self.own_belief_ids = _extract_bracket_ids(user, "YOUR BELIEFS")
        self.challenged_claim_ids = _extract_all(user, r"challenged claim \[(\d+)\]")

        self.open_hole_ids = _extract_bracket_ids(user, "OPEN RABBIT HOLES")
        self.member_hole_ids = _extract_bracket_ids(
            user, "OPEN RABBIT HOLES", only_matching=r"\[(\d+)\] \(you are in this one\)"
        )

        # Packet 8: dialogue signals.
        self.subject = _extract(user, "SUBJECT:")
        self.last_turn = _extract_last_turn(user)
        self.relationships = _extract_relationships(user)
        self.nearby_subject, self.nearby_participants = _extract_nearby_conversation(user)
        self.profile = CHARACTER_PROFILES.get(self.agent_id, _DEFAULT_PROFILE)

        # Packet 9: this agent's own reflections, shown in its context — the
        # concrete mechanism by which a reflection can go on to shape a later
        # decision (see the topic-selection bias in _generate_decision below).
        self.reflections = _extract_labeled_items(
            user, "RECENT REFLECTIONS (your own patterns, noticed across several things):"
        )

        # Persistent unresolved curiosity: this agent's own active questions,
        # shown in its context — target_question_id below is the only way
        # START_RESEARCH ever links to one, exactly as optional live.
        self.open_question_ids = _extract_bracket_ids(user, "OPEN QUESTIONS")


def _generate_decision(rng: random.Random, user: str) -> AgentDecision:
    ctx = _Context(user)

    if ctx.in_conversation:
        table = _WEIGHTED_CONVERSATION_ACTIONS
    else:
        # Packet 10: START_RESEARCH's weight scales by this agent's own
        # research_bias (app.domain.characters) — Dex reaches for research
        # noticeably more often than Optimisto, mechanically, the same way
        # challenge_bias already varies conversational-move weighting.
        table = [
            (a, w * ctx.profile.research_bias) if a is ActionType.START_RESEARCH else (a, w)
            for a, w in _BASE_WEIGHTED_ACTIONS
        ]
        for action_type, weight in _EXTRA_WEIGHTED_ACTIONS.items():
            if _precondition_met(action_type, ctx):
                table.append((action_type, weight))
        if ctx.nearby_subject is not None or ctx.nearby_participants:
            table.append((ActionType.JOIN_CONVERSATION, _join_weight(ctx)))

    population = [a for a, _ in table]
    weights = [w for _, w in table]
    chosen = rng.choices(population, weights=weights, k=1)[0]

    topic = rng.choice(ctx.interests) if ctx.interests else "the room"
    # Packet 9: sometimes let an earlier reflection actually steer what this
    # turn is about — the observable "a reflection later influenced a later
    # action" chain a live model would also be free to draw on, since
    # RECENT REFLECTIONS is rendered in context exactly like any other
    # relevant-experience section.
    if ctx.reflections and rng.random() < 0.4:
        _, reflection_text = rng.choice(ctx.reflections)
        reflection_kw = sorted(_words(reflection_text))
        if reflection_kw:
            topic = reflection_kw[0]
    target = rng.choice(ctx.peers) if ctx.peers else None
    if chosen in _DIRECTED and target is None:
        chosen = ActionType.OBSERVE

    action = _build_action(chosen, rng, ctx, topic, target)
    if action is None:
        # Preconditions turned out unusable (e.g. no id survived extraction);
        # fall back to a harmless default rather than emit something invalid.
        chosen = ActionType.OBSERVE
        action = None

    actions: list[AgentAction] = [action] if action is not None else []

    stays_put = ctx.in_conversation or chosen in (
        ActionType.START_RESEARCH, ActionType.CREATE_RABBIT_HOLE, ActionType.CONTRIBUTE_TO_RABBIT_HOLE,
    )
    location = (
        rng.choice(ctx.locations)
        if ctx.locations and not stays_put and rng.random() < 0.3
        else None
    )
    speaks = (not ctx.in_conversation) and (chosen in _DIRECTED or rng.random() < 0.25)

    return AgentDecision(
        summary=f"[fixture] {ctx.agent_id} chose {chosen.value} regarding {topic}.",
        activity=chosen.value.replace("_", " ").lower(),
        location=location,
        actions=actions,
        public_dialogue=f"[fixture] {topic}, maybe." if speaks else None,
        reflection=_maybe_reflect(rng, chosen, topic),
    )


def _maybe_reflect(rng: random.Random, chosen: ActionType, topic: str) -> Reflection | None:
    if chosen not in _REFLECTION_TRIGGERS or rng.random() >= _REFLECTION_PROBABILITY:
        return None
    return Reflection(
        what_changed=f"[fixture] Something about {topic} shifted a bit for me.",
        what_matters_now=f"[fixture] {topic} still feels worth tracking.",
        what_i_want_to_revisit=(
            f"[fixture] Whether {topic} holds up under more evidence." if rng.random() < 0.5 else None
        ),
    )


def _precondition_met(action_type: ActionType, ctx: _Context) -> bool:
    if action_type is ActionType.POST_TO_WALL:
        return True  # can always post a QUESTION/MYSTERY/HYPOTHESIS standalone
    if action_type is ActionType.READ_WALL_POST:
        return bool(ctx.wall_headlines)
    if action_type is ActionType.CREATE_RABBIT_HOLE:
        return bool(ctx.own_research_ids) or bool(ctx.wall_read)
    if action_type is ActionType.JOIN_RABBIT_HOLE:
        return bool(set(ctx.open_hole_ids) - set(ctx.member_hole_ids))
    if action_type is ActionType.CONTRIBUTE_TO_RABBIT_HOLE:
        return bool(ctx.member_hole_ids)
    if action_type is ActionType.LEAVE_RABBIT_HOLE:
        return bool(ctx.member_hole_ids)
    if action_type is ActionType.RESOLVE_RABBIT_HOLE:
        return bool(ctx.member_hole_ids)
    if action_type is ActionType.CHALLENGE_CLAIM:
        return bool(ctx.others_claim_ids)
    if action_type is ActionType.FORM_BELIEF:
        return bool(ctx.own_research_ids) and not ctx.own_belief_ids
    if action_type is ActionType.REVISE_BELIEF:
        return bool(ctx.own_belief_ids) and (
            bool(ctx.challenged_claim_ids) or bool(ctx.own_research_ids) or bool(ctx.wall_read)
        )
    if action_type is ActionType.RETIRE_BELIEF:
        return bool(ctx.own_belief_ids)
    return False


def _build_action(
    chosen: ActionType, rng: random.Random, ctx: _Context, topic: str, target: str | None
) -> AgentAction | None:
    if chosen is ActionType.WRITE_NOTE:
        return AgentAction(
            type=chosen, content=f"[fixture] A note about {topic}.",
            memory_type=rng.choice(list(MemoryType)),
        )
    if chosen is ActionType.ASK_QUESTION:
        return AgentAction(type=chosen, target_agent_id=target, content=f"[fixture] What do you make of {topic}?")
    if chosen is ActionType.SEND_MESSAGE:
        return AgentAction(type=chosen, target_agent_id=target, content=f"[fixture] Something about {topic} came to mind.")
    if chosen is ActionType.START_CONVERSATION:
        return AgentAction(
            type=chosen, target_agent_id=target, conversational_move=MOVE_OPEN,
            content=_open_line(rng, ctx.profile, topic),
        )
    if chosen is ActionType.START_RESEARCH:
        target_question_id = (
            rng.choice(ctx.open_question_ids) if ctx.open_question_ids and rng.random() < 0.5 else None
        )
        return AgentAction(
            type=chosen, content=f"[fixture] What is the current state of {topic}?",
            target_question_id=target_question_id,
        )
    if chosen is ActionType.SPEAK:
        return _build_speak(rng, ctx, topic)
    if chosen is ActionType.JOIN_CONVERSATION:
        return AgentAction(type=chosen)

    if chosen is ActionType.POST_TO_WALL:
        return _build_post_to_wall(rng, ctx, topic)
    if chosen is ActionType.READ_WALL_POST:
        if not ctx.wall_headlines:
            return None
        post_id, _, _, _ = rng.choice(ctx.wall_headlines)
        return AgentAction(type=chosen, target_wall_post_id=post_id)
    if chosen is ActionType.CREATE_RABBIT_HOLE:
        research_id = rng.choice(ctx.own_research_ids) if ctx.own_research_ids else None
        wall_post_id = rng.choice([p[0] for p in ctx.wall_read]) if ctx.wall_read else None
        return AgentAction(
            type=chosen,
            title=f"[fixture] {topic}",
            content=f"[fixture] Is there really something to {topic}?",
            target_research_id=research_id,
            target_wall_post_id=wall_post_id if research_id is None else None,
        )
    if chosen is ActionType.JOIN_RABBIT_HOLE:
        candidates = list(set(ctx.open_hole_ids) - set(ctx.member_hole_ids))
        if not candidates:
            return None
        return AgentAction(type=chosen, target_rabbit_hole_id=rng.choice(candidates))
    if chosen is ActionType.CONTRIBUTE_TO_RABBIT_HOLE:
        if not ctx.member_hole_ids:
            return None
        # Bringing new research in is the point of contributing to a shared
        # investigation; a bare note is the minority case, not the default.
        research_id = rng.choice(ctx.own_research_ids) if ctx.own_research_ids and rng.random() < 0.85 else None
        return AgentAction(
            type=chosen,
            target_rabbit_hole_id=rng.choice(ctx.member_hole_ids),
            content=f"[fixture] Here's something more on {topic}.",
            target_research_id=research_id,
        )
    if chosen is ActionType.LEAVE_RABBIT_HOLE:
        if not ctx.member_hole_ids:
            return None
        return AgentAction(type=chosen, target_rabbit_hole_id=rng.choice(ctx.member_hole_ids))
    if chosen is ActionType.RESOLVE_RABBIT_HOLE:
        if not ctx.member_hole_ids:
            return None
        return AgentAction(
            type=chosen,
            target_rabbit_hole_id=rng.choice(ctx.member_hole_ids),
            content=f"[fixture] I think this has run its course on {topic}.",
        )
    if chosen is ActionType.CHALLENGE_CLAIM:
        if not ctx.others_claim_ids:
            return None
        return AgentAction(
            type=chosen,
            target_claim_id=rng.choice(ctx.others_claim_ids),
            content=f"[fixture] I'm not convinced this generalizes about {topic}.",
        )
    if chosen is ActionType.FORM_BELIEF:
        if not ctx.own_research_ids:
            return None
        return AgentAction(
            type=chosen,
            content=f"[fixture] {topic.capitalize()} is more real than people assume.",
            target_research_id=rng.choice(ctx.own_research_ids),
        )
    if chosen is ActionType.REVISE_BELIEF:
        if not ctx.own_belief_ids:
            return None
        belief_id = rng.choice(ctx.own_belief_ids)
        if ctx.challenged_claim_ids:
            relation = BeliefBasisRelation.WEAKENS
            return AgentAction(
                type=chosen, target_belief_id=belief_id, belief_relation=relation,
                target_claim_id=int(rng.choice(ctx.challenged_claim_ids)),
                content="[fixture] That challenge is a fair point.",
            )
        if ctx.own_research_ids:
            relation = rng.choice([BeliefBasisRelation.STRENGTHENS, BeliefBasisRelation.WEAKENS])
            return AgentAction(
                type=chosen, target_belief_id=belief_id, belief_relation=relation,
                target_research_id=rng.choice(ctx.own_research_ids),
                content="[fixture] New research shifts this a bit.",
            )
        if ctx.wall_read:
            relation = rng.choice([BeliefBasisRelation.STRENGTHENS, BeliefBasisRelation.WEAKENS])
            return AgentAction(
                type=chosen, target_belief_id=belief_id, belief_relation=relation,
                target_wall_post_id=rng.choice([p[0] for p in ctx.wall_read]),
                content="[fixture] What I read changes this a bit.",
            )
        return None
    if chosen is ActionType.RETIRE_BELIEF:
        if not ctx.own_belief_ids:
            return None
        return AgentAction(
            type=chosen, target_belief_id=rng.choice(ctx.own_belief_ids),
            content="[fixture] I don't hold this one anymore.",
        )
    return None


def _open_line(rng: random.Random, profile: CharacterProfile, topic: str) -> str:
    templates = (
        f"Hey — been thinking about {topic}.",
        f"Can I ask you about {topic}?",
        f"Something about {topic} came to mind.",
        f"Got a minute? {topic.capitalize()}'s been on my mind.",
        f"Random question, but — {topic}?",
        f"You around? Wanted to talk through {topic}.",
    )
    return f"[fixture] {rng.choice(templates)}"


def _join_weight(ctx: _Context) -> float:
    """How much this agent wants to join the conversation happening nearby
    — real overlap with its own interests, or a strong relationship with
    someone already in it (rendered relationship lines aren't available for
    a non-participant, so this leans on subject-keyword overlap alone,
    matching find_joiner's own primary signal)."""
    if not ctx.nearby_subject:
        return 0.5
    interest_words: set[str] = set()
    for i in ctx.interests:
        interest_words |= _words(i)
    overlap = interest_words & _words(ctx.nearby_subject)
    return 0.5 + 2.0 * len(overlap)


def _build_speak(rng: random.Random, ctx: _Context, topic: str) -> AgentAction:
    """A reply that actually engages the last thing said — never an
    independent monologue that merely shares a topic (§ "Direct Response").
    """
    if ctx.last_turn is None:
        # First to speak in this conversation (e.g. the opener already
        # happened via START_CONVERSATION and nobody else has spoken since,
        # or a solo/degenerate case) — open rather than "reply to nothing".
        return AgentAction(
            type=ActionType.SPEAK, conversational_move=MOVE_OPEN,
            content=_open_line(rng, ctx.profile, topic),
        )

    last_speaker, last_content = ctx.last_turn
    speaker_kw_set = _words(last_content)
    if speaker_kw_set and rng.random() < 0.7:
        # Prefer the longest surviving word(s): a real topic noun
        # ("consciousness", "hospitality") tends to run longer than the
        # connector words that leak through a coarse length+stopword filter
        # ("plus", "hold", "can") — a cheap second line of defense on top of
        # the stopword list itself. The remaining 30% of the time falls back
        # to the speaker's own topic instead: every reply template's own
        # vocabulary becomes the *next* turn's extraction source once a
        # conversation runs several turns, so leaning on this agent's own
        # interest sometimes keeps that from cascading into nonsense over a
        # long exchange (found by inspecting real multi-day runs).
        longest_len = max(len(w) for w in speaker_kw_set)
        speaker_kw = rng.choice(sorted(w for w in speaker_kw_set if len(w) == longest_len))
    else:
        speaker_kw = topic

    relationship = ctx.relationships.get(last_speaker)
    weights = _move_weights(ctx.profile, relationship)
    moves = list(weights.keys())
    move = rng.choices(moves, weights=[weights[m] for m in moves], k=1)[0]

    line = rng.choice(_reply_templates(move, speaker_kw, topic))
    if ctx.agent_id == "agent_dex" and move in (MOVE_CHALLENGE, MOVE_QUESTION, MOVE_ANSWER):
        line = f"[{_dex_label(rng)}] {line}"
    content = f"[fixture] {line}"

    action_kwargs: dict = {}
    if move == MOVE_CHANGE_SUBJECT:
        action_kwargs["new_subject"] = topic[:200]
    # Occasionally ground the turn in something real — citing a real id, the
    # same discipline every other Packet 6/7 action already follows, never
    # an invented one. Only offered when the fixture actually has one.
    if move in (MOVE_PROPOSE_RESEARCH, MOVE_EXTEND) and ctx.own_research_ids and rng.random() < 0.4:
        action_kwargs["target_research_id"] = rng.choice(ctx.own_research_ids)
    elif move in (MOVE_CONNECT, MOVE_EXTEND) and ctx.wall_read and rng.random() < 0.3:
        action_kwargs["target_wall_post_id"] = rng.choice(ctx.wall_read)[0]
    elif move == MOVE_CONNECT and ctx.member_hole_ids and rng.random() < 0.3:
        action_kwargs["target_rabbit_hole_id"] = rng.choice(ctx.member_hole_ids)

    return AgentAction(
        type=ActionType.SPEAK, conversational_move=move, content=content, **action_kwargs
    )


def _build_post_to_wall(rng: random.Random, ctx: _Context, topic: str) -> AgentAction:
    # A CONNECTION needs something read to connect to; otherwise post freely.
    # A repeat connection to the same post is still possible here — validation
    # rejects it (§ anti-repetition), same as any other precondition this
    # generator can't fully verify from text alone.
    if ctx.wall_read and rng.random() < 0.5:
        post_id, _, _, _ = rng.choice(ctx.wall_read)
        return AgentAction(
            type=ActionType.POST_TO_WALL,
            wall_post_type=WallPostType.CONNECTION,
            content=f"[fixture] This connects to what I've been thinking about {topic}.",
            target_wall_post_id=post_id,
        )
    if ctx.own_research_ids and rng.random() < 0.6:
        return AgentAction(
            type=ActionType.POST_TO_WALL,
            wall_post_type=rng.choice(_WALL_POST_TYPES_FOR_FINDING),
            content=f"[fixture] Something worth sharing about {topic}.",
            target_research_id=rng.choice(ctx.own_research_ids),
        )
    return AgentAction(
        type=ActionType.POST_TO_WALL,
        wall_post_type=rng.choice(_WALL_POST_TYPES_STANDALONE),
        content=f"[fixture] I keep wondering about {topic}.",
    )


def _generate_research_synthesis(rng: random.Random, user: str) -> ResearchSynthesis:
    """Fabricate a plausible-but-labelled interpretation of the given passages.

    Only ever called by the research service, and only once real passages have
    already been retrieved and persisted — this generator reads the numbered
    PASSAGES block out of the prompt so its claims cite real passage indices,
    the same way a live model is asked to.
    """
    passage_indices = [
        int(n) for n in _extract_all(user, r"^\[(\d+)\]") if n.isdigit()
    ] or [1]
    question = _extract(user, "QUESTION:") or "the question"

    strength = rng.choice(list(EvidenceStrength))
    n_findings = rng.randint(1, 2)
    findings = []
    for i in range(n_findings):
        cited = rng.sample(passage_indices, k=min(len(passage_indices), rng.randint(1, 2)))
        findings.append(
            SynthesizedFinding(
                text=f"[fixture] A finding about {question} (finding {i + 1}).",
                classification=rng.choice(
                    [
                        FindingClassification.SOURCE_CLAIM,
                        FindingClassification.RESEARCH_FINDING,
                        FindingClassification.AGENT_INFERENCE,
                    ]
                ),
                claims=[
                    SynthesizedClaim(
                        text=f"[fixture] A claim drawn from the fixture passages ({i + 1}).",
                        classification=FindingClassification.SOURCE_CLAIM,
                        confidence=float(rng.randint(40, 90)),
                        evidence=[
                            SynthesizedEvidenceLink(passage_index=idx) for idx in cited
                        ],
                    )
                ],
            )
        )

    return ResearchSynthesis(
        interpretation=f"[fixture] Interpretation of the retrieved evidence on {question}.",
        evidence_strength=strength,
        confidence=float(rng.randint(30, 85)),
        findings=findings,
        open_questions=[f"[fixture] What else bears on {question}?"],
        follow_up_questions=[f"[fixture] A natural follow-up to {question}."],
    )


def _generate_reflection_synthesis(rng: random.Random, user: str) -> ReflectionSynthesis:
    """Ground one reflection in 1-2 real, distinct kinds of the agent's own
    prior experience — never inventing an id, and never a bare restatement
    of a single item (the fixture mirrors the "pattern across two or more
    things" instruction the same way a live model is asked to follow it).
    """
    pools = {
        "memory": _extract_labeled_items(user, "RECENT MEMORIES:"),
        "research": _extract_labeled_items(user, "RECENT RESEARCH:"),
        "belief": _extract_labeled_items(user, "YOUR BELIEFS:"),
        "conversation": _extract_labeled_items(user, "RECENT CONVERSATIONS:"),
        "rabbit_hole": _extract_labeled_items(user, "RABBIT HOLES YOU ARE PART OF:"),
        "wall_post": _extract_labeled_items(user, "YOUR OWN WALL ACTIVITY:"),
        "reflection": _extract_labeled_items(user, "YOUR EARLIER REFLECTIONS:"),
    }
    nonempty_kinds = [k for k, v in pools.items() if v]
    picked_kinds = rng.sample(nonempty_kinds, k=min(2, len(nonempty_kinds))) if nonempty_kinds else []

    source_memory_ids: list[int] = []
    source_research_ids: list[str] = []
    source_belief_ids: list[int] = []
    source_conversation_ids: list[int] = []
    source_rabbit_hole_ids: list[int] = []
    source_wall_post_ids: list[int] = []
    source_reflection_ids: list[int] = []
    topic_text = ""
    for kind in picked_kinds:
        item_id, item_text = rng.choice(pools[kind])
        topic_text = topic_text or item_text
        if kind == "memory":
            source_memory_ids.append(int(item_id))
        elif kind == "research":
            source_research_ids.append(item_id)
        elif kind == "belief":
            source_belief_ids.append(int(item_id))
        elif kind == "conversation":
            source_conversation_ids.append(int(item_id))
        elif kind == "rabbit_hole":
            source_rabbit_hole_ids.append(int(item_id))
        elif kind == "wall_post":
            source_wall_post_ids.append(int(item_id))
        elif kind == "reflection":
            source_reflection_ids.append(int(item_id))

    kw = sorted(_words(topic_text))
    topic_word = kw[0] if kw else "something"
    supersedes = source_reflection_ids[0] if source_reflection_ids and rng.random() < 0.3 else None

    # Persistent unresolved curiosity: independent of the "pattern across two
    # things" logic above — a reflection may separately judge (at most) one
    # of the agent's own existing open questions, exactly as optional as
    # open_question/suggested_follow_up already are.
    question_pool = _extract_labeled_items(user, "YOUR OPEN QUESTIONS")
    question_updates: list[QuestionUpdate] = []
    if question_pool and rng.random() < 0.5:
        q_id, q_text = rng.choice(question_pool)
        if rng.random() < 0.25:
            question_updates.append(
                QuestionUpdate(
                    question_id=int(q_id),
                    status="RESOLVED",
                    reformulated_question=f"[fixture] A sharper version of: {q_text.strip()[:100]}",
                )
            )
        else:
            question_updates.append(
                QuestionUpdate(
                    question_id=int(q_id),
                    status=rng.choice(["OPEN", "RESEARCHING", "RESOLVED", "ABANDONED"]),
                    note="[fixture] judged during this reflection." if rng.random() < 0.5 else None,
                )
            )

    return ReflectionSynthesis(
        topic=f"[fixture] A pattern around {topic_word}",
        summary=(
            f"[fixture] A few recent things ({', '.join(picked_kinds) or 'nothing much'}) "
            f"seem to point toward the same underlying question about {topic_word}."
        ),
        confidence=float(rng.randint(40, 85)),
        open_question=(
            f"[fixture] Is {topic_word} actually as settled as it looks?" if rng.random() < 0.6 else None
        ),
        suggested_follow_up=(
            f"[fixture] Worth researching {topic_word} more directly." if rng.random() < 0.4 else None
        ),
        supersedes_reflection_id=supersedes,
        source_memory_ids=source_memory_ids,
        source_research_ids=source_research_ids,
        source_belief_ids=source_belief_ids,
        source_conversation_ids=source_conversation_ids,
        source_rabbit_hole_ids=source_rabbit_hole_ids,
        source_wall_post_ids=source_wall_post_ids,
        source_reflection_ids=source_reflection_ids,
        question_updates=question_updates,
    )


def _generate_founder_report_synthesis(rng: random.Random, user: str) -> FounderReportSynthesis:
    """Template prose directly from the already-ranked, already-bounded facts
    app.services.daily_synthesis.gather_facts rendered — this generator never
    re-ranks or re-selects; the ordering it templates from is already the
    real significance ordering, the same discipline a live model is asked to
    respect ("treat the ranking ... as authoritative")."""
    findings = _extract_labeled_items(user, "RESEARCH FINDINGS:")
    failed = _extract_labeled_items(user, "FAILED OR ABANDONED RESEARCH:")
    wall = _extract_labeled_items(user, "WALL ACTIVITY:")
    cross = _extract_labeled_items(user, "CROSS-POLLINATION:")
    holes = _extract_labeled_items(user, "RABBIT HOLES:")
    belief_changes = _extract_labeled_items(user, "BELIEF CHANGES:")
    memories = _extract_labeled_items(user, "MEMORIES:")
    conversations = _extract_labeled_items(user, "CONVERSATIONS:")
    reflections = _extract_labeled_items(user, "REFLECTIONS:")
    questions = [
        line.strip().lstrip("-").strip() for line in _extract_section(user, "UNRESOLVED QUESTIONS:")
    ]
    source_quality = _extract(
        user, "SOURCE QUALITY (already computed, restate — do not recompute):"
    ) or "No research today."

    had_activity = bool(findings or wall or holes or belief_changes or conversations)

    def _texts(items: list[tuple[str, str]], k: int = 4) -> list[str]:
        return [f"[fixture] {text}" for _, text in items[:k]]

    standout = next(iter(findings or holes or belief_changes or wall), None)

    return FounderReportSynthesis(
        what_mattered_today=(
            f"[fixture] {len(findings)} finding(s), {len(wall)} wall post(s), "
            f"{len(holes)} rabbit hole update(s), {len(belief_changes)} belief change(s) today."
            if had_activity
            else "[fixture] Nothing significant happened today."
        ),
        top_discoveries=_texts(findings),
        unexpected_connections=_texts(cross),
        active_rabbit_holes=_texts(holes),
        beliefs_that_changed=_texts(belief_changes),
        character_development=_texts(memories + reflections),
        disagreements_and_uncertainties=_texts(belief_changes[:3] + failed[:2]),
        questions_the_village_wants_to_follow=[f"[fixture] {q}" for q in questions[:5] if q],
        source_quality=f"[fixture] {source_quality}",
        one_thing_worth_your_attention=(
            f"[fixture] {standout[1]}" if standout else "[fixture] Nothing stood out today."
        ),
    )


def _generate_search_query_plan(rng: random.Random, user: str) -> SearchQueryPlan:
    """Deterministically split one research question into a small set of
    concrete queries (Packet 10, Part J) — never the raw question sent
    wholesale, and never a fabricated topic unrelated to it."""
    question = _extract(user, "RESEARCH QUESTION:") or "the topic"
    max_queries = _extract(user, "MAX_QUERIES:")
    cap = int(max_queries) if max_queries and max_queries.isdigit() else 3

    kw = sorted(_words(question))
    queries = [f"[fixture] {question}"]
    if cap > 1 and kw:
        queries.append(f"[fixture] {' '.join(kw[:4])}")
    if cap > 2 and len(kw) > 2:
        queries.append(f"[fixture] {' '.join(kw[-3:])} overview")
    return SearchQueryPlan(queries=queries[:cap])


_GENERATORS: dict[type, Callable[[random.Random, str], BaseModel]] = {
    AgentDecision: _generate_decision,
    ResearchSynthesis: _generate_research_synthesis,
    ReflectionSynthesis: _generate_reflection_synthesis,
    FounderReportSynthesis: _generate_founder_report_synthesis,
    SearchQueryPlan: _generate_search_query_plan,
}


#: Prompt lines that carry real wall-clock time (see
#: app.services.research._render_synthesis_prompt). A research passage's
#: ``retrieved:``/``published:`` line is genuinely the moment the fixture
#: research provider ran, not fabricated — but hashing it into this
#: provider's own seed would make a fixture LLM's output depend on what time
#: it happened to be called, defeating the purpose of a fixture. Stripped
#: only for seeding; the real lines are still what the model "sees".
_VOLATILE_LINE_PREFIXES = ("    retrieved:", "    published:")

#: research_id / correlation_id are generated by app.domain.ids with
#: uuid.uuid4() — genuinely random, and (unlike the timestamp lines above)
#: woven directly into ordinary content the agent needs to see and cite
#: ("YOUR RESEARCH SESSIONS: res_<uuid> (COMPLETED): ..."). Left as-is, two
#: otherwise-identical simulation runs would seed this provider's RNG
#: differently the moment any research completed, and every decision after
#: that point would silently diverge — real behaviour observed and root-caused
#: while building the Packet 6 cross-pollination smoke test. Normalized to a
#: fixed placeholder for seeding only; `_generate_decision`'s extraction still
#: reads the real, distinct ids from the unstripped text.
_VOLATILE_ID_PATTERN = re.compile(r"\b(res|corr)_[0-9a-f]+\b")


def _stable_seed_text(user: str) -> str:
    stable_lines = (
        line for line in user.splitlines() if not line.startswith(_VOLATILE_LINE_PREFIXES)
    )
    return _VOLATILE_ID_PATTERN.sub(r"\1_STABLE", "\n".join(stable_lines))


def _extract(text: str, label: str) -> str | None:
    """Pull one labelled line out of the rendered context."""
    for line in text.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    return None


def _extract_all(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text, flags=re.MULTILINE)


def _extract_section(text: str, header_prefix: str) -> list[str]:
    """Every indented line following the first line starting with the given
    prefix, up to the next non-indented line — the shape every context_builder
    list section takes."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(header_prefix):
            start = i + 1
            break
    if start is None:
        return []
    section = []
    for line in lines[start:]:
        if line.startswith(" ") or line.startswith("\t"):
            section.append(line)
        else:
            break
    return section


def _extract_bracket_ids(
    text: str, header_prefix: str, *, only_matching: str | None = None
) -> list[int]:
    section = _extract_section(text, header_prefix)
    pattern = re.compile(only_matching or r"\[(\d+)\]")
    ids: list[int] = []
    for line in section:
        m = pattern.search(line)
        if m:
            ids.append(int(m.group(1)))
    return ids


def _extract_bracket_id(text: str, marker: str) -> int | None:
    for line in text.splitlines():
        if marker in line:
            m = re.search(r"\[(\d+)\]", line)
            if m:
                return int(m.group(1))
    return None


def _extract_labeled_items(text: str, header_prefix: str) -> list[tuple[str, str]]:
    """Every ``[id] rest of the line`` item in a section — generic across
    every shape this file's sections render (a bare int id, a ``res_...``
    string id, with or without a further ``[TAG]``/``(...)`` after it).
    Packet 9's reflection and daily-report generators use this instead of
    ``_extract_bracket_ids`` because several of their sections carry string
    ids (``research_id``), not just integers."""
    section = _extract_section(text, header_prefix)
    pattern = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$")
    items: list[tuple[str, str]] = []
    for line in section:
        m = pattern.match(line)
        if m:
            items.append((m.group(1), m.group(2)))
    return items


def _extract_wall_posts(text: str, header_prefix: str) -> list[tuple[int, str, str, str]]:
    """Returns ``(id, post_type, author, content)`` for each post in a section."""
    section = _extract_section(text, header_prefix)
    pattern = re.compile(r"\[(\d+)\] \[(\w+)\] (\S+):\s*(.*)$")
    posts = []
    for line in section:
        m = pattern.search(line.strip())
        if m:
            posts.append((int(m.group(1)), m.group(2), m.group(3).rstrip(":"), m.group(4)))
    return posts


#: Small, local, deliberately not shared with app.services.wall.keywords:
#: providers sit below services in this codebase's layering, so this file
#: never imports a service — a few lines of duplication here is cheaper than
#: inverting that dependency.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "and", "or", "for", "with", "about", "this", "that", "it", "as", "at",
    "be", "by", "from", "has", "have", "not", "what", "how", "do", "does",
    "you", "your", "i", "we", "they", "he", "she", "maybe", "actually",
    "something", "someone", "somewhere", "thing", "things", "came", "mind",
    "yeah", "right", "well", "just", "really", "still", "even", "much",
    # Every fixture-generated utterance is prefixed "[fixture] " (the marker
    # that keeps fixture output from ever being mistaken for a live model's,
    # same as everywhere else in this codebase) — without this, "fixture"
    # itself would keep winning as an "extracted keyword" from any content.
    "fixture",
    # Connective/filler words that show up across this file's own templates
    # ("Hey — been thinking about...", "What is the current state of...")
    # and would otherwise get extracted as a "keyword" from one template and
    # threaded into a *different* template, producing nonsense like "but
    # reminds doesn't quite hold up" or "what's the evidence for plus" —
    # found by inspecting real multi-day runs. Every reply template in this
    # file was re-read word by word to build this list, rather than adding
    # entries only as each awkward case turned up one at a time.
    "been", "hey", "thinking", "ask", "reminds", "state", "current",
    "wondering", "keep", "worth", "sharing", "here", "there", "regarding",
    "part", "tracks", "seen", "makes", "say", "wait", "work", "follows",
    "evidence", "another", "explanation", "used", "quite", "hold", "mean",
    "specifically", "whole", "connects", "plus", "underlying", "same",
    "unlike", "laughs", "only", "connect", "either", "brilliant",
    "completely", "made", "happen", "once", "around", "honestly", "sure",
    "could", "wrong", "sounds", "plausible", "guessing", "look", "into",
    "might", "dig", "properly", "later", "different", "question", "held",
    "shifts", "bit", "changes", "fair", "point", "held", "run", "course",
    "convinced", "generalizes", "assume", "real", "people", "worthwhile",
    "can", "could've", "would've",
    # Contractions: _words() keeps the apostrophe (see its regex), so these
    # need listing whole rather than relying on the length/stopword filter
    # to catch their stem.
    "don't", "can't", "won't", "you'd", "i'd", "that's", "there's",
    "what's", "it's", "you're", "i'm", "isn't", "doesn't", "didn't",
    "especially", "probably", "definitely", "certainly", "obviously",
    "random", "minute", "wanted", "talk", "through", "around",
}


def _words(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {w for w in tokens if len(w) > 2 and w not in _STOPWORDS}


def _extract_last_turn(text: str) -> tuple[str, str] | None:
    """The most recent line of ``WHAT HAS BEEN SAID:`` — ``(speaker, content)``
    — so a reply can be built to actually respond to it, not just share a
    topic with it."""
    section = _extract_section(text, "WHAT HAS BEEN SAID:")
    if not section:
        return None
    m = re.match(r"\s*\d+\.\s+(\S+):\s*(.*)$", section[-1])
    if not m:
        return None
    return m.group(1).rstrip(":"), m.group(2)


def _extract_relationships(text: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    pattern = re.compile(
        r"YOUR RELATIONSHIP WITH (\S+): trust=(-?\d+) familiarity=(-?\d+) "
        r"intellectual_affinity=(-?\d+) conversations_together=(\d+)"
    )
    for line in text.splitlines():
        m = pattern.search(line)
        if m:
            out[m.group(1)] = {
                "trust": float(m.group(2)),
                "familiarity": float(m.group(3)),
                "intellectual_affinity": float(m.group(4)),
                "conversations_together": float(m.group(5)),
            }
    return out


def _extract_nearby_conversation(text: str) -> tuple[str | None, list[str]]:
    m = re.search(
        r"A CONVERSATION IS HAPPENING NEARBY \([A-Z_]+\) between ([^\n]+?)"
        r"(?: about \"([^\"]*)\")?\.",
        text,
    )
    if not m:
        return None, []
    participants = [p.strip() for p in m.group(1).split(",") if p.strip()]
    return m.group(2), participants


def _extract_own_research_ids(text: str) -> list[str]:
    section = _extract_section(text, "YOUR RESEARCH SESSIONS")
    ids = []
    for line in section:
        m = re.match(r"\s*(res_\S+)\s+\((\w+)\):", line)
        if m and m.group(2) == "COMPLETED":
            ids.append(m.group(1))
    return ids


def _rough_tokens(text: str) -> int:
    """A character-count stand-in.

    Real token counts come from the live provider's usage block; this exists so
    fixture rows are not all zero, and is never used for billing.
    """
    return max(1, len(text) // 4)
