"""Anthropic Messages API client ownership."""

from __future__ import annotations

import importlib
import inspect
import json
from typing import Any

from bgs_translator.config.profiles import ProviderProfile, resolve_api_key
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.clients.base import BatchTranslationOutput, LLMResponse, TokenUsage


class AnthropicMessagesClient:
    """sdk_kind=anthropic. Uses Messages API with tool_use forced strict schema."""

    def __init__(self, profile: ProviderProfile):
        anthropic_mod = importlib.import_module("anthropic")
        async_anthropic = anthropic_mod.AsyncAnthropic
        key = resolve_api_key(profile)
        self.profile = profile
        self.client: Any = async_anthropic(api_key=key)

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Translate one batch through Anthropic Messages tool use."""

        kwargs = self._request_kwargs(batch, system_prompt, cache=True)
        try:
            response = await _maybe_await(self.client.messages.create(**kwargs))
        except Exception as exc:
            if not self.profile.prompt_caching or "cache" not in str(exc).casefold():
                raise
            response = await _maybe_await(
                self.client.messages.create(**self._request_kwargs(batch, system_prompt, cache=False))
            )
        output = BatchTranslationOutput.model_validate(_extract_tool_input(response))
        return LLMResponse(
            items=output.items,
            usage=_usage_from_response(response),
            request_id=_as_optional_str(getattr(response, "id", None)),
            via="messages",
        )

    async def aclose(self) -> None:
        close = getattr(self.client, "aclose", None)
        if close is not None:
            await _maybe_await(close())

    def _request_kwargs(self, batch: Batch, system_prompt: str, *, cache: bool) -> dict[str, Any]:
        system: str | list[dict[str, Any]]
        user_content: str | list[dict[str, Any]]
        user_json = _user_message(batch)
        if self.profile.prompt_caching and cache:
            system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
            user_content = [{"type": "text", "text": user_json, "cache_control": {"type": "ephemeral"}}]
        else:
            system = system_prompt
            user_content = user_json
        return {
            "model": self.profile.model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user_content}],
            "tools": [
                {
                    "name": "translate_batch",
                    "description": "Return the batch translation JSON object.",
                    "input_schema": BatchTranslationOutput.model_json_schema(),
                }
            ],
            "tool_choice": {"type": "tool", "name": "translate_batch"},
        }


def _user_message(batch: Batch) -> str:
    items = {f"I{index}": item.source_masked for index, item in enumerate(batch.items, start=1)}
    return json.dumps({"items": items}, ensure_ascii=False)


def _extract_tool_input(response: Any) -> Any:
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "translate_batch":
            return getattr(block, "input", None)
    raise ValueError("Anthropic response did not include translate_batch tool_use")


def _usage_from_response(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    cache_created = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cached_tokens = cache_created + cache_read
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        total_tokens=input_tokens + output_tokens + cached_tokens,
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _as_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


__all__ = ["AnthropicMessagesClient"]
