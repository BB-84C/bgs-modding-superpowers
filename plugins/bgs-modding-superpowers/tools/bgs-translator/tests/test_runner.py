"""Tests for batch runner lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch, BatchPlan
from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage
from bgs_translator.pipeline.clients.synthetic import SyntheticLLMClient
from bgs_translator.pipeline.mask import build_masked_unit


def _plan(source: str = "Hello") -> BatchPlan:
    unit = TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source=source)
    batch = Batch("b1", [build_masked_unit(unit)], None, [], [])
    return BatchPlan("p1", "demo", "synthetic", "zh-cn", "dialogue", [batch], 1, 10, 10, 0.0, "system")


def test_batch_runner_with_synthetic_client_runs_to_completion(tmp_path: object, monkeypatch: object) -> None:
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.observability.rate_tracker import RateTracker
    from bgs_translator.pipeline.runner import BatchRunner

    profile = ProviderProfile(
        name="synthetic",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
    )
    runner = BatchRunner(_plan(), SyntheticLLMClient(), RateTracker(profile), CostTracker(profile))

    result = asyncio.run(runner.run("run1"))

    assert result.succeeded == 1
    assert result.manual_review == 0
    assert result.cost_usd >= 0


def test_batch_runner_emits_start_and_complete_events() -> None:
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.observability.rate_tracker import RateTracker
    from bgs_translator.pipeline.runner import BatchEvent, BatchRunner

    async def run() -> list[BatchEvent]:
        profile = ProviderProfile(
            name="synthetic",
            sdk_kind="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-5-mini",
            api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
        )
        queue: asyncio.Queue[BatchEvent] = asyncio.Queue()
        runner = BatchRunner(_plan(), SyntheticLLMClient(), RateTracker(profile), CostTracker(profile))
        await runner.run("run1", event_queue=queue)
        return [queue.get_nowait(), queue.get_nowait()]

    events = asyncio.run(run())

    assert [event.kind for event in events] == ["start", "complete"]


def test_batch_runner_cancellation_stops_before_dispatch() -> None:
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.observability.rate_tracker import RateTracker
    from bgs_translator.pipeline.runner import BatchRunner

    async def run_cancelled() -> object:
        profile = ProviderProfile(
            name="synthetic",
            sdk_kind="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-5-mini",
            api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
        )
        cancel = asyncio.Event()
        cancel.set()
        runner = BatchRunner(_plan(), SyntheticLLMClient(), RateTracker(profile), CostTracker(profile))
        return await runner.run("run1", cancel_event=cancel)

    result = asyncio.run(run_cancelled())

    assert result.cancelled == 1


def test_batch_runner_retries_failed_validation_then_succeeds() -> None:
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.observability.rate_tracker import RateTracker
    from bgs_translator.pipeline.runner import BatchRunner

    class FlakyClient:
        def __init__(self) -> None:
            self.calls = 0

        async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
            self.calls += 1
            text = "translated {{P0}}" if self.calls > 1 else "missing"
            return LLMResponse({"I1": text}, TokenUsage(1, 1), via="synthetic")

        async def aclose(self) -> None:
            pass

    unit = TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Value %d")
    batch = Batch("b1", [build_masked_unit(unit)], None, [], [])
    plan = replace(_plan(), batches=[batch])
    profile = ProviderProfile(
        name="synthetic",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
    )
    client = FlakyClient()
    runner = BatchRunner(plan, client, RateTracker(profile), CostTracker(profile))

    result = asyncio.run(runner.run("run1"))

    assert client.calls == 2
    assert result.retried == 1
    assert result.succeeded == 1


def test_batch_runner_routes_to_manual_review_after_max_retries() -> None:
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.observability.rate_tracker import RateTracker
    from bgs_translator.pipeline.runner import BatchRunner

    class BadClient:
        async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
            return LLMResponse({"I1": "missing"}, TokenUsage(1, 1), via="synthetic")

        async def aclose(self) -> None:
            pass

    unit = TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Value %d")
    batch = Batch("b1", [build_masked_unit(unit)], None, [], [])
    plan = replace(_plan(), batches=[batch])
    profile = ProviderProfile(
        name="synthetic",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
    )
    runner = BatchRunner(plan, BadClient(), RateTracker(profile), CostTracker(profile), max_retries=1)

    result = asyncio.run(runner.run("run1"))

    assert result.manual_review == 1
    assert result.succeeded == 0
