"""OpenAI-compatible chat-completions client ownership."""

from __future__ import annotations

import importlib
import inspect
import json
from typing import Any

from bgs_translator.config.profiles import ProviderProfile, resolve_api_key
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.clients.base import BatchTranslationOutput, LLMResponse, TokenUsage


class OpenAICompatChatCompletionsClient:
    """sdk_kind=openai-compat. Uses chat.completions honestly."""

    def __init__(self, profile: ProviderProfile):
        openai_mod = importlib.import_module("openai")
        async_openai = openai_mod.AsyncOpenAI
        key = resolve_api_key(profile)
        self.profile = profile
        self.client: Any = async_openai(
            api_key=key,
            base_url=profile.base_url,
            default_headers=profile.extra_headers or None,
        )

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        """Translate one batch through chat completions."""

        kwargs: dict[str, Any] = {
            "model": self.profile.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _user_message(batch, self.profile.json_mode)},
            ],
            "response_format": _response_format(self.profile),
        }
        if self.profile.require_parameters:
            kwargs["extra_body"] = {"provider": {"require_parameters": True}}
        response = await _maybe_await(self.client.chat.completions.create(**kwargs))
        content = getattr(response.choices[0].message, "content", "{}")
        output = BatchTranslationOutput.model_validate(json.loads(str(content)))
        usage = _usage_from_response(response)
        cost_credits = _openrouter_cost_credits(response) if _is_openrouter(self.profile.base_url) else None
        return LLMResponse(
            items=output.items,
            usage=usage,
            cost_usd=cost_credits,
            cost_exact=cost_credits is not None,
            request_id=_as_optional_str(getattr(response, "id", None)),
            via="chat_completions",
        )

    async def aclose(self) -> None:
        close = getattr(self.client, "aclose", None)
        if close is not None:
            await _maybe_await(close())


def _response_format(profile: ProviderProfile) -> dict[str, Any]:
    if profile.json_mode == "json_schema":
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "BatchTranslation",
                "schema": BatchTranslationOutput.model_json_schema(),
                "strict": True,
            },
        }
    return {"type": "json_object"}


def _user_message(batch: Batch, json_mode: str | None) -> str:
    items = {f"I{index}": item.source_masked for index, item in enumerate(batch.items, start=1)}
    payload = json.dumps({"items": items}, ensure_ascii=False)
    if json_mode == "json_object":
        return (
            "Return as JSON matching this exact example shape: "
            '{"items":{"I1":"translated text"}}. Source batch: '
            f"{payload}"
        )
    return payload


def _usage_from_response(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


def _openrouter_cost_credits(response: Any) -> float | None:
    usage = getattr(response, "usage", None)
    raw_cost = getattr(usage, "cost", None)
    return float(raw_cost) if raw_cost is not None else None


def _is_openrouter(base_url: str) -> bool:
    return "openrouter" in base_url.casefold()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _as_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


__all__ = ["OpenAICompatChatCompletionsClient"]
