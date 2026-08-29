"""The LLM provider boundary.

Services never import an SDK. They ask a provider to complete one structured
output and get back a validated object plus the usage that producing it cost.
Swapping fixture for live, or Anthropic for another company, is a
configuration change — nothing in ``app/services`` names a vendor.

The interface is generic over the output schema (:class:`AgentDecision` for a
turn, :class:`~app.schemas.research.ResearchSynthesis` for a research session,
and whatever a later packet's report generator needs) rather than one method
per purpose. Adding a new structured call is a new Pydantic model, not a new
provider method every adapter must grow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The provider could not produce a result."""


class LLMSchemaError(LLMError):
    """The provider returned something that does not match the requested schema."""


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
    """A structured output, and the provenance of how it was produced.

    ``output`` is left untyped here (a Protocol method narrows it per call) so
    this dataclass does not have to be generic; every caller knows the type it
    asked for. ``is_fixture`` travels with every result and is persisted on the
    ``llm_runs`` row — fixture output is never presented as a live model
    decision, which is the whole point of recording it.
    """

    output: BaseModel
    usage: LLMUsage
    provider: str
    model: str
    is_fixture: bool
    latency_ms: int


class LLMProvider(Protocol):
    """What every model adapter must offer, regardless of company."""

    name: str
    is_fixture: bool

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        purpose: str,
        output_type: type[T],
    ) -> LLMResult:
        """Return one validated instance of ``output_type``.

        ``purpose`` is a free-text label (``"agent_decision"``,
        ``"research_synthesis"``, ...) carried onto telemetry; it never changes
        provider behaviour, so a provider may not branch on it.
        """
        ...
