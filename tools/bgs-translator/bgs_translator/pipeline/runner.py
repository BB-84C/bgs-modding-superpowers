"""Batch lifecycle, cancellation, retry, and event emission ownership."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import tomli_w

from bgs_translator.config import paths
from bgs_translator.config.pricing import estimate_cost
from bgs_translator.core import event_queue as gui_event_queue
from bgs_translator.core.event_publisher import get_publisher
from bgs_translator.core.memory import (
    insert_batch,
    insert_run,
    update_batch,
    update_run,
    update_unit_translation,
)
from bgs_translator.observability.cost_tracker import CostTracker
from bgs_translator.observability.rate_tracker import RateTracker
from bgs_translator.pipeline.batcher import Batch, BatchPlan, estimate_tokens
from bgs_translator.pipeline.clients.base import LLMClient, LLMResponse
from bgs_translator.pipeline.mask import unmask_dest
from bgs_translator.pipeline.validator import ValidationFailure, validate_item

log = logging.getLogger(__name__)


@dataclass
class BatchEvent:
    """Progress event for GUI/CLI consumption."""

    run_id: str
    batch_id: str
    kind: Literal["start", "in_flight", "complete", "failed", "cancelled", "abandoned", "rate_limited"]
    timestamp: datetime
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Final batch run summary."""

    run_id: str
    total_items: int
    succeeded: int
    retried: int
    manual_review: int
    cancelled: int
    abandoned: int
    cost_usd: float
    cost_exact: bool


@dataclass
class TranslatedUnit:
    """One validated translated unit plus persistence provenance."""

    row_id: str
    unit: Any
    dest: str
    via_llm: bool
    profile_used: str | None
    sdk_via: str
    cost_estimate_usd: float | None
    cost_exact: bool
    retry_count: int
    last_batch_id: str


@dataclass
class _BatchOutcome:
    succeeded: int = 0
    retried: int = 0
    manual_review: int = 0
    cancelled: int = 0
    abandoned: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    cost_exact: bool = False
    failures: list[ValidationFailure] = field(default_factory=list)
    translated_units: list[TranslatedUnit] = field(default_factory=list)


class PreviewAbandoned(RuntimeError):
    """A batch lost its preview before calling AI and must be started over."""


class BatchRunner:
    """Runs a BatchPlan to completion. Owns the asyncio lifecycle."""

    def __init__(
        self,
        plan: BatchPlan,
        client: LLMClient,
        rate_tracker: RateTracker,
        cost_tracker: CostTracker,
        *,
        max_retries: int = 2,
    ) -> None:
        self.plan = plan
        self.client = client
        self.rate_tracker = rate_tracker
        self.cost_tracker = cost_tracker
        self.max_retries = max_retries
        self._publisher = get_publisher(plan.project)

    async def run(
        self,
        run_id: str,
        event_queue: asyncio.Queue[BatchEvent] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> RunResult:
        """Execute all batches concurrently up to profile.max_concurrency."""

        run_dir = paths.project_root(self.plan.project) / "batches" / run_id
        self._prepare_run_dir(run_dir)
        memory_path = paths.project_root(self.plan.project) / "memory" / "memory.sqlite"
        memory_conn = sqlite3.connect(memory_path) if memory_path.exists() else None
        started_at = datetime.now(UTC).isoformat()
        if memory_conn is not None:
            insert_run(
                memory_conn,
                run_id,
                self.plan.plan_id,
                started_at,
                len(self.plan.batches),
                project=self.plan.project,
            )
        self._emit_gui_event(
            "run.start",
            run_id=run_id,
            payload={
                "run_id": run_id,
                "plan_id": self.plan.plan_id,
                "batches_total": len(self.plan.batches),
                "item_count_total": self.plan.total_items,
            },
        )
        try:
            semaphore = asyncio.Semaphore(max(1, self.rate_tracker.profile.max_concurrency))
            if getattr(self.client, "stop_run_on_abandon", False):
                outcomes = await self._run_preview_guarded_batches(
                    run_id,
                    run_dir,
                    semaphore,
                    event_queue,
                    cancel_event,
                    memory_conn,
                )
            else:
                outcomes = await asyncio.gather(
                    *(
                        self._run_batch(
                            run_id, run_dir, batch, semaphore, event_queue, cancel_event, memory_conn
                        )
                        for batch in self.plan.batches
                    )
                )
        except Exception:
            finished_at = datetime.now(UTC).isoformat()
            if memory_conn is not None:
                update_run(
                    memory_conn,
                    run_id,
                    status="failed",
                    finished_at=finished_at,
                    cost_total_usd=self.cost_tracker.estimated_total(),
                    cost_exact=self.cost_tracker.cost_exact,
                    succeeded=0,
                    retried=0,
                    manual_review=0,
                    cancelled=0,
                )
            self._emit_gui_event(
                "run.failed",
                run_id=run_id,
                payload={
                    "run_id": run_id,
                    "plan_id": self.plan.plan_id,
                    "cost_total_usd": self.cost_tracker.estimated_total(),
                    "cost_exact": self.cost_tracker.cost_exact,
                },
            )
            raise
        finally:
            if memory_conn is not None:
                memory_conn.close()
        result = RunResult(
            run_id=run_id,
            total_items=self.plan.total_items,
            succeeded=sum(outcome.succeeded for outcome in outcomes),
            retried=sum(outcome.retried for outcome in outcomes),
            manual_review=sum(outcome.manual_review for outcome in outcomes),
            cancelled=sum(outcome.cancelled for outcome in outcomes),
            abandoned=sum(outcome.abandoned for outcome in outcomes),
            cost_usd=self.cost_tracker.estimated_total(),
            cost_exact=self.cost_tracker.cost_exact,
        )
        run_status = (
            "abandoned"
            if result.abandoned
            else ("failed" if result.manual_review or result.cancelled else "complete")
        )
        finished_at = datetime.now(UTC).isoformat()
        memory_conn = sqlite3.connect(memory_path) if memory_path.exists() else None
        try:
            if memory_conn is not None:
                update_run(
                    memory_conn,
                    run_id,
                    status=run_status,
                    finished_at=finished_at,
                    cost_total_usd=result.cost_usd,
                    cost_exact=result.cost_exact,
                    succeeded=result.succeeded,
                    retried=result.retried,
                    manual_review=result.manual_review,
                    cancelled=result.cancelled,
                )
        finally:
            if memory_conn is not None:
                memory_conn.close()
        self._emit_gui_event(
            "run.complete"
            if run_status == "complete"
            else ("run.abandoned" if run_status == "abandoned" else "run.failed"),
            run_id=run_id,
            payload={
                "run_id": run_id,
                "plan_id": self.plan.plan_id,
                "total_items": result.total_items,
                "succeeded": result.succeeded,
                "retried": result.retried,
                "manual_review": result.manual_review,
                "cancelled": result.cancelled,
                "abandoned": result.abandoned,
                "cost_total_usd": result.cost_usd,
                "cost_exact": result.cost_exact,
            },
        )
        self._write_json(
            run_dir / "results.json",
            {
                "summary": asdict(result),
                "translated_units": _to_jsonable(
                    [unit for outcome in outcomes for unit in outcome.translated_units]
                ),
            },
        )
        (run_dir / "status.toml").write_text(tomli_w.dumps(asdict(result)), encoding="utf-8")
        failure_path = run_dir / "validator-failures.jsonl"
        failures = [failure for outcome in outcomes for failure in outcome.failures]
        failure_path.write_text(
            "\n".join(json.dumps(failure.model_dump(), ensure_ascii=False) for failure in failures),
            encoding="utf-8",
        )
        return result

    async def _run_preview_guarded_batches(
        self,
        run_id: str,
        run_dir: Path,
        semaphore: asyncio.Semaphore,
        event_queue: asyncio.Queue[BatchEvent] | None,
        cancel_event: asyncio.Event | None,
        memory_conn: sqlite3.Connection | None,
    ) -> list[_BatchOutcome]:
        outcomes: list[_BatchOutcome] = []
        preview_batch = getattr(self.client, "preview_batch", None)
        translate_preapproved = getattr(self.client, "translate_preapproved_batch", None)
        if not callable(preview_batch) or not callable(translate_preapproved):
            return await self._run_preview_guarded_batches_legacy(
                run_id,
                run_dir,
                semaphore,
                event_queue,
                cancel_event,
                memory_conn,
            )

        batch_index = 0
        while batch_index < len(self.plan.batches):
            batch = self.plan.batches[batch_index]
            try:
                decision = await preview_batch(batch, self._system_prompt(batch))
            except PreviewAbandoned as exc:
                outcomes.append(
                    await self._record_preview_abandoned_batch(
                        run_id,
                        batch,
                        event_queue,
                        memory_conn,
                        str(exc),
                    )
                )
                break
            if not isinstance(decision, dict):
                decision = {"op": "approved", "prompt": self._system_prompt(batch)}
            response = decision.get("response")
            prompt = str(decision.get("prompt", self._system_prompt(batch)))
            op = str(decision.get("op", "approved"))
            if op == "approve_all":
                remaining = self.plan.batches[batch_index:]
                outcomes.extend(
                    await asyncio.gather(
                        *(
                            self._run_batch(
                                run_id,
                                run_dir,
                                remaining_batch,
                                semaphore,
                                event_queue,
                                cancel_event,
                                memory_conn,
                                preapproved_prompt=prompt
                                if remaining_batch.batch_id == batch.batch_id
                                else self._system_prompt(remaining_batch),
                            )
                            for remaining_batch in remaining
                        )
                    )
                )
                break
            outcome = await self._run_batch(
                run_id,
                run_dir,
                batch,
                semaphore,
                event_queue,
                cancel_event,
                memory_conn,
                preapproved_prompt=prompt,
                preapproved_response=response if isinstance(response, LLMResponse) else None,
            )
            outcomes.append(outcome)
            batch_index += 1
            if outcome.abandoned or outcome.cancelled:
                break
        return outcomes

    async def _run_preview_guarded_batches_legacy(
        self,
        run_id: str,
        run_dir: Path,
        semaphore: asyncio.Semaphore,
        event_queue: asyncio.Queue[BatchEvent] | None,
        cancel_event: asyncio.Event | None,
        memory_conn: sqlite3.Connection | None,
    ) -> list[_BatchOutcome]:
        outcomes: list[_BatchOutcome] = []
        batch_index = 0
        while batch_index < len(self.plan.batches):
            batch = self.plan.batches[batch_index]
            outcome = await self._run_batch(run_id, run_dir, batch, semaphore, event_queue, cancel_event, memory_conn)
            outcomes.append(outcome)
            batch_index += 1
            if outcome.abandoned or outcome.cancelled:
                break
            if getattr(self.client, "allow_parallel_batches", False) and batch_index < len(self.plan.batches):
                outcomes.extend(
                    await asyncio.gather(
                        *(
                            self._run_batch(
                                run_id,
                                run_dir,
                                remaining,
                                semaphore,
                                event_queue,
                                cancel_event,
                                memory_conn,
                            )
                            for remaining in self.plan.batches[batch_index:]
                        )
                    )
                )
                break
        return outcomes

    async def _record_preview_abandoned_batch(
        self,
        run_id: str,
        batch: Batch,
        event_queue: asyncio.Queue[BatchEvent] | None,
        memory_conn: sqlite3.Connection | None,
        reason: str,
    ) -> _BatchOutcome:
        await self._emit(event_queue, run_id, batch.batch_id, "start")
        started_at = datetime.now(UTC).isoformat()
        if memory_conn is not None:
            insert_batch(
                memory_conn,
                batch.batch_id,
                run_id,
                started_at,
                len(batch.items),
                plan_id=self.plan.plan_id,
                profile_snapshot_json=self._profile_snapshot_json(),
            )
        self._emit_gui_event(
            "batch.start",
            run_id=run_id,
            batch_id=batch.batch_id,
            payload={
                "batch_id": batch.batch_id,
                "run_id": run_id,
                "item_count": len(batch.items),
                "total": len(batch.items),
                "profile": self.rate_tracker.profile.name,
                "model": self.rate_tracker.profile.model,
            },
        )
        failure = ValidationFailure(
            item_id=batch.batch_id,
            gate="prompt_preview",
            reason=reason,
            soft=False,
        )
        finished_at = datetime.now(UTC).isoformat()
        if memory_conn is not None:
            update_batch(
                memory_conn,
                batch.batch_id,
                run_id=run_id,
                status="abandoned",
                finished_at=finished_at,
                tokens_in=None,
                tokens_out=None,
                cost_usd=None,
            )
        self._emit_gui_event(
            "batch.abandoned",
            run_id=run_id,
            batch_id=batch.batch_id,
            payload={
                "batch_id": batch.batch_id,
                "run_id": run_id,
                "status": "abandoned",
                "item_count": len(batch.items),
                "done": 0,
                "total": len(batch.items),
                "reason": reason,
            },
        )
        self._emit_gui_event(
            "cost.update",
            run_id=run_id,
            batch_id=batch.batch_id,
            payload={
                "run_id": run_id,
                "batch_id": batch.batch_id,
                "cost_total_usd": self.cost_tracker.estimated_total(),
                "cost": self.cost_tracker.estimated_total(),
                "cost_exact": self.cost_tracker.cost_exact,
            },
        )
        await self._emit(
            event_queue,
            run_id,
            batch.batch_id,
            "abandoned",
            {"failures": [failure.model_dump()]},
        )
        return _BatchOutcome(abandoned=len(batch.items), failures=[failure])

    async def _run_batch(
        self,
        run_id: str,
        run_dir: Path,
        batch: Batch,
        semaphore: asyncio.Semaphore,
        event_queue: asyncio.Queue[BatchEvent] | None,
        cancel_event: asyncio.Event | None,
        memory_conn: sqlite3.Connection | None,
        *,
        preapproved_prompt: str | None = None,
        preapproved_response: LLMResponse | None = None,
    ) -> _BatchOutcome:
        async with semaphore:
            if self._cancel_requested(run_dir, cancel_event):
                await self._emit(event_queue, run_id, batch.batch_id, "cancelled")
                return _BatchOutcome(cancelled=len(batch.items))
            await self._emit(event_queue, run_id, batch.batch_id, "start")
            started_at = datetime.now(UTC).isoformat()
            if memory_conn is not None:
                insert_batch(
                    memory_conn,
                    batch.batch_id,
                    run_id,
                    started_at,
                    len(batch.items),
                    plan_id=self.plan.plan_id,
                    profile_snapshot_json=self._profile_snapshot_json(),
                )
            self._emit_gui_event(
                "batch.start",
                run_id=run_id,
                batch_id=batch.batch_id,
                payload={
                    "batch_id": batch.batch_id,
                    "run_id": run_id,
                    "item_count": len(batch.items),
                    "total": len(batch.items),
                    "profile": self.rate_tracker.profile.name,
                    "model": self.rate_tracker.profile.model,
                },
            )
            est_tokens = estimate_tokens(self._system_prompt(batch)) + estimate_tokens(
                "\n".join(item.source_masked for item in batch.items)
            )
            await self.rate_tracker.acquire(est_tokens)
            if self.cost_tracker.would_exceed_cap(self._batch_estimated_cost()):
                await self._emit(event_queue, run_id, batch.batch_id, "cancelled", {"reason": "cost_cap"})
                finished_at = datetime.now(UTC).isoformat()
                if memory_conn is not None:
                    update_batch(
                        memory_conn,
                        batch.batch_id,
                        run_id=run_id,
                        status="cancelled",
                        finished_at=finished_at,
                        tokens_in=None,
                        tokens_out=None,
                        cost_usd=None,
                    )
                self._emit_gui_event(
                    "batch.failed",
                    run_id=run_id,
                    batch_id=batch.batch_id,
                    payload={"batch_id": batch.batch_id, "run_id": run_id, "reason": "cost_cap"},
                )
                return _BatchOutcome(cancelled=len(batch.items))
            outcome = await self._attempt_batch(
                run_id,
                run_dir,
                batch,
                cancel_event,
                memory_conn,
                preapproved_prompt=preapproved_prompt,
                preapproved_response=preapproved_response,
            )
            if outcome.succeeded:
                self._emit_gui_event(
                    "batch.progress",
                    run_id=run_id,
                    batch_id=batch.batch_id,
                    payload={
                        "batch_id": batch.batch_id,
                        "items_done": outcome.succeeded,
                        "items_total": len(batch.items),
                        "done": outcome.succeeded,
                        "total": len(batch.items),
                    },
                )
            batch_status = self._batch_status(outcome)
            finished_at = datetime.now(UTC).isoformat()
            if memory_conn is not None:
                update_batch(
                    memory_conn,
                    batch.batch_id,
                    run_id=run_id,
                    status=batch_status,
                    finished_at=finished_at,
                    tokens_in=outcome.tokens_in,
                    tokens_out=outcome.tokens_out,
                    cost_usd=outcome.cost_usd,
                    cost_exact=outcome.cost_exact,
                    retry_count=outcome.retried,
                )
            self._emit_gui_event(
                "batch.complete"
                if batch_status == "complete"
                else ("batch.abandoned" if batch_status == "abandoned" else "batch.failed"),
                run_id=run_id,
                batch_id=batch.batch_id,
                payload={
                    "batch_id": batch.batch_id,
                    "run_id": run_id,
                    "status": batch_status,
                    "item_count": len(batch.items),
                    "done": outcome.succeeded,
                    "total": len(batch.items),
                    "tokens_in": outcome.tokens_in,
                    "tokens_out": outcome.tokens_out,
                    "cost_usd": outcome.cost_usd,
                    "cost": outcome.cost_usd,
                    "cost_exact": outcome.cost_exact,
                    "retry_count": outcome.retried,
                },
            )
            self._emit_gui_event(
                "cost.update",
                run_id=run_id,
                batch_id=batch.batch_id,
                payload={
                    "run_id": run_id,
                    "batch_id": batch.batch_id,
                    "cost_total_usd": self.cost_tracker.estimated_total(),
                    "cost": self.cost_tracker.estimated_total(),
                    "cost_exact": self.cost_tracker.cost_exact,
                },
            )
            await self._emit(
                event_queue,
                run_id,
                batch.batch_id,
                "abandoned"
                if outcome.abandoned
                else ("cancelled" if outcome.cancelled else ("failed" if batch_status == "failed" else "complete")),
                asdict(outcome) | {"failures": [failure.model_dump() for failure in outcome.failures]},
            )
            return outcome

    async def _attempt_batch(
        self,
        run_id: str,
        run_dir: Path,
        batch: Batch,
        cancel_event: asyncio.Event | None,
        memory_conn: sqlite3.Connection | None,
        *,
        preapproved_prompt: str | None = None,
        preapproved_response: LLMResponse | None = None,
    ) -> _BatchOutcome:
        failures: list[ValidationFailure] = []
        for attempt in range(self.max_retries + 1):
            if self._cancel_requested(run_dir, cancel_event):
                return _BatchOutcome(cancelled=len(batch.items), failures=failures)
            request_started_at: datetime | None = None
            try:
                if preapproved_response is not None and attempt == 0:
                    response = preapproved_response
                elif preapproved_prompt is not None:
                    translate_preapproved = getattr(self.client, "translate_preapproved_batch", None)
                    request_started_at = datetime.now(UTC)
                    self._emit_gui_event(
                        "batch.request_sent",
                        run_id=run_id,
                        batch_id=batch.batch_id,
                        payload={
                            "batch_id": batch.batch_id,
                            "run_id": run_id,
                            "attempt": attempt + 1,
                            "total": len(batch.items),
                            "profile": self.rate_tracker.profile.name,
                            "model": self.rate_tracker.profile.model,
                        },
                    )
                    if callable(translate_preapproved):
                        response = await translate_preapproved(batch, preapproved_prompt)
                    else:
                        response = await self.client.translate_batch(batch, preapproved_prompt)
                else:
                    request_started_at = datetime.now(UTC)
                    self._emit_gui_event(
                        "batch.request_sent",
                        run_id=run_id,
                        batch_id=batch.batch_id,
                        payload={
                            "batch_id": batch.batch_id,
                            "run_id": run_id,
                            "attempt": attempt + 1,
                            "total": len(batch.items),
                            "profile": self.rate_tracker.profile.name,
                            "model": self.rate_tracker.profile.model,
                        },
                    )
                    response = await self.client.translate_batch(batch, self._system_prompt(batch))
            except asyncio.CancelledError:
                return _BatchOutcome(cancelled=len(batch.items), failures=failures)
            except PreviewAbandoned as exc:
                failures.append(
                    ValidationFailure(
                        item_id=batch.batch_id,
                        gate="prompt_preview",
                        reason=str(exc),
                        soft=False,
                    )
                )
                return _BatchOutcome(abandoned=len(batch.items), failures=failures)
            except Exception as exc:
                log.exception("Batch %s failed before an LLM response was persisted", batch.batch_id)
                failures.append(
                    ValidationFailure(
                        item_id=batch.batch_id,
                        gate="llm_request",
                        reason=str(exc),
                        soft=False,
                    )
                )
                return _BatchOutcome(
                    manual_review=len(batch.items),
                    retried=attempt,
                    failures=failures,
                )
            elapsed_seconds = (
                (datetime.now(UTC) - request_started_at).total_seconds()
                if request_started_at is not None
                else 0.0
            )
            self._emit_gui_event(
                "batch.response_received",
                run_id=run_id,
                batch_id=batch.batch_id,
                payload={
                    "batch_id": batch.batch_id,
                    "run_id": run_id,
                    "attempt": attempt + 1,
                    "total": len(batch.items),
                    "elapsed_seconds": round(elapsed_seconds, 1),
                    "tokens_in": response.usage.input_tokens,
                    "tokens_out": response.usage.output_tokens,
                    "cost_usd": response.cost_usd,
                    "cost_exact": response.cost_exact,
                },
            )
            self.cost_tracker.record(response.usage, response.cost_usd if response.cost_exact else None)
            self._persist_response(run_dir, batch.batch_id, attempt, response)
            hard_failures = self._validate_response(batch, response)
            failures.extend(hard_failures)
            if not hard_failures:
                return self._persist_translated_units(memory_conn, run_id, batch, response, attempt, failures)
        return _BatchOutcome(
            manual_review=len(batch.items),
            retried=self.max_retries,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=self._batch_cost_usd(response),
            cost_exact=response.cost_exact,
            failures=failures,
        )

    def _persist_translated_units(
        self,
        memory_conn: sqlite3.Connection | None,
        run_id: str,
        batch: Batch,
        response: LLMResponse,
        attempt: int,
        failures: list[ValidationFailure],
    ) -> _BatchOutcome:
        translated_units: list[TranslatedUnit] = []
        persist_failures: list[ValidationFailure] = []
        item_cost = self._item_cost_usd(response, len(batch.items))
        profile_used = _client_profile_name(self.client) or self.plan.profile_name
        for index, item in enumerate(batch.items, start=1):
            item_id = f"I{index}"
            dest_masked = response.items.get(item_id, "")
            dest = unmask_dest(dest_masked, item.mask_map, item.mcm_token_prefix)
            row_id = self._row_id_for_item(memory_conn, item.unit)
            row_ids = self._row_ids_for_item_group(memory_conn, item.unit)
            if row_id is not None and row_id not in row_ids:
                row_ids.insert(0, row_id)
            if not row_ids and row_id is not None:
                row_ids = [row_id]
            row_cost = item_cost / max(1, len(row_ids)) if item_cost is not None else None
            persisted_any = False
            if memory_conn is not None and row_ids:
                try:
                    for target_row_id in row_ids:
                        update_unit_translation(
                            memory_conn,
                            row_id=target_row_id,
                            dest=dest,
                            status="translated",
                            sparams=0,
                            via_llm=True,
                            profile_used=profile_used,
                            sdk_via=response.via,
                            cost_estimate_usd=row_cost,
                            cost_exact=response.cost_exact,
                            retry_count=attempt,
                            last_batch_id=batch.batch_id,
                            last_run_id=run_id,
                        )
                        persisted_any = True
                except (sqlite3.Error, ValueError) as exc:
                    persist_failures.append(
                        ValidationFailure(
                            item_id=item_id,
                            gate="persistence",
                            reason=str(exc),
                            soft=False,
                        )
                    )
                    continue
            translated_row_ids = row_ids if row_ids else [row_id or ""]
            if not persisted_any and row_id:
                translated_row_ids = [row_id]
            for translated_row_id in translated_row_ids:
                translated_units.append(
                    TranslatedUnit(
                        row_id=translated_row_id,
                        unit=item.unit,
                        dest=dest,
                        via_llm=True,
                        profile_used=profile_used,
                        sdk_via=response.via,
                        cost_estimate_usd=row_cost if row_ids else item_cost,
                        cost_exact=response.cost_exact,
                        retry_count=attempt,
                        last_batch_id=batch.batch_id,
                    )
                )
        if persist_failures:
            return _BatchOutcome(
                manual_review=len(persist_failures),
                retried=attempt,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                cost_usd=self._batch_cost_usd(response),
                cost_exact=response.cost_exact,
                failures=failures + persist_failures,
                translated_units=translated_units,
            )
        return _BatchOutcome(
            succeeded=len(translated_units),
            retried=attempt,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=self._batch_cost_usd(response),
            cost_exact=response.cost_exact,
            failures=failures,
            translated_units=translated_units,
        )

    def _validate_response(self, batch: Batch, response: LLMResponse) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        for index, item in enumerate(batch.items, start=1):
            item_id = f"I{index}"
            dest_masked = response.items.get(item_id, "")
            validation = validate_item(item, dest_masked, batch.do_not_translate, ["utf-8"])
            failures.extend(failure for failure in validation.failures if not failure.soft)
            if validation.ok:
                unmask_dest(dest_masked, item.mask_map, item.mcm_token_prefix)
        return failures

    def _row_id_for_item(self, memory_conn: sqlite3.Connection | None, unit: Any) -> str | None:
        row_id = getattr(unit, "row_id", None)
        if isinstance(row_id, str) and row_id:
            return row_id
        if memory_conn is None:
            return None
        row = memory_conn.execute(
            """
            SELECT row_id FROM units
            WHERE plugin = ? AND formid = ? AND signature = ? AND field = ? AND index_n = ?
            """,
            (unit.plugin, unit.formid, unit.signature, unit.field, unit.index_n),
        ).fetchone()
        return None if row is None else str(row[0])

    def _row_ids_for_item_group(self, memory_conn: sqlite3.Connection | None, unit: Any) -> list[str]:
        if memory_conn is None:
            return []
        rows = memory_conn.execute(
            """
            SELECT row_id FROM units
            WHERE source = ? AND signature = ? AND field = ? AND status = 'untranslated'
            ORDER BY signature, field, formid, index_n
            """,
            (unit.source, unit.signature, unit.field),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def _prepare_run_dir(self, run_dir: Path) -> None:
        (run_dir / "responses").mkdir(parents=True, exist_ok=True)
        (run_dir / "retries").mkdir(parents=True, exist_ok=True)
        self._write_json(run_dir / "plan.json", _to_jsonable(self.plan))
        (run_dir / "system-prompt.md").write_text(self.plan.sample_system_prompt, encoding="utf-8")

    @staticmethod
    def _cancel_requested(run_dir: Path, cancel_event: asyncio.Event | None) -> bool:
        return bool(cancel_event is not None and cancel_event.is_set()) or (run_dir / "cancel.requested").exists()

    def _persist_response(self, run_dir: Path, batch_id: str, attempt: int, response: LLMResponse) -> None:
        response_dir = run_dir / "responses"
        retry_dir = run_dir / "retries"
        payload = _to_jsonable(response)
        if attempt == 0:
            self._write_json(response_dir / f"{batch_id}.raw.json", _raw_response_payload(response, payload))
            self._write_json(response_dir / f"{batch_id}.normalized.json", payload)
        else:
            self._write_json(retry_dir / f"{batch_id}.attempt-{attempt}.json", payload)

    def _item_cost_usd(self, response: LLMResponse, item_count: int) -> float | None:
        divisor = max(1, item_count)
        if response.cost_usd is not None:
            return response.cost_usd / divisor
        estimated = estimate_cost(
            self.cost_tracker.pricing,
            self.cost_tracker.profile.sdk_kind,
            self.cost_tracker.profile.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.usage.cached_tokens,
        )
        return None if estimated is None else estimated / divisor

    def _batch_estimated_cost(self) -> float:
        if not self.plan.batches:
            return 0.0
        return self.plan.est_cost_usd / len(self.plan.batches)

    def _batch_cost_usd(self, response: LLMResponse) -> float | None:
        if response.cost_usd is not None:
            return response.cost_usd
        return estimate_cost(
            self.cost_tracker.pricing,
            self.cost_tracker.profile.sdk_kind,
            self.cost_tracker.profile.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.usage.cached_tokens,
        )

    def _batch_status(self, outcome: _BatchOutcome) -> str:
        if outcome.cancelled:
            return "cancelled"
        if outcome.abandoned:
            return "abandoned"
        if outcome.manual_review:
            return "failed"
        if outcome.succeeded:
            return "complete"
        if outcome.failures:
            return "failed"
        return "complete"

    def _profile_snapshot_json(self) -> str:
        profile = self.rate_tracker.profile
        return json.dumps(
            {
                "name": profile.name,
                "profile": profile.name,
                "sdk_kind": profile.sdk_kind,
                "model": profile.model,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _system_prompt(self, batch: Batch) -> str:
        if batch.system_prompt:
            return batch.system_prompt
        if batch.parent_context_summary:
            return f"{self.plan.sample_system_prompt}\n\n{batch.parent_context_summary}"
        return self.plan.sample_system_prompt

    async def _emit(
        self,
        event_queue: asyncio.Queue[BatchEvent] | None,
        run_id: str,
        batch_id: str,
        kind: Literal["start", "in_flight", "complete", "failed", "cancelled", "abandoned", "rate_limited"],
        detail: dict[str, Any] | None = None,
    ) -> None:
        if event_queue is None:
            return
        await event_queue.put(
            BatchEvent(
                run_id=run_id,
                batch_id=batch_id,
                kind=kind,
                timestamp=datetime.now(UTC),
                detail=detail or {},
            )
        )

    def _emit_gui_event(
        self,
        kind: gui_event_queue.GuiEventKind,
        *,
        run_id: str | None = None,
        batch_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            self._publisher.emit(
                gui_event_queue.GuiEvent(
                    kind=kind,
                    run_id=run_id,
                    batch_id=batch_id,
                    payload=payload or {},
                )
            )
        except Exception as exc:  # pragma: no cover - defensive GUI bridge isolation
            log.warning("GUI event emission failed for %s: %s", kind, exc)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _client_profile_name(client: Any) -> str | None:
    profile = getattr(client, "profile", None)
    name = getattr(profile, "name", None)
    return name if isinstance(name, str) else None


def _raw_response_payload(response: LLMResponse, fallback: Any) -> Any:
    if response.raw_response is not None:
        return _to_jsonable(response.raw_response)
    raw_path = response.raw_response_path
    if raw_path is not None and raw_path.exists():
        try:
            return json.loads(raw_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return raw_path.read_text(encoding="utf-8")
    return fallback


__all__ = ["BatchEvent", "BatchRunner", "PreviewAbandoned", "RunResult"]
