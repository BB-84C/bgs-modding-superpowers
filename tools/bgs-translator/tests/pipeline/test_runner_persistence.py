"""Regression tests for run/batch persistence and GUI events."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

from bgs_translator.config.pricing import ModelPrice, Pricing
from bgs_translator.config.profiles import ProviderProfile
from bgs_translator.core import event_queue
from bgs_translator.core.event_publisher import reset_publishers_for_tests
from bgs_translator.core.memory import fetch_events_for_run, insert_units, open_memory_db
from bgs_translator.observability.cost_tracker import CostTracker
from bgs_translator.observability.rate_tracker import RateTracker
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch, BatchPlan
from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.pipeline.runner import BatchRunner, PreviewAbandoned


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


class _FailingClient(_TwoBatchClient):
    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del batch, system_prompt
        raise RuntimeError("prompt preview required but GUI is unreachable")


class _PreviewUnavailableClient(_TwoBatchClient):
    stop_run_on_abandon = True

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del batch, system_prompt
        raise PreviewAbandoned("prompt preview required but GUI is unreachable")


class _ApproveAllThenParallelClient(_TwoBatchClient):
    stop_run_on_abandon = True

    def __init__(self) -> None:
        self.calls = 0
        self.active = 0
        self.max_active = 0

    @property
    def allow_parallel_batches(self) -> bool:
        return self.calls >= 1

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del system_prompt
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return LLMResponse(
            {f"I{index}": f"译文-{batch.batch_id}-{index}" for index, _ in enumerate(batch.items, 1)},
            TokenUsage(input_tokens=11, output_tokens=7, total_tokens=18),
            cost_usd=0.0125,
            cost_exact=True,
            via="synthetic",
        )


class _ApproveAllPreviewGateClient(_TwoBatchClient):
    stop_run_on_abandon = True

    def __init__(self) -> None:
        self.calls = 0
        self.preview_calls = 0
        self.active = 0
        self.max_active = 0
        self.second_started = asyncio.Event()

    @property
    def allow_parallel_batches(self) -> bool:
        return self.preview_calls >= 1

    async def preview_batch(self, batch: Batch, system_prompt: str) -> dict[str, str]:
        del batch
        self.preview_calls += 1
        return {"op": "approve_all", "prompt": system_prompt}

    async def translate_preapproved_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        del system_prompt
        return await self._translate(batch)

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        decision = await self.preview_batch(batch, system_prompt)
        del decision
        return await self._translate(batch)

    async def _translate(self, batch: Batch) -> LLMResponse:
        self.calls += 1
        call_number = self.calls
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if call_number == 1:
            await asyncio.wait_for(self.second_started.wait(), timeout=1.0)
        else:
            self.second_started.set()
        await asyncio.sleep(0.01)
        self.active -= 1
        return LLMResponse(
            {f"I{index}": f"译文-{batch.batch_id}-{index}" for index, _ in enumerate(batch.items, 1)},
            TokenUsage(input_tokens=11, output_tokens=7, total_tokens=18),
            cost_usd=0.0125,
            cost_exact=True,
            via="synthetic",
        )


def test_runner_persists_runs_batches_and_emits_gui_events(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    plan, project_root = _seeded_two_batch_plan(tmp_path)
    runner = _runner(plan)

    result = asyncio.run(runner.run("run-gui-events"))

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    conn.row_factory = sqlite3.Row
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
    events = fetch_events_for_run(conn, "run-gui-events")

    assert result.succeeded == 2
    assert tuple(run_row) == ("complete", 2, 0.025, 1)
    assert [tuple(row) for row in batch_rows] == [
        ("batch-1", "complete", 11, 7, 0.0125),
        ("batch-2", "complete", 11, 7, 0.0125),
    ]
    assert _event_kinds(events) == [
        "run.start",
        "batch.start",
        "batch.request_sent",
        "batch.start",
        "batch.request_sent",
        "batch.response_received",
        "batch.progress",
        "batch.complete",
        "cost.update",
        "batch.response_received",
        "batch.progress",
        "batch.complete",
        "cost.update",
        "run.complete",
    ]
    assert events[0]["payload"] == {
        "run_id": "run-gui-events",
        "plan_id": "plan-2batch",
        "batches_total": 2,
        "item_count_total": 2,
    }
    assert [event["payload"]["cost_total_usd"] for event in events if event["kind"] == "cost.update"] == [
        0.0125,
        0.025,
    ]


def test_runner_emits_one_progress_event_per_batch(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    plan = _seeded_one_batch_plan(tmp_path, unit_count=3)
    runner = _runner(plan)

    result = asyncio.run(runner.run("run-progress-coalesced"))
    with open_memory_db(tmp_path / "translator" / "projects" / "demo") as conn:
        progress_events = [
            event
            for event in fetch_events_for_run(conn, "run-progress-coalesced")
            if event["kind"] == "batch.progress"
        ]

    assert result.succeeded == 3
    assert len(progress_events) == 1
    assert progress_events[0]["payload"]["done"] == 3
    assert progress_events[0]["payload"]["total"] == 3


def test_runner_marks_batch_failed_when_client_raises(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    plan = _seeded_one_batch_plan(tmp_path, unit_count=3)
    client = _FailingClient()
    pricing = Pricing(
        providers={"openai": {"gpt-5-mini": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}}
    )
    runner = BatchRunner(plan, client, RateTracker(client.profile), CostTracker(client.profile, pricing=pricing))

    result = asyncio.run(runner.run("run-client-raises"))
    with open_memory_db(tmp_path / "translator" / "projects" / "demo") as conn:
        batch_row = conn.execute(
            "SELECT status, completed_at, tokens_in, tokens_out, cost_usd FROM batches WHERE run_id = ?",
            ("run-client-raises",),
        ).fetchone()
        run_row = conn.execute(
            "SELECT status, completed_at, cost_total_usd FROM runs WHERE run_id = ?",
            ("run-client-raises",),
        ).fetchone()
        event_kinds = [event["kind"] for event in fetch_events_for_run(conn, "run-client-raises")]

    assert result.succeeded == 0
    assert result.manual_review == 3
    assert batch_row[0] == "failed"
    assert batch_row[1] is not None
    assert batch_row[2:] == (None, None, None)
    assert run_row[0] == "failed"
    assert run_row[1] is not None
    assert run_row[2] == 0.0
    assert event_kinds == [
        "run.start",
        "batch.start",
        "batch.request_sent",
        "batch.failed",
        "cost.update",
        "run.failed",
    ]


def test_runner_abandons_when_preview_is_unavailable_before_ai(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    plan, project_root = _seeded_two_batch_plan(tmp_path)
    client = _PreviewUnavailableClient()
    pricing = Pricing(
        providers={"openai": {"gpt-5-mini": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}}
    )
    runner = BatchRunner(plan, client, RateTracker(client.profile), CostTracker(client.profile, pricing=pricing))

    result = asyncio.run(runner.run("run-preview-abandoned"))
    with open_memory_db(project_root) as conn:
        batch_rows = conn.execute(
            """
            SELECT batch_id, status, completed_at, tokens_in, tokens_out, cost_usd
            FROM batches
            WHERE run_id = ?
            ORDER BY batch_id
            """,
            ("run-preview-abandoned",),
        ).fetchall()
        run_row = conn.execute(
            "SELECT status, completed_at, cost_total_usd FROM runs WHERE run_id = ?",
            ("run-preview-abandoned",),
        ).fetchone()
        event_kinds = [event["kind"] for event in fetch_events_for_run(conn, "run-preview-abandoned")]

    assert result.succeeded == 0
    assert result.manual_review == 0
    assert result.abandoned == 1
    assert [(row[0], row[1], row[3], row[4], row[5]) for row in batch_rows] == [
        ("batch-1", "abandoned", None, None, None)
    ]
    assert batch_rows[0][2] is not None
    assert run_row[0] == "abandoned"
    assert run_row[1] is not None
    assert run_row[2] == 0.0
    assert event_kinds == [
        "run.start",
        "batch.start",
        "batch.request_sent",
        "batch.abandoned",
        "cost.update",
        "run.abandoned",
    ]


def test_runner_restores_batch_parallelism_after_approve_all(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    plan = _seeded_many_batch_plan(tmp_path, batch_count=4)
    client = _ApproveAllThenParallelClient()
    pricing = Pricing(
        providers={"openai": {"gpt-5-mini": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}}
    )
    runner = BatchRunner(plan, client, RateTracker(client.profile), CostTracker(client.profile, pricing=pricing))

    result = asyncio.run(runner.run("run-approve-all-parallel"))

    assert result.succeeded == 4
    assert client.calls == 4
    assert client.max_active == client.profile.max_concurrency


def test_runner_starts_parallel_window_immediately_after_approve_all(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    plan = _seeded_many_batch_plan(tmp_path, batch_count=4)
    client = _ApproveAllPreviewGateClient()
    pricing = Pricing(
        providers={"openai": {"gpt-5-mini": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}}
    )
    runner = BatchRunner(plan, client, RateTracker(client.profile), CostTracker(client.profile, pricing=pricing))

    result = asyncio.run(asyncio.wait_for(runner.run("run-approve-all-immediate"), timeout=2.0))

    assert result.succeeded == 4
    assert client.preview_calls == 1
    assert client.calls == 4
    assert client.max_active == client.profile.max_concurrency


def test_runner_fans_out_translation_to_safe_duplicate_group(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    units = [
        TranslationUnit("A.esp", 1, 1, "WeaponA", "WEAP", "FULL", "Ship"),
        TranslationUnit("A.esp", 2, 2, "WeaponB", "WEAP", "FULL", "Ship"),
        TranslationUnit("A.esp", 3, 3, "MessageA", "MESG", "FULL", "Ship"),
    ]
    insert_units(conn, units)
    conn.close()
    plan = BatchPlan(
        "plan-dupe-fanout",
        "demo",
        "mock-profile",
        "zh-cn",
        "dialogue",
        [Batch("batch-1", [build_masked_unit(units[0])], None, [], [])],
        1,
        20,
        20,
        0.0,
        "system",
    )

    result = asyncio.run(_runner(plan).run("run-dupe-fanout"))

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    rows = conn.execute(
        "SELECT signature, formid, dest, status FROM units ORDER BY formid"
    ).fetchall()
    conn.close()
    assert result.succeeded == 2
    assert rows == [
        ("WEAP", 1, "译文-batch-1-1", "translated"),
        ("WEAP", 2, "译文-batch-1-1", "translated"),
        ("MESG", 3, None, "untranslated"),
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


def _seeded_one_batch_plan(translator_home: Path, *, unit_count: int) -> BatchPlan:
    project_root = translator_home / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    units = [
        TranslationUnit("A.esp", index, index, f"EDID{index}", "QUST", "FULL", f"Source {index}")
        for index in range(1, unit_count + 1)
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
    batches = [Batch("batch-1", masked_units, None, [], [])]
    return BatchPlan("plan-1batch", "demo", "mock-profile", "zh-cn", "dialogue", batches, unit_count, 20, 20, 0.0, "system")


def _seeded_many_batch_plan(translator_home: Path, *, batch_count: int) -> BatchPlan:
    project_root = translator_home / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    units = [
        TranslationUnit("A.esp", index, index, f"EDID{index}", "QUST", "FULL", f"Source {index}")
        for index in range(1, batch_count + 1)
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
    batches = [
        Batch(
            f"batch-{index}",
            [
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
            ],
            None,
            [],
            [],
        )
        for index, row in enumerate(rows, start=1)
    ]
    return BatchPlan(
        "plan-many-batch",
        "demo",
        "mock-profile",
        "zh-cn",
        "dialogue",
        batches,
        batch_count,
        20,
        20,
        0.0,
        "system",
    )


def _runner(plan: BatchPlan) -> BatchRunner:
    client = _TwoBatchClient()
    pricing = Pricing(
        providers={"openai": {"gpt-5-mini": ModelPrice(input_per_1m=1.0, output_per_1m=2.0)}}
    )
    return BatchRunner(plan, client, RateTracker(client.profile), CostTracker(client.profile, pricing=pricing))


def _event_kinds(events: list[event_queue.GuiEvent]) -> list[str]:
    return [event.kind if isinstance(event, event_queue.GuiEvent) else str(event["kind"]) for event in events]
