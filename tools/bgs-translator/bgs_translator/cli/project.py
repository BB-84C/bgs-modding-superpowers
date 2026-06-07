"""Project lifecycle CLI commands for translator projects."""

# ruff: noqa: UP045

from __future__ import annotations

import hashlib
import json
import pickle
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import tomli_w
import typer

from bgs_translator import __version__
from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.core.memory import insert_units, open_memory_db
from bgs_translator.parsers.extractor import GameSchema, extract_translation_units
from bgs_translator.parsers.form_versions import detect_game_from_form_version
from bgs_translator.parsers.schemas import get_schema_for_game
from bgs_translator.parsers.tes4_family import TES4FamilyWalker, TES4Header, TranslationUnit

project_app = typer.Typer(no_args_is_help=True)
NAME_ARGUMENT = typer.Argument(..., help="Project name (slug)")
PLUGIN_OPTION = typer.Option(..., "--plugin", "-p", help="Source plugin path")
GAME_OPTION = typer.Option(None, "--game", "-g", help="Game name")
TARGET_LANG_OPTION = typer.Option("zh-cn", "--target-lang", "-t")
SOURCE_LANG_OPTION = typer.Option("en", "--source-lang", "-s")


@project_app.command("init")
def init_project(
    name: str = NAME_ARGUMENT,
    plugin: Path = PLUGIN_OPTION,
    game: Optional[str] = GAME_OPTION,
    target_lang: str = TARGET_LANG_OPTION,
    source_lang: str = SOURCE_LANG_OPTION,
) -> None:
    """Create a new translation project: walk plugin, extract units, seed memory.sqlite."""

    if not plugin.exists():
        _emit_failure("plugin_not_found", f"Plugin not found: {plugin}", {"plugin": str(plugin)})

    try:
        header = _read_header(plugin)
        selected_game = game or _detect_unique_game(header)
        schema = get_schema_for_game(selected_game)
        units = list(extract_translation_units(plugin, selected_game, schema=schema))
        project_root = paths.project_root(name)
        for subdir in ["sources", "memory", "batches", "exports"]:
            (project_root / subdir).mkdir(parents=True, exist_ok=True)
        plugin_sha = _sha256(plugin)
        _write_cache(project_root, plugin, units, plugin_sha, schema)
        conn = open_memory_db(project_root)
        inserted = insert_units(conn, units)
        _write_project_toml(
            project_root,
            name=name,
            plugin=plugin,
            plugin_sha=plugin_sha,
            game=selected_game,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    except KeyError as exc:
        _emit_failure("unknown_game", f"Unknown game: {game}", {"game": game})
        raise typer.Exit(1) from exc
    except ValueError as exc:
        _emit_failure("parse_error", str(exc), {"plugin": str(plugin)})
        raise typer.Exit(1) from exc

    _emit_success(
        {
            "project": name,
            "project_root": str(project_root),
            "game": selected_game,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "plugin_sha256": plugin_sha,
            "units_extracted": inserted,
            "signature_distribution": dict(Counter(unit.signature for unit in units)),
        }
    )


def _detect_unique_game(header: TES4Header) -> str:
    candidates = detect_game_from_form_version(header.form_version)
    if len(candidates) == 1:
        return candidates[0]
    details = {"form_version": header.form_version, "candidates": candidates}
    envelope = failure(
        "ambiguous_game",
        f"Form version {header.form_version} is ambiguous; pass --game.",
        details=details,
    )
    _echo_envelope(envelope)
    raise typer.Exit(1)


def _read_header(plugin: Path) -> TES4Header:
    walker = TES4FamilyWalker(plugin)
    next(walker.walk(), None)
    if walker.header is None:
        msg = f"Could not parse TES4 header from {plugin}"
        raise ValueError(msg)
    return walker.header


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_cache(
    project_root: Path,
    plugin: Path,
    units: list[TranslationUnit],
    plugin_sha: str,
    schema: GameSchema,
) -> None:
    cache_bin = project_root / "sources" / f"{plugin.name}.cache.bin"
    cache_bin.write_bytes(pickle.dumps(units))
    cache_toml = {
        "plugin_sha256": plugin_sha,
        "parser_version": __version__,
        "schema_version": str(getattr(schema, "schema_version", "unknown")),
        "extracted_units": len(units),
        "extracted_at": datetime.now(UTC).isoformat(),
    }
    (project_root / "sources" / f"{plugin.name}.cache.toml").write_text(
        tomli_w.dumps(cache_toml), encoding="utf-8"
    )


def _write_project_toml(
    project_root: Path,
    *,
    name: str,
    plugin: Path,
    plugin_sha: str,
    game: str,
    source_lang: str,
    target_lang: str,
) -> None:
    project_data: dict[str, Any] = {
        "schema_version": 1,
        "project": {
            "name": name,
            "created_at": datetime.now(UTC).isoformat(),
            "game": game,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_plugin_path": str(plugin),
            "source_plugin_sha256": plugin_sha,
            "parser_version": __version__,
        },
        "settings": {
            "active_profile": "",
            "prompt_template": "default",
            "starfield_dummy_fill": game == "Starfield",
        },
        "cost": {"cap_usd": 10.0, "spent_usd_session": 0.0, "spent_usd_total": 0.0},
    }
    (project_root / "project.toml").write_text(tomli_w.dumps(project_data), encoding="utf-8")


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> None:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["project_app"]
