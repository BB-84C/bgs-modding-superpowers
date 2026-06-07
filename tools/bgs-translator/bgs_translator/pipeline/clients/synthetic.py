"""Synthetic LLM client for deterministic pipeline tests."""

from __future__ import annotations

from bgs_translator.pipeline.batcher import Batch, estimate_tokens
from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage


class SyntheticLLMClient:
    """Return each item's masked source as its destination."""

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Return identity translations without dispatching to a provider."""

        items = {f"I{index}": item.source_masked for index, item in enumerate(batch.items, start=1)}
        input_tokens = estimate_tokens(system_prompt) + estimate_tokens(
            "\n".join(item.source_masked for item in batch.items)
        )
        output_tokens = estimate_tokens("\n".join(items.values()))
        return LLMResponse(
            items=items,
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            via="synthetic",
        )


__all__ = ["SyntheticLLMClient"]
