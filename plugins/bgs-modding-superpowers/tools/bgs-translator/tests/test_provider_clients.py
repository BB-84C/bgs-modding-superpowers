"""Mocked provider client tests."""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch
from bgs_translator.pipeline.mask import build_masked_unit


def _batch() -> Batch:
    unit = TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Hello")
    return Batch("b1", [build_masked_unit(unit)], None, [], [])


def _profile(sdk_kind: str, base_url: str, json_mode: str | None = None) -> Any:
    from bgs_translator.config.profiles import ProviderProfile

    return ProviderProfile(
        name="p",
        sdk_kind=sdk_kind,
        base_url=base_url,
        model="model",
        api_key_env="BGS_TRANSLATOR_KEY",
        json_mode=json_mode,
        require_parameters="openrouter" in base_url,
    )


async def test_openai_responses_client_uses_responses_text_format(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponses:
        async def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_1",
                output=[SimpleNamespace(content=[SimpleNamespace(parsed={"items": {"I1": "Bonjour"}})])],
                usage=SimpleNamespace(input_tokens=3, output_tokens=4, total_tokens=7),
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    import bgs_translator.pipeline.clients.openai_responses as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    client = module.OpenAIResponsesClient(_profile("openai", "https://api.openai.com/v1"))

    response = await client.translate_batch(_batch(), "system")

    assert response.items == {"I1": "Bonjour"}
    assert response.via == "responses"
    assert "response_format" not in captured
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["strict"] is True


async def test_anthropic_client_uses_forced_tool_use(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeMessages:
        async def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(
                id="msg_1",
                content=[SimpleNamespace(type="tool_use", name="translate_batch", input={"items": {"I1": "Salut"}})],
                usage=SimpleNamespace(
                    input_tokens=5,
                    output_tokens=6,
                    cache_creation_input_tokens=7,
                    cache_read_input_tokens=8,
                ),
            )

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            self.messages = FakeMessages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic))
    import bgs_translator.pipeline.clients.anthropic_messages as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    profile = _profile("anthropic", "https://api.anthropic.com/v1")
    profile.prompt_caching = True
    client = module.AnthropicMessagesClient(profile)

    response = await client.translate_batch(_batch(), "system")

    assert response.items == {"I1": "Salut"}
    assert response.via == "messages"
    assert captured["tool_choice"] == {"type": "tool", "name": "translate_batch"}
    assert response.usage.cached_tokens == 15


async def test_gemini_client_uses_response_schema(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeModels:
        def generate_content(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(
                text=json.dumps({"items": {"I1": "Hola"}}),
                usage_metadata=SimpleNamespace(
                    prompt_token_count=2,
                    candidates_token_count=3,
                    total_token_count=5,
                ),
            )

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.models = FakeModels()

    google_mod = types.ModuleType("google")
    genai_mod = SimpleNamespace(Client=FakeClient)
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    import bgs_translator.pipeline.clients.gemini_generate as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    client = module.GeminiGenerateClient(_profile("gemini", "https://generativelanguage.googleapis.com"))

    response = await client.translate_batch(_batch(), "system")

    assert response.items == {"I1": "Hola"}
    assert response.via == "generate_content"
    assert captured["config"]["response_mime_type"] == "application/json"
    assert captured["config"]["response_schema"].__name__ == "BatchTranslationOutput"


@dataclass
class _Usage:
    prompt_tokens: int = 9
    completion_tokens: int = 10
    total_tokens: int = 19
    cost: float | None = None


async def test_openai_compat_client_deepseek_uses_json_object(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(
                id="chat_1",
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"items": {"I1": "Ciao"}})))],
                usage=_Usage(),
            )

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    import bgs_translator.pipeline.clients.openai_compat_cc as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    client = module.OpenAICompatChatCompletionsClient(
        _profile("openai-compat", "https://api.deepseek.com", "json_object")
    )

    response = await client.translate_batch(_batch(), "system")

    assert response.items == {"I1": "Ciao"}
    assert response.via == "chat_completions"
    assert captured["response_format"] == {"type": "json_object"}


async def test_openai_compat_client_openrouter_uses_schema_and_provider_routing(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    class FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(
                id="chat_2",
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"items": {"I1": "Hej"}})))],
                usage=_Usage(cost=0.001),
            )

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    import bgs_translator.pipeline.clients.openai_compat_cc as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    client = module.OpenAICompatChatCompletionsClient(
        _profile("openai-compat", "https://openrouter.ai/api/v1", "json_schema")
    )

    response = await client.translate_batch(_batch(), "system")

    assert response.cost_exact is True
    assert response.cost_usd == 0.001
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["extra_body"] == {"provider": {"require_parameters": True}}
    assert "usage" not in captured
