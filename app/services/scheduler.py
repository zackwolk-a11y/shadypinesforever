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
#: Discourages back-to-back reactivation without silently overriding
#: ``Settings.max_daily_agent_activations`` (the documented "real" per-agent
#: daily ceiling — see that field's own comment in app/core/config.py).
#: The two mechanisms must stay arithmetically consistent: the highest
#: possible positive score in any period is PERIOD_WEIGHT's max (3.0) plus
#: CURIOSITY_MAX (2.0) = 5.0, so this penalty must stay well under
#: 5.0 / (max_daily_agent_activations - 1) or the soft penalty alone
#: silently zeroes out eligibility long before the configured hard cap is
#: ever reached. The previous value (2.5) crossed that line: at just 2
#: prior activations (2.5x2=5.0), a positive score became mathematically
#: impossible in every period for every agent at once, village-wide,
#: however many of the configured 6 daily activations (48 across all 8
#: agents) remained unused — this is what silently emptied RESEARCH/
#: AFTERNOON/EVENING/NIGHT on the first real live day after only the
#: morning gathering and a partial first round (Packet 12 live-day
#: diagnostic; see scripts/smoke_test_daily_activation_budget.py). 0.75
#: keeps a real, felt bias toward whoever hasn't gone yet (an agent's
#: first repeat costs -0.75, a meaningful discount against an untouched
#: agent's typical ~period+1.0) while leaving a real, not just
#: theoretical, chance of reaching the configured cap across a full day.
RECENT_ACTIVATION_PENALTY = 0.75
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


def activations_today(session: Session, agent_id: str, clock: SimulationClock) -> int:
    """How many times this agent has already been activated today.

    The single source of truth every activation-granting path must consult
    before handing out another one — not just this module's own
    ``score_agents``. Conversation turn-taking
    (``app.services.conversations.next_speaker``) and joining a conversation
    (``app.services.dialogue.find_joiner``) each grant a real activation
    exactly like the scheduler does (the same ``AGENT_ACTED``/
    ``INVALID_AGENT_DECISION`` event lands either way), so each must respect
    the same day-wide ``Settings.max_daily_agent_activations`` budget this
    counts against — a scheduler-only check left conversation rotation free
    to hand one agent unlimited activations while the rest of the village
    waited (Packet 12's scheduler/conversation correctness fix).
    """
    return (
        session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.agent_id == agent_id,
                Event.sim_day == clock.current_day,
                Event.event_type.in_(ACTIVATION_EVENTS),
            )
        )
        or 0
    )


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
        agent_activations_today = activations_today(session, agent.agent_id, clock)

        rng = random.Random(
            hashlib.sha256(
                f"{seed}|{agent.agent_id}|{clock.current_day}|{clock.current_period}"
                f"|{agent_activations_today}".encode()
            ).hexdigest()[:16]
        )
        components = {
            "unread_message": unread * UNREAD_MESSAGE_POINTS,
            "period": period_score,
            "curiosity": rng.random() * CURIOSITY_MAX,
            "recent_activation_penalty": -agent_activations_today * RECENT_ACTIVATION_PENALTY,
            "dormant_rabbit_hole_pull": (
                DORMANT_RABBIT_HOLE_PULL if agent.agent_id in dormant_hole_member_ids else 0.0
            ),
        }
        # A hard daily ceiling, so no agent can monopolise a day however it scores.
        score = (
            0.0
            if agent_activations_today >= settings.max_daily_agent_activations
            else sum(components.values())
        )
        candidates.append(
            ActivationCandidate(
                agent_id=agent.agent_id,
                score=score,
                components=components,
                activations_today=agent_activations_today,
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
