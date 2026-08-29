"""A deterministic stand-in for a model.

Lets the whole loop — activation, context building, validation, execution, the
event log, telemetry — be exercised with no API key, no network and no spend.
Its output is plausible but mechanical, and every run it records is flagged
``is_fixture``, so a fixture day can never be mistaken for a live one.

Dispatch is by requested ``output_type`` rather than a method per purpose, so
adding a new structured call (a daily report, say) only means adding a
generator function here and registering it in ``_GENERATORS`` — this file
never needs a new public method.
"""

from __future__ import annotations

import hashlib
import random
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from app.providers.llm.base import LLMResult, LLMSchemaError, LLMUsage
from app.schemas.actions import ActionType, AgentAction, AgentDecision
from app.schemas.research import (
    ResearchSynthesis,
    SynthesizedClaim,
    SynthesizedEvidenceLink,
    SynthesizedFinding,
)
from app.domain.enums import EvidenceStrength, FindingClassification

T = TypeVar("T", bound=BaseModel)

#: In a conversation the weights change: people mostly talk when spoken to, and
#: a conversation that nobody ever leaves would never end.
_WEIGHTED_CONVERSATION_ACTIONS: tuple[tuple[ActionType, int], ...] = (
    (ActionType.SPEAK, 6),
    (ActionType.DO_NOTHING, 3),
    (ActionType.LEAVE_CONVERSATION, 1),
)

#: Weighted so most activations are quiet. A village where everyone acts every
#: time they are activated is the failure mode, not the goal.
_WEIGHTED_ACTIONS: tuple[tuple[ActionType, int], ...] = (
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


def _generate_decision(rng: random.Random, user: str) -> AgentDecision:
    agent_id = _extract(user, "AGENT_ID:") or "unknown_agent"
    interests = [i for i in (_extract(user, "INTERESTS:") or "").split("; ") if i]
    peers = [p for p in (_extract(user, "PRESENT:") or "").split(", ") if p and p != agent_id]
    locations = [le for le in (_extract(user, "LOCATIONS:") or "").split(", ") if le]

    in_conversation = "YOU ARE IN A CONVERSATION" in user
    table = _WEIGHTED_CONVERSATION_ACTIONS if in_conversation else _WEIGHTED_ACTIONS
    population = [a for a, _ in table]
    weights = [w for _, w in table]
    chosen = rng.choices(population, weights=weights, k=1)[0]

    topic = rng.choice(interests) if interests else "the room"
    target = rng.choice(peers) if peers else None
    directed = {
        ActionType.ASK_QUESTION,
        ActionType.SEND_MESSAGE,
        ActionType.START_CONVERSATION,
    }
    if chosen in directed and target is None:
        chosen = ActionType.OBSERVE

    content = {
        ActionType.WRITE_NOTE: f"[fixture] A note about {topic}.",
        ActionType.ASK_QUESTION: f"[fixture] What do you make of {topic}?",
        ActionType.SEND_MESSAGE: f"[fixture] Something about {topic} came to mind.",
        ActionType.SPEAK: f"[fixture] Something occurs to me about {topic}.",
        ActionType.START_CONVERSATION: f"[fixture] Can I ask you about {topic}?",
        ActionType.START_RESEARCH: f"[fixture] What is the current state of {topic}?",
    }.get(chosen)

    actions: list[AgentAction] = []
    if chosen is not ActionType.DO_NOTHING:
        actions.append(
            AgentAction(
                type=chosen,
                target_agent_id=target if chosen in directed else None,
                content=content,
            )
        )

    # Moving rooms mid-conversation (or mid-research) would be strange.
    stays_put = in_conversation or chosen is ActionType.START_RESEARCH
    location = (
        rng.choice(locations) if locations and not stays_put and rng.random() < 0.3 else None
    )
    speaks = (not in_conversation) and (chosen in directed or rng.random() < 0.25)

    return AgentDecision(
        summary=f"[fixture] {agent_id} chose {chosen.value} regarding {topic}.",
        activity=chosen.value.replace("_", " ").lower(),
        location=location,
        actions=actions,
        public_dialogue=f"[fixture] {topic}, maybe." if speaks else None,
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


def _stable_seed_text(user: str) -> str:
    return "\n".join(
        line for line in user.splitlines() if not line.startswith(_VOLATILE_LINE_PREFIXES)
    )


def _extract(text: str, label: str) -> str | None:
    """Pull one labelled line out of the rendered context."""
    for line in text.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    return None


def _extract_all(text: str, pattern: str) -> list[str]:
    import re

    return re.findall(pattern, text, flags=re.MULTILINE)


def _rough_tokens(text: str) -> int:
    """A character-count stand-in.

    Real token counts come from the live provider's usage block; this exists so
    fixture rows are not all zero, and is never used for billing.
    """
    return max(1, len(text) // 4)
