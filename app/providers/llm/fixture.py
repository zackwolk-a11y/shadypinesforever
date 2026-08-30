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

from app.domain.enums import (
    BeliefBasisRelation,
    EvidenceStrength,
    FindingClassification,
    MemoryType,
    WallPostType,
)
from app.providers.llm.base import LLMResult, LLMSchemaError, LLMUsage
from app.schemas.actions import ActionType, AgentAction, AgentDecision, Reflection
from app.schemas.research import (
    ResearchSynthesis,
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
    ) -> LLMResult:
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


def _generate_decision(rng: random.Random, user: str) -> AgentDecision:
    ctx = _Context(user)

    if ctx.in_conversation:
        table = _WEIGHTED_CONVERSATION_ACTIONS
    else:
        table = list(_BASE_WEIGHTED_ACTIONS)
        for action_type, weight in _EXTRA_WEIGHTED_ACTIONS.items():
            if _precondition_met(action_type, ctx):
                table.append((action_type, weight))

    population = [a for a, _ in table]
    weights = [w for _, w in table]
    chosen = rng.choices(population, weights=weights, k=1)[0]

    topic = rng.choice(ctx.interests) if ctx.interests else "the room"
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
        return AgentAction(type=chosen, target_agent_id=target, content=f"[fixture] Can I ask you about {topic}?")
    if chosen is ActionType.START_RESEARCH:
        return AgentAction(type=chosen, content=f"[fixture] What is the current state of {topic}?")

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


_GENERATORS: dict[type, Callable[[random.Random, str], BaseModel]] = {
    AgentDecision: _generate_decision,
    ResearchSynthesis: _generate_research_synthesis,
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
