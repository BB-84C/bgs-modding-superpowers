"""Inspection CLI commands for parsed plugin translation units."""

# ruff: noqa: UP045

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import typer

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.core.memory import (
    count_units,
    get_unit_by_row_id,
    get_unit_counts_by_signature,
    list_units,
    open_memory_db,
)
from bgs_translator.parsers.extractor import extract_translation_units
from bgs_translator.parsers.form_versions import detect_game_from_form_version
from bgs_translator.parsers.schemas import get_schema_for_game
from bgs_translator.parsers.tes4_family import TES4FamilyWalker, TES4Header

inspect_app = typer.Typer(no_args_is_help=True)
PLUGIN_ARGUMENT = typer.Argument(...)
PROJECT_ARGUMENT = typer.Argument(...)
PROJECT_NAME_ARGUMENT = typer.Argument(..., help="Project name")
ROW_ID_ARGUMENT = typer.Argument(...)
GAME_OPTION = typer.Option(None, "--game")
SIG_OPTION = typer.Option(None, "--sig")
FIELD_OPTION = typer.Option(None, "--field")
LIMIT_OPTION = typer.Option(50)


@inspect_app.command("plugin")
def inspect_plugin(
    plugin: Path = PLUGIN_ARGUMENT,
    game: Optional[str] = GAME_OPTION,
) -> None:
    """Walk plugin without project state; return header info and signature distribution."""

    if not plugin.exists():
        _emit_failure("plugin_not_found", f"Plugin not found: {plugin}", {"plugin": str(plugin)})
    header = _read_header(plugin)
    selected_game = game or _detect_unique_game(header)
    schema = get_schema_for_game(selected_game)
    units = list(extract_translation_units(plugin, selected_game, schema=schema))
    _emit_success(
        {
            "plugin": str(plugin),
            "game": selected_game,
            "header": {
                "form_version": header.form_version,
                "is_localized": header.is_localized,
                "is_esl": header.is_esl,
                "masters": header.masters,
            },
            "total_units": len(units),
            "signature_distribution": dict(Counter(unit.signature for unit in units)),
        }
    )


@inspect_app.command("signatures")
def inspect_signatures(project: str = PROJECT_NAME_ARGUMENT) -> None:
    """For an existing project, return signature counts from memory.sqlite."""

    conn = _open_project(project)
    _emit_success({"project": project, "signatures": get_unit_counts_by_signature(conn)})


@inspect_app.command("entries")
def inspect_entries(
    project: str = PROJECT_ARGUMENT,
    sig: Optional[str] = SIG_OPTION,
    field: Optional[str] = FIELD_OPTION,
    limit: int = LIMIT_OPTION,
) -> None:
    """Filterable entry listing."""

    conn = _open_project(project)
    total = count_units(conn, sig=sig, field=field)
    entries = list_units(conn, sig=sig, field=field, limit=limit)
    _emit_success(
        {"project": project, "total_matched": total, "returned": len(entries), "entries": entries}
    )


@inspect_app.command("entry")
def inspect_entry(
    project: str = PROJECT_ARGUMENT, row_id: str = ROW_ID_ARGUMENT
) -> None:
    """Return a single entry by row_id."""

    conn = _open_project(project)
    entry = get_unit_by_row_id(conn, row_id)
    if entry is None:
        _emit_failure("entry_not_found", f"Entry not found: {row_id}", {"row_id": row_id})
    _emit_success({"project": project, "entry": entry})


@inspect_app.command("orphans")
def inspect_orphans(project: str = PROJECT_ARGUMENT) -> None:
    """Entries with status='orphan'."""

    conn = _open_project(project)
    entries = list_units(conn, status="orphan", limit=10_000)
    _emit_success({"project": project, "returned": len(entries), "entries": entries})


def _open_project(project: str) -> sqlite3.Connection:
    project_root = paths.project_root(project)
    if not project_root.exists():
        _emit_failure("project_not_found", f"Project not found: {project}", {"project": project})
    return open_memory_db(project_root)


def _detect_unique_game(header: TES4Header) -> str:
    candidates = detect_game_from_form_version(header.form_version)
    if len(candidates) == 1:
        return candidates[0]
    _emit_failure(
        "ambiguous_game",
        f"Form version {header.form_version} is ambiguous; pass --game.",
        {"form_version": header.form_version, "candidates": candidates},
    )
    raise typer.Exit(1)


def _read_header(plugin: Path) -> TES4Header:
    walker = TES4FamilyWalker(plugin)
    next(walker.walk(), None)
    if walker.header is None:
        msg = f"Could not parse TES4 header from {plugin}"
        raise ValueError(msg)
    return walker.header


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> None:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["inspect_app"]
