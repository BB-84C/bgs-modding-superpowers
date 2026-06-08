"""Base LLM client response models and protocol ownership."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.pipeline.batcher import Batch


@dataclass(frozen=True)
class TokenUsage:
    """Normalized token usage for one provider response."""

    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class RateLimit:
    """Provider rate-limit headers, when available."""

    limit_requests: int | None = None
    remaining_requests: int | None = None
    reset_requests: datetime | None = None
    limit_tokens: int | None = None
    remaining_tokens: int | None = None
    reset_tokens: datetime | None = None
    retry_after_seconds: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Normalized LLM response envelope."""

    items: dict[str, str]
    usage: TokenUsage
    cost_usd: float | None = None
    cost_exact: bool = False
    rate_limit_observed: RateLimit | None = None
    request_id: str | None = None
    raw_response_path: Path | None = None
    raw_response: Any | None = None
    via: Literal[
        "responses", "messages", "generate_content", "chat_completions", "synthetic"
    ] = "synthetic"


class BatchTranslationOutput(BaseModel):
    """Provider-independent strict structured output schema."""

    items: dict[str, str]

    model_config = ConfigDict(extra="forbid")


class LLMClient(Protocol):
    """Protocol shared by provider clients."""

    profile: ProviderProfile

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Translate a planned batch using ``system_prompt``."""

    async def aclose(self) -> None:
        """Close provider resources."""


def build_client_for(profile: ProviderProfile) -> LLMClient:
    """Build a provider client for the profile's sdk_kind."""

    if profile.sdk_kind == "openai":
        from bgs_translator.pipeline.clients.openai_responses import OpenAIResponsesClient

        return OpenAIResponsesClient(profile)
    if profile.sdk_kind == "anthropic":
        from bgs_translator.pipeline.clients.anthropic_messages import AnthropicMessagesClient

        return AnthropicMessagesClient(profile)
    if profile.sdk_kind == "gemini":
        from bgs_translator.pipeline.clients.gemini_generate import GeminiGenerateClient

        return GeminiGenerateClient(profile)
    if profile.sdk_kind == "openai-compat":
        from bgs_translator.pipeline.clients.openai_compat_cc import (
            OpenAICompatChatCompletionsClient,
        )

        return OpenAICompatChatCompletionsClient(profile)
    raise ValueError(f"Unsupported sdk_kind: {profile.sdk_kind}")


__all__ = [
    "BatchTranslationOutput",
    "LLMClient",
    "LLMResponse",
    "RateLimit",
    "TokenUsage",
    "build_client_for",
]
