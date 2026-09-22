"""Agent memory (§9, §17, Packet 7).

A memory is never handed the full event log. Something becomes a memory only
when ``app.services.memory`` judges it likely to matter later (§ memory
selection), and every field here exists to make that judgment — and later
retrieval — cheap without re-deriving it from the event log each time:

- ``importance``/``confidence`` are the two independent axes a memory is
  scored on: how much it matters, and how sure the agent is of it. A
  surprising, unresolved research result can be highly important and *low*
  confidence at once.
- ``created_sim_day``/``last_accessed_sim_day`` mirror the simulated-day
  convention already used for rabbit-hole staleness (``last_activity_day``)
  rather than wall-clock time — an agent's sense of "a while ago" is
  simulated days, not however fast the fixture happened to run.
- ``reinforcement_count``/``decay_score`` are the mechanism behind §5/§6:
  a memory that keeps getting corroborated strengthens; a low-importance one
  that nobody has needed in a long time decays in retrieval priority. Neither
  ever deletes a row — see :mod:`app.services.memory`.
- The four ``related_*`` lists are typed on purpose (research/agent/rabbit
  hole ids, plus the event ids that caused this memory to exist) rather than
  one generic bag, so retrieval can ask "does this memory concern agent X" or
  "does this memory concern rabbit hole Y" precisely. None are foreign-keyed:
  a memory may legitimately point at something that has since been resolved,
  retired, or otherwise changed shape, and should still be recallable.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import MemoryType

from app.db.base import Base, TimestampMixin
from app.db.models.agents import AGENT_FK

#: Every memory starts at full retrieval weight; only decay lowers it, and
#: only for low-importance memories nobody has needed in a while (§6).
DEFAULT_DECAY_SCORE = 1.0


class Memory(TimestampMixin, Base):
    """One remembered thing, agent-private by construction.

    Privacy (§11) needs no extra enforcement here: every query against this
    table filters by ``agent_id``, and nothing ever joins across agents. A
    memory only comes to exist because something the owning agent actually
    experienced, was told, or was exposed to caused it — see the trigger
    points in :mod:`app.services.memory`.
    """

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(AGENT_FK), index=True, nullable=False
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType, name="memory_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    importance: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=70.0)

    created_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_accessed_sim_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_event_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_research_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_agent_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_rabbit_hole_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: Not in the build bible's minimum field list, but the same typed-list
    #: convention as the other three: lets a SEMANTIC memory about a belief's
    #: latest twist be found and reinforced on the belief's *next* revision
    #: (§5) without collapsing belief and memory into one concept (§14).
    related_belief_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: Packet 8: which conversation(s) this memory came out of — lets a later
    #: conversation reference "that thing you said" honestly, by finding the
    #: real conversation behind a memory rather than inferring one.
    related_conversation_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    decay_score: Mapped[float] = mapped_column(Float, nullable=False, default=DEFAULT_DECAY_SCORE)
    reinforcement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
