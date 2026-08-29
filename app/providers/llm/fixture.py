"""A deterministic stand-in for a model.

Lets the whole loop — activation, context building, validation, execution, the
event log, telemetry — be exercised with no API key, no network and no spend.
Its output is plausible but mechanical, and every run it records is flagged
``is_fixture``, so a fixture day can never be mistaken for a live one.
"""

from __future__ import annotations

import hashlib
import random
import time

from app.providers.llm.base import LLMResult, LLMUsage
from app.schemas.actions import ActionType, AgentAction, AgentDecision

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
)


class FixtureLLMProvider:
    """Deterministic decisions seeded by the prompt itself."""

    name = "fixture"
    is_fixture = True

    def __init__(self, seed: str = "village") -> None:
        self._seed = seed

    def _rng(self, *parts: str) -> random.Random:
        digest = hashlib.sha256("|".join((self._seed, *parts)).encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def decide(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
    ) -> LLMResult:
        started = time.perf_counter()
        rng = self._rng(purpose, user)

        agent_id = _extract(user, "AGENT_ID:") or "unknown_agent"
        interests = [i for i in (_extract(user, "INTERESTS:") or "").split("; ") if i]
        peers = [p for p in (_extract(user, "PRESENT:") or "").split(", ") if p and p != agent_id]
        locations = [le for le in (_extract(user, "LOCATIONS:") or "").split(", ") if le]

        population = [a for a, _ in _WEIGHTED_ACTIONS]
        weights = [w for _, w in _WEIGHTED_ACTIONS]
        chosen = rng.choices(population, weights=weights, k=1)[0]

        topic = rng.choice(interests) if interests else "the room"
        target = rng.choice(peers) if peers else None
        if chosen in (ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE) and target is None:
            chosen = ActionType.OBSERVE

        content = {
            ActionType.WRITE_NOTE: f"[fixture] A note about {topic}.",
            ActionType.ASK_QUESTION: f"[fixture] What do you make of {topic}?",
            ActionType.SEND_MESSAGE: f"[fixture] Something about {topic} came to mind.",
        }.get(chosen)

        actions: list[AgentAction] = []
        if chosen is not ActionType.DO_NOTHING:
            actions.append(
                AgentAction(
                    type=chosen,
                    target_agent_id=target if chosen in (ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE) else None,
                    content=content,
                )
            )

        location = rng.choice(locations) if locations and rng.random() < 0.3 else None
        speaks = chosen in (ActionType.ASK_QUESTION, ActionType.SEND_MESSAGE) or rng.random() < 0.25

        decision = AgentDecision(
            summary=f"[fixture] {agent_id} chose {chosen.value} regarding {topic}.",
            activity=chosen.value.replace("_", " ").lower(),
            location=location,
            actions=actions,
            public_dialogue=f"[fixture] {topic}, maybe." if speaks else None,
        )

        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        return LLMResult(
            decision=decision,
            usage=LLMUsage(
                input_tokens=_rough_tokens(system) + _rough_tokens(user),
                output_tokens=_rough_tokens(decision.model_dump_json()),
                stop_reason="end_turn",
            ),
            provider=self.name,
            model=f"fixture:{model}",
            is_fixture=True,
            latency_ms=latency_ms,
        )


def _extract(text: str, label: str) -> str | None:
    """Pull one labelled line out of the rendered context."""
    for line in text.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    return None


def _rough_tokens(text: str) -> int:
    """A character-count stand-in.

    Real token counts come from the live provider's usage block; this exists so
    fixture rows are not all zero, and is never used for billing.
    """
    return max(1, len(text) // 4)
