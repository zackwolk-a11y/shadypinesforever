"""Persistent, personal unresolved curiosity — one agent's own open question,
distinct from a shared Rabbit Hole and from the write-only
``ResearchSession.open_questions``/``follow_ups`` fields this feature draws
its organic creation material from (see :mod:`app.services.agent_questions`).

Deliberately small: no embedding/semantic-similarity fields, no
collaboration fields (that stays Rabbit Holes' job — see
``rabbit_hole_id``, the escalation link, not a duplicate of
``RabbitHoleMember``), and only the five lifecycle states
:class:`~app.domain.enums.AgentQuestionStatus` defines.
"""

from __future__ import annotations

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK
from app.db.models.research import RESEARCH_FK
from app.domain.enums import AgentQuestionStatus

QUESTION_FK = "agent_questions.id"


class AgentQuestion(TimestampMixin, Base):
    """One agent's own, still-open (or not) curiosity.

    ``origin_*`` columns are independent and nullable — a question is
    typically born from exactly one of them, recorded once and never
    overwritten, so provenance survives even once the originating row (a
    reflection, a memory) is itself long superseded or decayed.
    ``research_session_id`` is a different, forward-looking link: which
    research session, if any, is *currently* pursuing this question — set
    only when an agent explicitly links START_RESEARCH to it
    (``AgentAction.target_question_id``), and never implied by research
    merely existing on the same topic.
    """

    __tablename__ = "agent_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentQuestionStatus] = mapped_column(
        Enum(AgentQuestionStatus, name="agent_question_status"),
        nullable=False,
        default=AgentQuestionStatus.OPEN,
    )
    #: 0-100, the same scale as Memory.importance/AgentReflection.importance —
    #: reused deliberately rather than a third scoring convention.
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=45.0)
    #: Simulated day of the last explicit engagement (creation, revisit, a
    #: reflection touching it, a research link) — what daily decay judges
    #: staleness against, mirroring AgentInterest.last_engaged_sim_day.
    last_engaged_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    origin_memory_id: Mapped[int | None] = mapped_column(
        ForeignKey("memories.id"), nullable=True
    )
    origin_reflection_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_reflections.id"), nullable=True
    )
    origin_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    #: The completed research session whose open_questions/follow_ups this
    #: question was organically drawn from, if any — distinct from
    #: research_session_id below, which is about research pursuing THIS
    #: question, not research this question came FROM.
    origin_research_session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), nullable=True
    )

    #: Forward link: the research session currently pursuing this question,
    #: set only via an explicit target_question_id on START_RESEARCH.
    research_session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey(RESEARCH_FK), nullable=True
    )
    #: The collaborative escalation, if this question ever graduated into a
    #: shared Rabbit Hole investigation. Set by ordinary application code
    #: alongside CREATE_RABBIT_HOLE/CONTRIBUTE_TO_RABBIT_HOLE bookkeeping,
    #: never a second collaboration mechanism of its own.
    rabbit_hole_id: Mapped[int | None] = mapped_column(
        ForeignKey("rabbit_holes.id"), nullable=True
    )

    #: Reformulation preserves lineage rather than silently overwriting: the
    #: old row is marked RESOLVED (its phrasing reached its natural end by
    #: becoming a better question) and points forward; the new row points
    #: back. Both nullable, both self-referential.
    reformulated_from_id: Mapped[int | None] = mapped_column(ForeignKey(QUESTION_FK), nullable=True)
    reformulated_into_id: Mapped[int | None] = mapped_column(ForeignKey(QUESTION_FK), nullable=True)
