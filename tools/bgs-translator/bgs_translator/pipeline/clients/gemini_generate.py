"""Gemini generate_content client ownership."""

from __future__ import annotations

import importlib
import inspect
import json
from typing import Any

from bgs_translator.config.profiles import ProviderProfile, resolve_api_key
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.clients.base import BatchTranslationOutput, LLMResponse, TokenUsage
from bgs_translator.pipeline.item_payload import batch_items_payload


class GeminiGenerateClient:
    """sdk_kind=gemini. Uses google-genai with response_schema."""

    def __init__(self, profile: ProviderProfile):
        genai_mod = importlib.import_module("google.genai")
        client_cls = genai_mod.Client
        key = resolve_api_key(profile)
        self.profile = profile
        self.client: Any = client_cls(api_key=key)

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Translate one batch via Gemini generate_content."""

        response = await _maybe_await(
            self.client.models.generate_content(
                model=self.profile.model,
                contents=_user_message(batch),
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "response_schema": BatchTranslationOutput,
                },
            )
        )
        output = BatchTranslationOutput.model_validate(json.loads(str(getattr(response, "text", "{}"))))
        return LLMResponse(items=output.items, usage=_usage_from_response(response), via="generate_content")

    async def aclose(self) -> None:
        close = getattr(self.client, "aclose", None)
        if close is not None:
            await _maybe_await(close())


def _user_message(batch: Batch) -> str:
    items = batch_items_payload(batch)
    return json.dumps({"items": items}, ensure_ascii=False)


def _usage_from_response(response: Any) -> TokenUsage:
    usage = getattr(response, "usage_metadata", None)
    input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    total_tokens = int(getattr(usage, "total_token_count", input_tokens + output_tokens) or 0)
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


__all__ = ["GeminiGenerateClient"]
