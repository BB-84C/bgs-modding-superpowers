"""Regression tests for run/batch persistence and GUI events."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from bgs_translator.config.pricing import ModelPrice, Pricing
from bgs_translator.config.profiles import ProviderProfile
from bgs_translator.core import event_queue
from bgs_translator.core.memory import insert_units, open_memory_db
from bgs_translator.observability.cost_tracker import CostTracker
from bgs_translator.observability.rate_tracker import RateTracker
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch, BatchPlan
from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.pipeline.runner import BatchRunner


class _TwoBatchClient:
    profile = ProviderProfile(
        name="mock-profile",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_TEST",
        max_concurrency=2,
    )

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del system_prompt
        await asyncio.sleep(0)
        return LLMResponse(
            {f"I{index}": f"译文-{batch.batch_id}-{index}" for index, _ in enumerate(batch.items, 1)},
            TokenUsage(input_tokens=11, output_tokens=7, total_tokens=18),
            cost_usd=0.0125,
            cost_exact=True,
            via="synthetic",
        )

    async def aclose(self) -> None:
        pass


def test_runner_persists_runs_batches_and_emits_gui_events(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    bridge = event_queue.EventQueueBridge()
    monkeypatch.setattr(event_queue, "_singleton", bridge)
    plan, project_root = _seeded_two_batch_plan(tmp_path)
    runner = _runner(plan)

    result = asyncio.run(runner.run("run-gui-events"))
    events = bridge.drain()

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    run_row = conn.execute(
        """
        SELECT status, batches_total, cost_total_usd, cost_exact
        FROM runs
        WHERE run_id = ?
        """,
        ("run-gui-events",),
    ).fetchone()
    batch_rows = conn.execute(
        """
        SELECT batch_id, status, tokens_in, tokens_out, cost_usd
        FROM batches
        ORDER BY batch_id
        """
    ).fetchall()

    assert result.succeeded == 2
    assert run_row == ("complete", 2, 0.025, 1)
    assert batch_rows == [
        ("batch-1", "complete", 11, 7, 0.0125),
        ("batch-2", "complete", 11, 7, 0.0125),
    ]
    assert _event_kinds(events) == [
        "run.start",
        "batch.start",
        "batch.start",
        "batch.progress",
        "batch.complete",
        "cost.update",
        "batch.progress",
        "batch.complete",
        "cost.update",
        "run.complete",
    ]
    assert events[0].payload == {
        "run_id": "run-gui-events",
        "plan_id": "plan-2batch",
        "batches_total": 2,
        "item_count_total": 2,
    }
    assert [event.payload["cost_total_usd"] for event in events if event.kind == "cost.update"] == [
        0.0125,
        0.025,
    ]


def _seeded_two_batch_plan(translator_home: Path) -> tuple[BatchPlan, Path]:
    project_root = translator_home / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    units = [
        TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", "Hello"),
        TranslationUnit("A.esp", 2, 2, "B", "ARMO", "FULL", "Goodbye"),
    ]
    insert_units(conn, units)
    rows = conn.execute(
        """
        SELECT plugin, formid, formid_sanitized, edid, signature, field,
               source, index_n, index_max, list_index, strid
        FROM units
        ORDER BY formid
        """
    ).fetchall()
    masked_units = [
        build_masked_unit(
            TranslationUnit(
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
        )
        for row in rows
    ]
    batches = [
        Batch("batch-1", [masked_units[0]], None, [], []),
        Batch("batch-2", [masked_units[1]], None, [], []),
    ]
    return (
        BatchPlan("plan-2batch", "demo", "mock-profile", "zh-cn", "dialogue", batches, 2, 20, 20, 0.0, "system"),
        project_root,
    )


def _runner(plan: BatchPlan) -> BatchRunner:
    client = _TwoBatchClient()
    pricing = Pricing(
        providers={"openai": {"gpt-5-mini": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}}
    )
    return BatchRunner(plan, client, RateTracker(client.profile), CostTracker(client.profile, pricing=pricing))


def _event_kinds(events: list[event_queue.GuiEvent]) -> list[str]:
    return [event.kind for event in events]
