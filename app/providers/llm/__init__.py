"""LLM provider selection."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.providers.llm.base import LLMError, LLMProvider, LLMResult, LLMUsage

__all__ = ["LLMError", "LLMProvider", "LLMResult", "LLMUsage", "get_llm_provider"]


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Build the configured provider. Defaults to the fixture."""
    settings = settings or get_settings()

    if settings.llm_provider == "fixture":
        from app.providers.llm.fixture import FixtureLLMProvider

        return FixtureLLMProvider()

    if settings.llm_provider == "anthropic":
        from app.providers.llm.anthropic import AnthropicLLMProvider

        return AnthropicLLMProvider(api_key=settings.anthropic_api_key)

    raise LLMError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}; expected 'fixture' or 'anthropic'."
    )
