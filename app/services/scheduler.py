"""The activation scheduler.

Decides *who gets an opportunity to think*, never what they think. That
distinction is what keeps the emergence real: the score is mechanism, the
decision is the agent's.

It also keeps the Village from becoming eight parallel bots — a normal event
activates one agent, not all eight, so a simulated day costs a handful of calls
rather than dozens.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.agents import Agent
from app.db.models.conversations import Message
from app.db.models.events import Event
from app.db.models.rabbit_holes import RabbitHoleMember
from app.db.models.rabbit_holes import RabbitHole as RabbitHoleModel
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, RabbitHoleStatus

#: How likely each period is to produce activity at all (§ daily rhythm).
PERIOD_WEIGHT: dict[str, float] = {
    "MORNING": 3.0,
    "RESEARCH": 2.0,
    "AFTERNOON": 3.0,
    "EVENING": 2.5,
    "NIGHT": 0.5,
}

UNREAD_MESSAGE_POINTS = 3.0
RECENT_ACTIVATION_PENALTY = 2.5
CURIOSITY_MAX = 2.0
#: Packet 7: a member of a dormant rabbit hole gets a small, deterministic
#: pull back toward it — "agents returning to a dormant rabbit hole" (§13)
#: should happen more than by pure chance, without ever forcing the choice;
#: it only raises how likely this agent is to be activated at all, same as
#: an unread message would.
DORMANT_RABBIT_HOLE_PULL = 1.5

#: Events that count as an agent having been activated today.
ACTIVATION_EVENTS = (EventType.AGENT_ACTED, EventType.INVALID_AGENT_DECISION)


@dataclass(frozen=True)
class ActivationCandidate:
    """One agent's case for being allowed to act right now."""

    agent_id: str
    score: float
    components: dict[str, float]
    activations_today: int

    @property
    def is_eligible(self) -> bool:
        return self.score > 0


def score_agents(
    session: Session,
    clock: SimulationClock,
    settings: Settings,
    *,
    seed: str = "",
) -> list[ActivationCandidate]:
    """Score every agent, highest first.

    Components present in Packet 3: unread direct messages, the period's
    baseline, a seeded curiosity jitter, and a penalty for having acted already
    today. Social, research and rabbit-hole triggers join as their packets land.
    """
    period_score = PERIOD_WEIGHT.get(clock.current_period, 1.0)
    candidates: list[ActivationCandidate] = []

    dormant_hole_member_ids: set[str] = set(
        session.scalars(
            select(RabbitHoleMember.agent_id)
            .join(RabbitHoleModel, RabbitHoleMember.rabbit_hole_id == RabbitHoleModel.id)
            .where(
                RabbitHoleMember.left_at.is_(None),
                RabbitHoleModel.status == RabbitHoleStatus.DORMANT,
            )
        )
    )

    for agent in session.scalars(select(Agent).order_by(Agent.id)):
        unread = session.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.recipient_agent_id == agent.agent_id,
                Message.read_at.is_(None),
            )
        ) or 0
        activations_today = session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.agent_id == agent.agent_id,
                Event.sim_day == clock.current_day,
                Event.event_type.in_(ACTIVATION_EVENTS),
            )
        ) or 0

        rng = random.Random(
            hashlib.sha256(
                f"{seed}|{agent.agent_id}|{clock.current_day}|{clock.current_period}"
                f"|{activations_today}".encode()
            ).hexdigest()[:16]
        )
        components = {
            "unread_message": unread * UNREAD_MESSAGE_POINTS,
            "period": period_score,
            "curiosity": rng.random() * CURIOSITY_MAX,
            "recent_activation_penalty": -activations_today * RECENT_ACTIVATION_PENALTY,
            "dormant_rabbit_hole_pull": (
                DORMANT_RABBIT_HOLE_PULL if agent.agent_id in dormant_hole_member_ids else 0.0
            ),
        }
        # A hard daily ceiling, so no agent can monopolise a day however it scores.
        score = (
            0.0
            if activations_today >= settings.max_daily_agent_activations
            else sum(components.values())
        )
        candidates.append(
            ActivationCandidate(
                agent_id=agent.agent_id,
                score=score,
                components=components,
                activations_today=activations_today,
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.agent_id))
    return candidates


def next_agent(
    session: Session,
    clock: SimulationClock,
    settings: Settings,
    *,
    seed: str = "",
) -> ActivationCandidate | None:
    """The single agent with the best case for acting now, if any qualifies."""
    for candidate in score_agents(session, clock, settings, seed=seed):
        if candidate.is_eligible:
            return candidate
    return None
