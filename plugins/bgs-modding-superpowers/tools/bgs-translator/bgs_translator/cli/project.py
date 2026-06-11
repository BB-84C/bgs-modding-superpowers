"""Project lifecycle CLI commands for translator projects."""

# ruff: noqa: UP045

from __future__ import annotations

import hashlib
import json
import pickle
import sqlite3
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
from bgs_translator.parsers.form_versions import detect_game_from_header
from bgs_translator.parsers.schemas import get_schema_for_game
from bgs_translator.parsers.tes4_family import TES4FamilyWalker, TES4Header, TranslationUnit
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.sst.hash import compute_rhash
from bgs_translator.sst.status import SStrParam, normalize_params_for_status
from bgs_translator.sst.writer import SSTUnit, write_sst

# Starfield 9-fill lang slugs per PRD §3.2
STARFIELD_FILL_LANGS = [
    "english",
    "french",
    "german",
    "italian",
    "spanish",
    "polish",
    "brazilianportuguese",
    "japanese",
]

# Target lang code → xTranslator filename slug (PRD §2 table)
LANG_SLUG = {
    "en": "english",
    "fr": "french",
    "de": "german",
    "it": "italian",
    "es": "spanish",
    "pl": "polish",
    "ru": "russian",
    "cs": "czech",
    "ja": "japanese",
    "zh-cn": "chinese",
}

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
    candidates = detect_game_from_header(header.form_version, header.masters)
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


@project_app.command("export")
def export_project(
    name: str = NAME_ARGUMENT,
    fmt: str = typer.Option("sst", "--format", "-f", help="Export format: sst or eet_xml"),
    no_starfield_fill: bool = typer.Option(
        False, "--no-starfield-dummy-fill", help="Disable Starfield 9-fill"
    ),
) -> None:
    """Export project translations to SST (TES4-family) or ESP-ESM XML (Morrowind)."""
    project_root = paths.project_root(name)
    if not (project_root / "project.toml").exists():
        _emit_failure("project_not_found", f"No project at {project_root}", {"name": name})
    try:
        proj_meta = _read_project_toml(project_root)
        plugin_basename = Path(proj_meta["source_plugin_path"]).stem
        game = proj_meta["game"]
        source_lang = proj_meta["source_lang"]
        target_lang = proj_meta["target_lang"]
        starfield_fill = (
            game == "Starfield"
            and proj_meta.get("starfield_dummy_fill", True)
            and not no_starfield_fill
        )

        exports_dir = project_root / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        if fmt == "sst":
            conn = open_memory_db(project_root)
            units = _read_units_from_memory(conn)
            sst_units = [_unit_row_to_sst_unit(row) for row in units]
            masters = _detect_masters_from_units(units)

            outputs = _emit_sst_outputs(
                exports_dir,
                plugin_basename,
                source_lang,
                target_lang,
                sst_units,
                masters,
                starfield_fill=starfield_fill,
            )
            conn.close()
            _emit_success(
                {
                    "project": name,
                    "format": "sst",
                    "files_emitted": outputs,
                    "starfield_dummy_fill_applied": starfield_fill,
                    "entry_count": len(sst_units),
                }
            )
        else:
            _emit_failure(
                "unsupported_format",
                f"Format '{fmt}' not yet supported by CLI export; use sst for now.",
                {"requested": fmt},
            )
    except FileNotFoundError as exc:
        _emit_failure("project_corrupted", str(exc), {"name": name})
        raise typer.Exit(1) from exc


def _read_project_toml(project_root: Path) -> dict[str, Any]:
    import tomllib

    with (project_root / "project.toml").open("rb") as fh:
        data = tomllib.load(fh)
    proj: dict[str, Any] = data.get("project", {})
    proj["starfield_dummy_fill"] = data.get("settings", {}).get(
        "starfield_dummy_fill", proj.get("game") == "Starfield"
    )
    return proj


def _read_units_from_memory(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT plugin, formid, formid_sanitized, edid, signature, field, "
        "index_n, index_max, source, list_index, strid, rhash, sparams, "
        "dest, status FROM units WHERE source IS NOT NULL"
    )
    rows = cur.fetchall()
    referenced_string_keys = {
        (row["plugin"], row["list_index"], row["strid"])
        for row in rows
        if str(row["signature"] or "").strip().upper() != "ORPH" and row["strid"]
    }
    return [
        row
        for row in rows
        if _should_export_unit_row(row)
        and not _is_redundant_orphan_string(row, referenced_string_keys)
    ]


def _is_redundant_orphan_string(
    row: sqlite3.Row, referenced_string_keys: set[tuple[str, int, int]]
) -> bool:
    if str(row["signature"] or "").strip().upper() != "ORPH":
        return False
    return (row["plugin"], row["list_index"], row["strid"]) in referenced_string_keys


_EXPORT_STATUS_MASK = (
    SStrParam.TRANSLATED
    | SStrParam.LOCKED_TRANS
    | SStrParam.INCOMPLETE_TRANS
    | SStrParam.VALIDATED
    | SStrParam.PENDING
)


def _should_export_unit_row(row: sqlite3.Row) -> bool:
    status_value = str(row["status"] or "").strip().lower()
    sparams = _export_sparams_for_row(row, status_value)
    if not (sparams & _EXPORT_STATUS_MASK):
        return False
    if SStrParam.LOCKED_TRANS in sparams or SStrParam.PENDING in sparams:
        return True
    return bool(str(row["dest"] or "").strip())


def _unit_row_to_sst_unit(row: sqlite3.Row) -> SSTUnit:
    edid = row["edid"]
    is_orphan = str(row["signature"] or "").strip().upper() == "ORPH"
    rhash = 0 if is_orphan else row["rhash"] or compute_rhash(edid, row["formid"])
    status_value = str(row["status"] or "").strip().lower()
    sparams = _export_sparams_for_row(row, status_value)
    source = row["source"] or ""
    dest = row["dest"] or ""
    if not dest and (SStrParam.LOCKED_TRANS in sparams or SStrParam.PENDING in sparams):
        dest = source
    return SSTUnit(
        list_index=row["list_index"],
        strid=row["strid"] or 0,
        formid=0 if is_orphan else row["formid"],
        signature="" if is_orphan else row["signature"],
        field="" if is_orphan else row["field"],
        index=0 if is_orphan else row["index_n"] or 0,
        index_max=0 if is_orphan else row["index_max"] or 0,
        rhash=rhash,
        colab_id=0,
        s_params=int(sparams),
        source=source,
        dest=dest,
    )


def _export_sparams_for_row(row: sqlite3.Row, status_value: str) -> SStrParam:
    raw_params = SStrParam(int(row["sparams"] or 0) & 0xFF)
    if SStrParam.LOCKED_TRANS in raw_params:
        return SStrParam.LOCKED_TRANS
    if _is_xtranslator_locked_header(row):
        return SStrParam.LOCKED_TRANS
    if _unit_row_skip_reason(row):
        return SStrParam.LOCKED_TRANS
    if SStrParam.INCOMPLETE_TRANS in raw_params:
        return SStrParam.INCOMPLETE_TRANS
    if SStrParam.TRANSLATED in raw_params:
        return SStrParam.TRANSLATED
    if SStrParam.PENDING in raw_params:
        return SStrParam.PENDING
    if status_value == "untranslated":
        return SStrParam.PENDING
    return normalize_params_for_status(status_value, row["sparams"] or 0)


def _is_xtranslator_locked_header(row: sqlite3.Row) -> bool:
    return str(row["signature"] or "").strip().upper() == "TES4" and str(row["field"] or "").strip().upper() in {
        "CNAM",
        "SNAM",
    }


def _unit_row_skip_reason(row: sqlite3.Row) -> str:
    unit = TranslationUnit(
        plugin=str(row["plugin"]),
        formid=int(row["formid"]),
        formid_sanitized=int(row["formid_sanitized"] if row["formid_sanitized"] is not None else row["formid"]),
        edid=str(row["edid"] or ""),
        signature=str(row["signature"]),
        field=str(row["field"]),
        source=str(row["source"] or ""),
        list_index=int(row["list_index"] or 0),
        strid=int(row["strid"] or 0),
    )
    masked = build_masked_unit(unit)
    return masked.skip_reason if masked.skip_llm else ""


def _detect_masters_from_units(units: list[sqlite3.Row]) -> list[str]:
    seen: set[str] = set()
    masters: list[str] = []
    for row in units:
        plugin_name = row["plugin"]
        if plugin_name and plugin_name not in seen:
            seen.add(plugin_name)
            masters.append(plugin_name)
    return masters


def _emit_sst_outputs(
    exports_dir: Path,
    plugin_basename: str,
    source_lang: str,
    target_lang: str,
    units: list[SSTUnit],
    masters: list[str],
    *,
    starfield_fill: bool,
) -> list[str]:
    """Emit 1 real SST + (Starfield only) 8 dummy-fill SSTs per PRD §3.2."""
    written: list[str] = []
    src_slug = LANG_SLUG.get(source_lang, source_lang)
    tgt_slug = LANG_SLUG.get(target_lang, target_lang)

    real_path = exports_dir / f"{plugin_basename}_{src_slug}_{tgt_slug}.sst"
    write_sst(real_path, units, masters)
    written.append(str(real_path))

    if starfield_fill:
        dummy_units = [
            SSTUnit(
                list_index=u.list_index,
                strid=u.strid,
                formid=u.formid,
                signature=u.signature,
                field=u.field,
                index=u.index,
                index_max=u.index_max,
                rhash=u.rhash,
                colab_id=u.colab_id,
                s_params=u.s_params,
                source=u.source,
                dest=u.source,  # dummy: dest = source verbatim
            )
            for u in units
        ]
        for lang in STARFIELD_FILL_LANGS:
            if lang == tgt_slug:
                continue
            dummy_path = exports_dir / f"{plugin_basename}_{src_slug}_{lang}.sst"
            write_sst(dummy_path, dummy_units, masters)
            written.append(str(dummy_path))
    return written


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> None:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["project_app"]
