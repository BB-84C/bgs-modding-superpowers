"""Base LLM client response models and protocol ownership."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from bgs_translator.pipeline.batcher import Batch


@dataclass(frozen=True)
class TokenUsage:
    """Normalized token usage for one provider response."""

    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    """Normalized LLM response envelope."""

    items: dict[str, str]
    usage: TokenUsage
    cost_usd: float | None = None
    cost_exact: bool = False
    request_id: str | None = None
    raw_response_path: Path | None = None
    via: Literal[
        "responses", "messages", "generate_content", "chat_completions", "synthetic"
    ] = "synthetic"


class LLMClient(Protocol):
    """Minimal protocol shared by synthetic and future provider clients."""

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Translate a planned batch using ``system_prompt``."""


__all__ = ["LLMClient", "LLMResponse", "TokenUsage"]
