"""Batch-planning CLI commands."""

from __future__ import annotations

import json
import sqlite3
import tomllib
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.kb.glossary import GlossaryComposer
from bgs_translator.kb.models import GlossaryEntry
from bgs_translator.pipeline.batcher import plan_batches
from bgs_translator.pipeline.extractor import collect_units_for_run

batch_app = typer.Typer(no_args_is_help=True)
SIG_OPTION = typer.Option(None, "--sig")
FIELD_OPTION = typer.Option(None, "--field")


class _EmptyGlossaryReader:
    def query_matching_entries(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        mod_slug: str | None = None,
    ) -> list[GlossaryEntry]:
        del source_strings, target_lang, game, mod_slug
        return []


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
            glossary_composer=GlossaryComposer(_EmptyGlossaryReader()),  # type: ignore[arg-type]
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


def _read_project_game(project_root: Path) -> str:
    project_toml = project_root / "project.toml"
    if not project_toml.exists():
        return "SkyrimSE"
    data = tomllib.loads(project_toml.read_text(encoding="utf-8"))
    project_data = data.get("project", {})
    game = project_data.get("game")
    return str(game) if game else "SkyrimSE"


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


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> None:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["batch_app", "plan_batch"]
