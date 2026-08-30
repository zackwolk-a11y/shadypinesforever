"""The Research Wall: the clubhouse's one shared, public surface.

Posting is always the agent's own choice — nothing here ever posts on an
agent's behalf. Reading in full is also a choice, distinct from glancing at a
headline: everyone sees every recent headline (the wall is physically shared
infrastructure), but only ``READ_WALL_POST`` turns that into real exposure,
including exposure to whatever research the post cites (§ cross-pollination).

``find_cross_pollination_candidate`` is the mechanical half of "an agent
should be able to encounter another agent's post and connect it to its own
interests": cheap keyword overlap, no model call, surfacing at most one
candidate so it nudges without overwhelming. What the agent does with the
nudge — investigate, challenge, discuss, or ignore it — is never decided here.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agents import AgentInterest
from app.db.models.wall import ResearchWallPost
from app.db.models.world import SimulationClock
from app.domain.enums import EventType, ExposureType, WallPostType
from app.services.events import record_event
from app.services.exposure import expose, expose_shared_research, exposed_entity_ids

#: A CONNECTION this deliberately similar to one already made is noise, not
#: cross-pollination — "recently explored connections" penalty from the spec.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "and", "or", "for", "with", "about", "this", "that", "it", "as", "at",
    "be", "by", "from", "has", "have", "not", "what", "how", "do", "does",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def post_to_wall(
    session: Session,
    agent_id: str,
    post_type: WallPostType,
    content: str,
    clock: SimulationClock,
    correlation_id: str,
    *,
    related_research_id: str | None = None,
    related_wall_post_id: int | None = None,
    related_rabbit_hole_id: int | None = None,
) -> tuple[ResearchWallPost, int]:
    """Pin one post. Returns the row and the event id that recorded it."""
    post = ResearchWallPost(
        agent_id=agent_id,
        post_type=post_type,
        content=content,
        related_research_id=related_research_id,
        related_wall_post_id=related_wall_post_id,
        related_rabbit_hole_id=related_rabbit_hole_id,
    )
    session.add(post)
    session.flush()

    event = record_event(
        session,
        event_type=EventType.RESEARCH_WALL_POSTED,
        agent_id=agent_id,
        payload={
            "post_type": post_type.value,
            "related_research_id": related_research_id,
            "related_wall_post_id": related_wall_post_id,
            "related_rabbit_hole_id": related_rabbit_hole_id,
        },
        entity_type="research_wall",
        entity_id=str(post.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    # The author obviously knows what they posted; this is what lets their own
    # later actions cite it as target_wall_post_id without a separate read.
    expose(
        session,
        agent_id=agent_id,
        entity_type="research_wall",
        entity_id=post.id,
        exposure_type=ExposureType.CREATED,
        source_event_id=event.id,
    )
    return post, event.id


def read_wall_post(
    session: Session,
    agent_id: str,
    post: ResearchWallPost,
    clock: SimulationClock,
    correlation_id: str,
) -> int:
    """Read one post in full. Cascades exposure to any research it cites.

    Returns the event id.
    """
    event = record_event(
        session,
        event_type=EventType.WALL_POST_READ,
        agent_id=agent_id,
        payload={"wall_post_id": post.id, "author": post.agent_id},
        entity_type="research_wall",
        entity_id=str(post.id),
        correlation_id=correlation_id,
        clock=clock,
    )
    expose(
        session,
        agent_id=agent_id,
        entity_type="research_wall",
        entity_id=post.id,
        exposure_type=ExposureType.WALL_READ,
        source_event_id=event.id,
    )
    if post.related_research_id:
        expose_shared_research(
            session,
            agent_id=agent_id,
            research_session_id=post.related_research_id,
            source_event_id=event.id,
        )
        record_event(
            session,
            event_type=EventType.FINDING_SHARED,
            agent_id=agent_id,
            payload={"research_id": post.related_research_id, "via_wall_post": post.id},
            entity_type="research_session",
            entity_id=post.related_research_id,
            correlation_id=correlation_id,
            causation_id=event.id,
            clock=clock,
        )
    return event.id


def already_connected(session: Session, agent_id: str, target_wall_post_id: int) -> bool:
    """Has this agent already posted a CONNECTION to this exact post?

    The anti-repetition guard for "recently explored connections": the same
    agent drawing the same line twice adds nothing.
    """
    existing = session.scalars(
        select(ResearchWallPost.id).where(
            ResearchWallPost.agent_id == agent_id,
            ResearchWallPost.post_type == WallPostType.CONNECTION,
            ResearchWallPost.related_wall_post_id == target_wall_post_id,
        )
    ).first()
    return existing is not None


def find_cross_pollination_candidate(
    session: Session, agent_id: str, *, limit_recent: int = 15
) -> tuple[ResearchWallPost, set[str]] | None:
    """The single most interest-relevant *unread* post by someone else, if any.

    Scored by plain keyword overlap between the post's content and the agent's
    own interests — no model call, no embeddings, matching the build bible's
    "search cheaply" mechanism-not-content philosophy. Returns ``None`` when
    nothing clears a minimal overlap bar, which is the common case: most posts
    are not relevant to most agents, and that is the point of it being partial
    knowledge rather than a feed everyone reads in full.
    """
    interests = session.scalars(
        select(AgentInterest.interest).where(AgentInterest.agent_id == agent_id)
    ).all()
    interest_words: set[str] = set()
    for interest in interests:
        interest_words |= _keywords(interest)
    if not interest_words:
        return None

    read_ids = exposed_entity_ids(session, agent_id, "research_wall")

    candidates = session.scalars(
        select(ResearchWallPost)
        .where(ResearchWallPost.agent_id != agent_id)
        .order_by(ResearchWallPost.id.desc())
        .limit(limit_recent)
    ).all()

    best: tuple[ResearchWallPost, set[str]] | None = None
    best_score = 0
    for post in candidates:
        if str(post.id) in read_ids:
            continue
        overlap = interest_words & _keywords(post.content)
        if len(overlap) > best_score:
            best = (post, overlap)
            best_score = len(overlap)

    return best if best_score >= 1 else None
