"""The LLM provider boundary.

Services never import an SDK. They ask a provider for a decision and get back a
validated envelope plus the usage that producing it cost. Swapping fixture for
live is a configuration change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.actions import AgentDecision


class LLMError(RuntimeError):
    """The provider could not produce a decision."""


class LLMSchemaError(LLMError):
    """The provider returned something that is not a valid decision envelope."""


@dataclass(frozen=True)
class LLMUsage:
    """What one call consumed. Mirrors the fields the Messages API reports."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    stop_reason: str | None = None


@dataclass(frozen=True)
class LLMResult:
    """A decision, and the provenance of how it was produced.

    ``is_fixture`` travels with every result and is persisted on the
    ``llm_runs`` row. Fixture output is never presented as a live model
    decision — that distinction is the whole point of recording it.
    """

    decision: AgentDecision
    usage: LLMUsage
    provider: str
    model: str
    is_fixture: bool
    latency_ms: int


class LLMProvider(Protocol):
    """What every model adapter must offer."""

    name: str
    is_fixture: bool

    def decide(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
    ) -> LLMResult:
        """Return one validated :class:`AgentDecision`."""
        ...
