"""OpenAI Responses API client ownership."""

from __future__ import annotations

import importlib
import inspect
import json
from typing import Any

from bgs_translator.config.profiles import ProviderProfile, resolve_api_key
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.clients.base import BatchTranslationOutput, LLMResponse, TokenUsage
from bgs_translator.pipeline.item_payload import batch_items_payload


class OpenAIResponsesClient:
    """sdk_kind=openai. Uses Responses API with text.format json_schema strict."""

    def __init__(self, profile: ProviderProfile):
        openai_mod = importlib.import_module("openai")
        async_openai = openai_mod.AsyncOpenAI
        key = resolve_api_key(profile)
        self.profile = profile
        self.client: Any = async_openai(api_key=key, base_url=profile.base_url)

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Translate one batch through the Responses API."""

        response = await _maybe_await(
            self.client.responses.create(
                model=self.profile.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": _user_message(batch)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "BatchTranslation",
                        "schema": BatchTranslationOutput.model_json_schema(),
                        "strict": True,
                    }
                },
            )
        )
        output = BatchTranslationOutput.model_validate(_extract_parsed(response))
        return LLMResponse(
            items=output.items,
            usage=_usage_from_response(response),
            request_id=_as_optional_str(getattr(response, "id", None)),
            via="responses",
        )

    async def aclose(self) -> None:
        """Close the underlying SDK client when supported."""

        close = getattr(self.client, "aclose", None)
        if close is not None:
            await _maybe_await(close())


def _user_message(batch: Batch) -> str:
    items = batch_items_payload(batch)
    return json.dumps({"items": items}, ensure_ascii=False)


def _extract_parsed(response: Any) -> Any:
    for output in getattr(response, "output", []) or []:
        for content in getattr(output, "content", []) or []:
            parsed = getattr(content, "parsed", None)
            if parsed is not None:
                return parsed
            text = getattr(content, "text", None)
            if isinstance(text, str):
                return json.loads(text)
    raise ValueError("OpenAI Responses result did not include parsed structured output")


def _usage_from_response(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _as_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


__all__ = ["OpenAIResponsesClient"]
