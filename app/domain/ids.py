"""Stable identifier generation for the Village's business keys.

Agents carry authored ids (``agent_optimisto``); everything else that needs a
stable string key gets one from here, so the format is decided in one place.
"""

from __future__ import annotations

import uuid


def _short() -> str:
    return uuid.uuid4().hex[:12]


def new_research_id() -> str:
    """A ``research_id`` for a research session."""
    return f"res_{_short()}"


def new_correlation_id() -> str:
    """A correlation id tying every event of one causal chain together."""
    return f"corr_{_short()}"
