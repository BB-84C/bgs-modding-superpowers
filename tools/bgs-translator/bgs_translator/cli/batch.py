"""Batch-planning CLI commands."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import sys
import tomllib
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

import typer
from pydantic import BaseModel

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.config.profiles import ProviderProfile, get_active_profile, load_profiles
from bgs_translator.config.settings import load_settings
from bgs_translator.core import runtime_pid
from bgs_translator.core.client import request_preview
from bgs_translator.kb.glossary import GlossaryComposer
from bgs_translator.kb.reader import KBGlossaryReader
from bgs_translator.observability.cost_tracker import CostTracker
from bgs_translator.observability.rate_tracker import RateTracker
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.batcher import Batch, BatchPlan, plan_batches
from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage, build_client_for
from bgs_translator.pipeline.clients.synthetic import SyntheticLLMClient
from bgs_translator.pipeline.extractor import collect_units_for_run
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.pipeline.runner import BatchRunner

batch_app = typer.Typer(no_args_is_help=True)
SIG_OPTION = typer.Option(None, "--sig")
FIELD_OPTION = typer.Option(None, "--field")
log = logging.getLogger(__name__)


@batch_app.command("plan")
def plan_batch(
    project: str = typer.Argument(...),
    register: str = typer.Option(..., "--register"),
    target_lang: str = typer.Option(..., "--target-lang"),
    profile: str = typer.Option(..., "--profile"),
    game_lore: str = typer.Option("", "--game-lore"),
    mod_name: str = typer.Option("", "--mod-name"),
    mod_theme: str = typer.Option("", "--mod-theme"),
    style: str = typer.Option("", "--style"),
    batch_size: int | None = typer.Option(None, "--batch-size"),
    sig: list[str] | None = SIG_OPTION,
    field: list[str] | None = FIELD_OPTION,
) -> None:
    """Plan a batch run and persist plan.json. Does not dispatch LLM calls."""

    project_root = paths.project_root(project)
    memory_path = project_root / "memory" / "memory.sqlite"
    if not memory_path.exists():
        _emit_failure("project_not_found", f"memory.sqlite not found for project: {project}", {})
    conn = sqlite3.connect(memory_path)
    try:
        units = collect_units_for_run(
            conn,
            statuses=["untranslated"],
            signatures=sig,
            fields=field,
        )
        game = _read_project_game(project_root)
        batch_plan = plan_batches(
            units,
            project=project,
            profile_name=profile,
            target_lang=target_lang,
            register=register,
            glossary_composer=GlossaryComposer(KBGlossaryReader()),
            game=game,
            batch_size=batch_size,
            game_lore_world=game_lore or game,
            game_context_lore_summary=game_lore or game,
            mod_context_name=mod_name or project,
            mod_context_theme=mod_theme,
            style_directives=style,
        )
        run_id = uuid.uuid4().hex
        run_dir = project_root / "batches" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        plan_path = run_dir / "plan.json"
        plan_path.write_text(json.dumps(_to_jsonable(batch_plan), ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        conn.close()

    _emit_success(
        {
            "project": project,
            "run_id": run_id,
            "plan_id": batch_plan.plan_id,
            "plan_path": str(plan_path),
            "total_items": batch_plan.total_items,
            "batch_count": len(batch_plan.batches),
            "est_input_tokens": batch_plan.est_input_tokens,
            "est_output_tokens": batch_plan.est_output_tokens,
            "est_cost_usd": batch_plan.est_cost_usd,
        }
    )


@batch_app.command("run")
def run_batch(
    project: str = typer.Argument(...),
    plan_id: str = typer.Option(..., "--plan"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Execute a planned batch run."""

    project_root = paths.project_root(project)
    plan_path = _find_plan_path(project_root, plan_id)
    if plan_path is None:
        _emit_failure("plan_not_found", f"Plan {plan_id!r} not found for project {project!r}.", {})
    assert plan_path is not None
    plan = _load_plan(plan_path)
    run_id = f"rn_{uuid.uuid4().hex[:12]}"
    client: Any
    if dry_run:
        profile = ProviderProfile(
            name="synthetic",
            sdk_kind="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-5-mini",
            api_key_env="BGS_TRANSLATOR_KEY_SYNTHETIC",
        )
        client = SyntheticLLMClient()
    else:
        cfg = load_profiles()
        profile = get_active_profile(cfg) if cfg.active is not None else cfg.profiles[plan.profile_name]
        client = build_client_for(profile)
    if _preview_enabled_for_session():
        client = _PreviewingLLMClient(client, profile)
    runner = BatchRunner(plan, client, RateTracker(profile), CostTracker(profile))
    result = asyncio.run(runner.run(run_id))
    _emit_success({"run_id": run_id, "plan_id": plan.plan_id, "dry_run": dry_run, "summary": asdict(result)})


@batch_app.command("status")
def batch_status(run_id: str) -> None:
    """Show persisted run status."""

    status_path = _find_run_file(run_id, "status.toml")
    if status_path is None:
        _emit_failure("run_not_found", f"Run {run_id!r} not found.", {})
    assert status_path is not None
    data = tomllib.loads(status_path.read_text(encoding="utf-8"))
    _emit_success({"run_id": run_id, "status": data})


@batch_app.command("cancel")
def batch_cancel(run_id: str) -> None:
    """Request cancellation for a run by writing a cancel marker."""

    run_dir = _find_run_dir(run_id)
    if run_dir is None:
        _emit_failure("run_not_found", f"Run {run_id!r} not found.", {})
    assert run_dir is not None
    marker = run_dir / "cancel.requested"
    marker.write_text("cancel requested\n", encoding="utf-8")
    _emit_success(
        {
            "run_id": run_id,
            "cancel_requested": True,
            "note": "Provider may bill for tokens consumed before client-side abort. Final bill may differ from estimate.",
        }
    )


@batch_app.command("logs")
def batch_logs(run_id: str) -> None:
    """Show recent persisted run log-like artifacts."""

    run_dir = _find_run_dir(run_id)
    if run_dir is None:
        _emit_failure("run_not_found", f"Run {run_id!r} not found.", {})
    assert run_dir is not None
    lines: list[str] = []
    for name in ("status.toml", "validator-failures.jsonl"):
        path = run_dir / name
        if path.exists():
            lines.extend(path.read_text(encoding="utf-8").splitlines()[-20:])
    _emit_success({"run_id": run_id, "lines": lines[-50:]})


def _read_project_game(project_root: Path) -> str:
    project_toml = project_root / "project.toml"
    if not project_toml.exists():
        return "SkyrimSE"
    data = tomllib.loads(project_toml.read_text(encoding="utf-8"))
    project_data = data.get("project", {})
    game = project_data.get("game")
    return str(game) if game else "SkyrimSE"


class _PreviewingLLMClient:
    """LLM client wrapper that performs GUI prompt approval before dispatch."""

    def __init__(self, inner: Any, profile: ProviderProfile) -> None:
        self._inner = inner
        self.profile = profile
        self._approve_all_remaining = False

    async def translate_batch(self, batch: Batch, system_prompt: str) -> LLMResponse:
        prompt = system_prompt
        if not self._approve_all_remaining:
            response = self._request_preview(batch, system_prompt)
            op = str(response.get("op", "approved"))
            if op == "approved":
                prompt = str(response.get("prompt", system_prompt))
            elif op == "approve_all":
                prompt = str(response.get("prompt", system_prompt))
                self._approve_all_remaining = True
            elif op == "discarded":
                return _discarded_response(batch)
            elif op in {"no_gui", "timeout", "transport_unavailable"}:
                log.info("Using original prompt for batch %s after preview op=%s", batch.batch_id, op)
                prompt = system_prompt
        return cast(LLMResponse, await self._inner.translate_batch(batch, prompt))

    async def aclose(self) -> None:
        close = getattr(self._inner, "aclose", None)
        if close is not None:
            await close()

    def _request_preview(self, batch: Batch, system_prompt: str) -> dict[str, Any]:
        try:
            return request_preview(
                batch.batch_id,
                system_prompt,
                _items_payload(batch),
                timeout=300.0,
            )
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            log.warning(
                "IPC preview unavailable for batch %s (GUI not listening): %s",
                batch.batch_id,
                exc,
            )
            sys.stderr.write(
                f"[warn] preview skipped for batch {batch.batch_id}: GUI not reachable ({exc})\n"
            )
            return {"op": "no_gui"}
        except TimeoutError as exc:
            log.warning("IPC preview timed out for batch %s: %s", batch.batch_id, exc)
            sys.stderr.write(f"[warn] preview timeout for batch {batch.batch_id}\n")
            return {"op": "timeout"}
        except RuntimeError as exc:
            log.error("IPC preview transport unavailable: %s", exc)
            sys.stderr.write(
                f"[error] preview transport missing: {exc}\n  install pywin32: pip install pywin32\n"
            )
            return {"op": "transport_unavailable"}


def _preview_enabled_for_session() -> bool:
    settings = load_settings()
    if not settings.behavior.prompt_preview_required:
        return False
    alive, _pid = runtime_pid.is_gui_alive()
    return alive


def _items_payload(batch: Batch) -> list[dict[str, object]]:
    payload = _to_jsonable(batch.items)
    if not isinstance(payload, list):
        return []
    return [cast(dict[str, object], item) for item in payload if isinstance(item, dict)]


def _discarded_response(batch: Batch) -> LLMResponse:
    return LLMResponse(
        items={f"I{index}": item.source_masked for index, item in enumerate(batch.items, start=1)},
        usage=TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0),
        via="synthetic",
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _find_plan_path(project_root: Path, plan_id: str) -> Path | None:
    for candidate in sorted((project_root / "batches").glob("*/plan.json")):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("plan_id") == plan_id:
            return candidate
    return None


def _find_run_dir(run_id: str) -> Path | None:
    for candidate in paths.projects_root().glob(f"*/batches/{run_id}"):
        if candidate.is_dir():
            return candidate
    return None


def _find_run_file(run_id: str, file_name: str) -> Path | None:
    run_dir = _find_run_dir(run_id)
    if run_dir is None:
        return None
    candidate = run_dir / file_name
    return candidate if candidate.exists() else None


def _load_plan(plan_path: Path) -> BatchPlan:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    batches = [_load_batch(batch_data) for batch_data in data.get("batches", [])]
    return BatchPlan(
        plan_id=str(data["plan_id"]),
        project=str(data["project"]),
        profile_name=str(data["profile_name"]),
        target_lang=str(data["target_lang"]),
        register=str(data["register"]),
        batches=batches,
        total_items=int(data["total_items"]),
        est_input_tokens=int(data["est_input_tokens"]),
        est_output_tokens=int(data["est_output_tokens"]),
        est_cost_usd=float(data["est_cost_usd"]),
        sample_system_prompt=str(data.get("sample_system_prompt", "")),
    )


def _load_batch(data: dict[str, Any]) -> Batch:
    items = []
    for item_data in data.get("items", []):
        unit_data = item_data["unit"]
        unit = TranslationUnit(
            plugin=str(unit_data["plugin"]),
            formid=int(unit_data["formid"]),
            formid_sanitized=int(unit_data["formid_sanitized"]),
            edid=unit_data.get("edid"),
            signature=str(unit_data["signature"]),
            field=str(unit_data["field"]),
            source=str(unit_data["source"]),
            index_n=int(unit_data.get("index_n", 0)),
            index_max=int(unit_data.get("index_max", 0)),
            list_index=int(unit_data.get("list_index", 0)),
            strid=int(unit_data.get("strid", 0)),
        )
        items.append(build_masked_unit(unit))
    return Batch(
        batch_id=str(data["batch_id"]),
        items=items,
        parent_context_summary=data.get("parent_context_summary"),
        glossary_subset=[],
        do_not_translate=[str(item) for item in data.get("do_not_translate", [])],
    )


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> NoReturn:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["batch_app", "plan_batch"]
