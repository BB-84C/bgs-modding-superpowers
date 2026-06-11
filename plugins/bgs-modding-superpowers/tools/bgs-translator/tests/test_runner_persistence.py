"""Regression tests for batch-run memory and audit persistence."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bgs_translator.config.pricing import ModelPrice, Pricing
from bgs_translator.config.profiles import ProviderProfile
from bgs_translator.core.memory import insert_units, open_memory_db
from bgs_translator.observability.cost_tracker import CostTracker
from bgs_translator.observability.rate_tracker import RateTracker
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch, BatchPlan
from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.pipeline.runner import BatchRunner
from bgs_translator.sst.status import SStrParam


class _KnownTranslationClient:
    profile = ProviderProfile(
        name="mock-profile",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_TEST",
    )

    def __init__(self, translated: str = "Bonjour") -> None:
        self.translated = translated

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del system_prompt
        return LLMResponse(
            {f"I{index}": self.translated for index, _item in enumerate(batch.items, start=1)},
            TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            via="synthetic",
        )

    async def aclose(self) -> None:
        pass


class _RetryThenSuccessClient:
    profile = _KnownTranslationClient.profile

    def __init__(self) -> None:
        self.calls = 0

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del batch, system_prompt
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                {"I1": ""},
                TokenUsage(input_tokens=10, output_tokens=0, total_tokens=10),
                via="synthetic",
            )
        return LLMResponse(
            {"I1": "Bonjour"},
            TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            via="synthetic",
        )

    async def aclose(self) -> None:
        pass


@pytest.fixture
def translator_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    return tmp_path


def test_runner_writes_dest_to_memory_sqlite(translator_home: Path) -> None:
    plan, project_root = _seeded_plan(translator_home)
    runner = _runner(plan, _KnownTranslationClient("Bonjour"))

    result = asyncio.run(runner.run("run-persist"))

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    row = conn.execute(
        """
        SELECT dest, status, sparams, via_llm, profile_used, sdk_via, last_batch_id, last_run_id
        FROM units
        """
    ).fetchone()
    assert result.succeeded == 1
    assert row == (
        "Bonjour",
        "translated",
        int(SStrParam.TRANSLATED),
        1,
        "mock-profile",
        "synthetic",
        "batch-1",
        "run-persist",
    )


def test_runner_writes_audit_artifacts(translator_home: Path) -> None:
    plan, project_root = _seeded_plan(translator_home)
    runner = _runner(plan, _KnownTranslationClient("Bonjour"))

    asyncio.run(runner.run("run-audit"))

    run_dir = project_root / "batches" / "run-audit"
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    assert (run_dir / "status.toml").exists()
    assert (run_dir / "responses" / "batch-1.raw.json").exists()
    assert (run_dir / "responses" / "batch-1.normalized.json").exists()
    assert results["translated_units"][0]["dest"] == "Bonjour"


def test_runner_preserves_batch_rows_across_repeated_plan_runs(translator_home: Path) -> None:
    plan, project_root = _seeded_plan(translator_home)
    runner = _runner(plan, _KnownTranslationClient("Bonjour"))

    asyncio.run(runner.run("run-one"))
    asyncio.run(runner.run("run-two"))

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    rows = conn.execute(
        """
        SELECT run_id, batch_id, status
        FROM batches
        WHERE batch_id = 'batch-1'
        ORDER BY run_id
        """
    ).fetchall()
    conn.close()

    assert rows == [("run-one", "batch-1", "complete"), ("run-two", "batch-1", "complete")]


def test_retry_success_marks_batch_complete(translator_home: Path) -> None:
    from bgs_translator.core.event_publisher import reset_publishers_for_tests
    from bgs_translator.core.memory import fetch_events_for_run

    reset_publishers_for_tests()
    plan, project_root = _seeded_plan(translator_home)
    client = _RetryThenSuccessClient()
    runner = _runner(plan, client, max_retries=1)

    result = asyncio.run(runner.run("run-retry-success"))

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    try:
        row = conn.execute(
            "SELECT status, retry_count FROM batches WHERE run_id = ? AND batch_id = ?",
            ("run-retry-success", "batch-1"),
        ).fetchone()
        events = fetch_events_for_run(conn, "run-retry-success", 0)
    finally:
        conn.close()
    event_kinds = [event["kind"] for event in events]

    assert client.calls == 2
    assert result.succeeded == 1
    assert result.retried == 1
    assert result.manual_review == 0
    assert row == ("complete", 1)
    assert "batch.complete" in event_kinds
    assert "batch.failed" not in event_kinds


def test_runner_succeeded_count_only_after_persist(
    translator_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _project_root = _seeded_plan(translator_home)

    def fail_update(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("bgs_translator.pipeline.runner.update_unit_translation", fail_update, raising=False)
    runner = _runner(plan, _KnownTranslationClient("Bonjour"))

    result = asyncio.run(runner.run("run-persist-fails"))

    assert result.succeeded == 0
    assert result.manual_review == 1


def test_openrouter_cost_exact_when_response_has_cost(
    translator_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _project_root = _seeded_plan(translator_home)
    client = _openrouter_client(monkeypatch, cost=0.005)
    runner = _runner(plan, client)

    result = asyncio.run(runner.run("run-cost-exact"))
    raw = json.loads(
        (translator_home / "translator" / "projects" / "demo" / "batches" / "run-cost-exact" / "responses" / "batch-1.raw.json").read_text(
            encoding="utf-8"
        )
    )

    assert result.cost_usd == 0.005
    assert result.cost_exact is True
    assert raw["id"] == "chat_2"
    assert raw["usage"]["cost"] == 0.005


def test_openrouter_cost_inexact_without_cost_field(
    translator_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _project_root = _seeded_plan(translator_home)
    client = _openrouter_client(monkeypatch, cost=None)
    pricing = Pricing(
        providers={
            "openai-compat": {
                "openrouter/mock": ModelPrice(input_per_1m=100.0, output_per_1m=200.0)
            }
        }
    )
    runner = _runner(plan, client, pricing=pricing)

    result = asyncio.run(runner.run("run-cost-estimated"))

    assert result.cost_usd == pytest.approx((9 * 100.0 + 10 * 200.0) / 1_000_000)
    assert result.cost_exact is False


def _seeded_plan(translator_home: Path) -> tuple[BatchPlan, Path]:
    project_root = translator_home / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", "Hello")])
    row = conn.execute(
        """
        SELECT plugin, formid, formid_sanitized, edid, signature, field,
               source, index_n, index_max, list_index, strid
        FROM units
        """
    ).fetchone()
    unit = TranslationUnit(
        plugin=str(row[0]),
        formid=int(row[1]),
        formid_sanitized=int(row[2]),
        edid=str(row[3]),
        signature=str(row[4]),
        field=str(row[5]),
        source=str(row[6]),
        index_n=int(row[7]),
        index_max=int(row[8]),
        list_index=int(row[9]),
        strid=int(row[10]),
    )
    batch = Batch("batch-1", [build_masked_unit(unit)], None, [], [])
    plan = BatchPlan("plan-1", "demo", "mock-profile", "zh-cn", "dialogue", [batch], 1, 10, 10, 0.0, "system")
    return plan, project_root


def _runner(
    plan: BatchPlan,
    client: Any,
    *,
    pricing: Pricing | None = None,
    max_retries: int = 2,
) -> BatchRunner:
    profile = getattr(client, "profile", _KnownTranslationClient.profile)
    return BatchRunner(
        plan,
        client,
        RateTracker(profile),
        CostTracker(profile, pricing=pricing),
        max_retries=max_retries,
    )


def _openrouter_client(monkeypatch: pytest.MonkeyPatch, *, cost: float | None) -> Any:
    class FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            del kwargs
            usage = SimpleNamespace(prompt_tokens=9, completion_tokens=10, total_tokens=19)
            if cost is not None:
                usage.cost = cost
            return SimpleNamespace(
                id="chat_2",
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"items": {"I1": "Bonjour"}})))],
                usage=usage,
            )

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            del kwargs
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    import bgs_translator.pipeline.clients.openai_compat_cc as module

    monkeypatch.setattr(module, "resolve_api_key", lambda profile: "sk-test")
    profile = ProviderProfile(
        name="openrouter",
        sdk_kind="openai-compat",
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/mock",
        api_key_env="BGS_TRANSLATOR_KEY_OPENROUTER",
        json_mode="json_schema",
        require_parameters=True,
    )
    return module.OpenAICompatChatCompletionsClient(profile)
