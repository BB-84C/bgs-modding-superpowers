"""Batch lifecycle, cancellation, retry, and event emission ownership."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import tomli_w

from bgs_translator.config import paths
from bgs_translator.observability.cost_tracker import CostTracker
from bgs_translator.observability.rate_tracker import RateTracker
from bgs_translator.pipeline.batcher import Batch, BatchPlan, estimate_tokens
from bgs_translator.pipeline.clients.base import LLMClient, LLMResponse
from bgs_translator.pipeline.mask import unmask_dest
from bgs_translator.pipeline.validator import ValidationFailure, validate_item


@dataclass
class BatchEvent:
    """Progress event for GUI/CLI consumption."""

    run_id: str
    batch_id: str
    kind: Literal["start", "in_flight", "complete", "failed", "cancelled", "rate_limited"]
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
    cost_usd: float
    cost_exact: bool


@dataclass
class _BatchOutcome:
    succeeded: int = 0
    retried: int = 0
    manual_review: int = 0
    cancelled: int = 0
    failures: list[ValidationFailure] = field(default_factory=list)


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

    async def run(
        self,
        run_id: str,
        event_queue: asyncio.Queue[BatchEvent] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> RunResult:
        """Execute all batches concurrently up to profile.max_concurrency."""

        run_dir = paths.project_root(self.plan.project) / "batches" / run_id
        self._prepare_run_dir(run_dir)
        semaphore = asyncio.Semaphore(max(1, self.rate_tracker.profile.max_concurrency))
        outcomes = await asyncio.gather(
            *(self._run_batch(run_id, run_dir, batch, semaphore, event_queue, cancel_event) for batch in self.plan.batches)
        )
        result = RunResult(
            run_id=run_id,
            total_items=self.plan.total_items,
            succeeded=sum(outcome.succeeded for outcome in outcomes),
            retried=sum(outcome.retried for outcome in outcomes),
            manual_review=sum(outcome.manual_review for outcome in outcomes),
            cancelled=sum(outcome.cancelled for outcome in outcomes),
            cost_usd=self.cost_tracker.estimated_total(),
            cost_exact=self.cost_tracker.cost_exact,
        )
        self._write_json(run_dir / "results.json", asdict(result))
        (run_dir / "status.toml").write_text(tomli_w.dumps(asdict(result)), encoding="utf-8")
        failure_path = run_dir / "validator-failures.jsonl"
        failures = [failure for outcome in outcomes for failure in outcome.failures]
        if failures:
            failure_path.write_text(
                "\n".join(json.dumps(failure.model_dump(), ensure_ascii=False) for failure in failures),
                encoding="utf-8",
            )
        return result

    async def _run_batch(
        self,
        run_id: str,
        run_dir: Path,
        batch: Batch,
        semaphore: asyncio.Semaphore,
        event_queue: asyncio.Queue[BatchEvent] | None,
        cancel_event: asyncio.Event | None,
    ) -> _BatchOutcome:
        async with semaphore:
            if cancel_event is not None and cancel_event.is_set():
                await self._emit(event_queue, run_id, batch.batch_id, "cancelled")
                return _BatchOutcome(cancelled=len(batch.items))
            await self._emit(event_queue, run_id, batch.batch_id, "start")
            est_tokens = estimate_tokens(self._system_prompt(batch)) + estimate_tokens(
                "\n".join(item.source_masked for item in batch.items)
            )
            await self.rate_tracker.acquire(est_tokens)
            if self.cost_tracker.would_exceed_cap(self._batch_estimated_cost()):
                await self._emit(event_queue, run_id, batch.batch_id, "cancelled", {"reason": "cost_cap"})
                return _BatchOutcome(cancelled=len(batch.items))
            outcome = await self._attempt_batch(run_dir, batch, cancel_event)
            await self._emit(
                event_queue,
                run_id,
                batch.batch_id,
                "cancelled" if outcome.cancelled else "complete",
                asdict(outcome) | {"failures": [failure.model_dump() for failure in outcome.failures]},
            )
            return outcome

    async def _attempt_batch(
        self, run_dir: Path, batch: Batch, cancel_event: asyncio.Event | None
    ) -> _BatchOutcome:
        failures: list[ValidationFailure] = []
        for attempt in range(self.max_retries + 1):
            if cancel_event is not None and cancel_event.is_set():
                return _BatchOutcome(cancelled=len(batch.items), failures=failures)
            try:
                response = await self.client.translate_batch(batch, self._system_prompt(batch))
            except asyncio.CancelledError:
                return _BatchOutcome(cancelled=len(batch.items), failures=failures)
            self.cost_tracker.record(response.usage, response.cost_usd if response.cost_exact else None)
            self._persist_response(run_dir, batch.batch_id, attempt, response)
            hard_failures = self._validate_response(batch, response)
            failures.extend(hard_failures)
            if not hard_failures:
                return _BatchOutcome(succeeded=len(batch.items), retried=attempt, failures=failures)
        return _BatchOutcome(
            manual_review=len(batch.items),
            retried=self.max_retries,
            failures=failures,
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

    def _prepare_run_dir(self, run_dir: Path) -> None:
        (run_dir / "responses").mkdir(parents=True, exist_ok=True)
        (run_dir / "retries").mkdir(parents=True, exist_ok=True)
        self._write_json(run_dir / "plan.json", _to_jsonable(self.plan))
        (run_dir / "system-prompt.md").write_text(self.plan.sample_system_prompt, encoding="utf-8")

    def _persist_response(self, run_dir: Path, batch_id: str, attempt: int, response: LLMResponse) -> None:
        response_dir = run_dir / "responses"
        retry_dir = run_dir / "retries"
        payload = _to_jsonable(response)
        if attempt == 0:
            self._write_json(response_dir / f"{batch_id}.normalized.json", payload)
        else:
            self._write_json(retry_dir / f"{batch_id}.attempt-{attempt}.json", payload)

    def _batch_estimated_cost(self) -> float:
        if not self.plan.batches:
            return 0.0
        return self.plan.est_cost_usd / len(self.plan.batches)

    def _system_prompt(self, batch: Batch) -> str:
        if batch.parent_context_summary:
            return f"{self.plan.sample_system_prompt}\n\n{batch.parent_context_summary}"
        return self.plan.sample_system_prompt

    async def _emit(
        self,
        event_queue: asyncio.Queue[BatchEvent] | None,
        run_id: str,
        batch_id: str,
        kind: Literal["start", "in_flight", "complete", "failed", "cancelled", "rate_limited"],
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


__all__ = ["BatchEvent", "BatchRunner", "RunResult"]
