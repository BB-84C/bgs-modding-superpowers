"""OpenAI-compatible chat-completions client regressions."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from bgs_translator.config.profiles import ProviderProfile
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.mask import build_masked_unit


@dataclass
class _Usage:
    prompt_tokens: int = 9
    completion_tokens: int = 10
    total_tokens: int = 19


def _batch() -> Batch:
    unit = TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Hello")
    return Batch("batch-empty", [build_masked_unit(unit)], None, [], [])


def _profile() -> ProviderProfile:
    return ProviderProfile(
        name="openrouter",
        sdk_kind="openai-compat",
        base_url="https://openrouter.ai/api/v1",
        model="deepseek/deepseek-v4-pro",
        api_key_env="BGS_TRANSLATOR_KEY_OPENROUTER",
        json_mode="json_schema",
    )


async def test_openai_compat_empty_content_returns_empty_completion_marker(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    class FakeCompletions:
        async def create(self, **_: Any) -> Any:
            return SimpleNamespace(
                id="req-empty",
                choices=[SimpleNamespace(message=SimpleNamespace(content="   "))],
                usage=_Usage(),
            )

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **_: Any) -> None:
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    import bgs_translator.pipeline.clients.openai_compat_cc as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    client = module.OpenAICompatChatCompletionsClient(_profile())

    with caplog.at_level(logging.WARNING):
        response = await client.translate_batch(_batch(), "system")

    assert response.items == {}
    assert response.empty_completion is True
    assert "batch-empty" in caplog.text
    assert "req-empty" in caplog.text


async def test_openai_compat_retries_json_schema_rejection_as_json_object(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    captured: list[dict[str, Any]] = []

    class FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            captured.append(kwargs)
            if len(captured) == 1:
                raise RuntimeError(
                    "Invalid schema for response_format 'BatchTranslation': invalid_json_schema"
                )
            return SimpleNamespace(
                id="req-json-object",
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":{"I1":"你好"}}'))],
                usage=_Usage(),
            )

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **_: Any) -> None:
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    import bgs_translator.pipeline.clients.openai_compat_cc as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    client = module.OpenAICompatChatCompletionsClient(_profile())

    with caplog.at_level(logging.WARNING):
        response = await client.translate_batch(_batch(), "system")

    assert response.items == {"I1": "你好"}
    assert [call["response_format"]["type"] for call in captured] == ["json_schema", "json_object"]
    assert "retrying" in caplog.text
