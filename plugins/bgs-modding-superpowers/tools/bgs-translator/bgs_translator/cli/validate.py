"""Validation CLI commands for project and output checks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import tomllib
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, NoReturn

import typer

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.core.memory import open_memory_db
from bgs_translator.parsers.schemas import get_schema_for_game
from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.pipeline.validator import validate_item
from bgs_translator.sst import SStrParam, SSTUnit, read_sst, write_sst

Severity = Literal["info", "warn", "error"]
validate_app = typer.Typer(no_args_is_help=True)

PROJECT_ARGUMENT = typer.Argument(...)
SST_ARGUMENT = typer.Argument(...)
REFERENCE_OPTION = typer.Option(None, "--reference", help="Compare against another SST")

_SEVERITY_ORDER: dict[Severity, int] = {"info": 0, "warn": 1, "error": 2}
_DNT_TERMS: list[str] = ["SKSE", "F4SE", "SFSE", "FOSE", "NVSE", "OBSE", "SkyUI", "MCM"]


@validate_app.command("project")
def validate_project(
    project: str = PROJECT_ARGUMENT,
    json_output: bool = typer.Option(True, "--json/--text"),
) -> None:
    """Audit a project: orphans, partial entries, validator gate failures replayed."""

    project_root = paths.project_root(project)
    if not project_root.exists():
        _emit_failure("project_not_found", f"Project not found: {project}", {"project": project})
    conn = open_memory_db(project_root)
    try:
        rows = _all_units(conn)
    finally:
        conn.close()
    project_data = _read_project_toml(project_root)
    game = _project_game(project_data)

    findings = {
        "orphans": _find_orphans(rows),
        "partials": _find_partials(rows),
        "validator_replay": _replay_validators(rows),
        "cache_freshness": _check_cache_freshness(project_root, project_data),
        "coverage_gaps": _find_coverage_gaps(rows, game),
    }
    severity = _overall_severity(findings)
    data = {"project": project, "severity": severity, "findings": findings}
    if json_output:
        _emit_success(data)
        return
    _emit_text(data)


@validate_app.command("sst")
def validate_sst(
    sst_path: Path = SST_ARGUMENT,
    reference_path: Path | None = REFERENCE_OPTION,
) -> None:
    """Validate an SST file via round-trip read+write; optional byte-diff against reference."""

    if not sst_path.exists():
        _emit_failure("sst_not_found", f"SST not found: {sst_path}", {"sst": str(sst_path)})
    try:
        decoded = read_sst(sst_path)
        with tempfile.TemporaryDirectory(prefix="bgs-translator-sst-") as tmpdir:
            rewritten = Path(tmpdir) / sst_path.name
            write_sst(
                rewritten,
                decoded.entries,
                decoded.masters,
                colab_labels=decoded.colab_labels,
                sst_version=_writable_version(decoded.label),
            )
            original_bytes = sst_path.read_bytes()
            rewritten_bytes = rewritten.read_bytes()
            byte_identical = original_bytes == rewritten_bytes
    except Exception as exc:
        _emit_failure("sst_validation_failed", str(exc), {"sst": str(sst_path)})

    reference_identical: bool | None = None
    differing_entries: list[dict[str, Any]] | None = None
    if reference_path is not None:
        if not reference_path.exists():
            _emit_failure(
                "reference_not_found",
                f"Reference SST not found: {reference_path}",
                {"reference": str(reference_path)},
            )
        reference_identical = sst_path.read_bytes() == reference_path.read_bytes()
        differing_entries = _diff_reference_entries(decoded.entries, read_sst(reference_path).entries)

    signatures = sorted({entry.signature for entry in decoded.entries})
    _emit_success(
        {
            "round_trip_ok": True,
            "byte_identical": byte_identical,
            "version": decoded.label,
            "entry_count": len(decoded.entries),
            "masters": decoded.masters,
            "signatures": signatures,
            "reference_byte_identical": reference_identical,
            "reference_differing_entries": differing_entries,
        }
    )


def _all_units(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
               index_n, index_max, source, list_index, strid, dest, status, updated_at, sparams
        FROM units
        ORDER BY signature, field, formid, index_n
        """
    ).fetchall()
    return [_row_to_unit(row) for row in rows]


def _find_orphans(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    findings: list[dict[str, Any]] = []
    for row in rows:
        status = str(row["status"])
        updated_at = _parse_datetime(str(row["updated_at"]))
        if status == "orphan" or (status == "untranslated" and updated_at < cutoff):
            findings.append(_finding(row, "info", "orphan or stale untranslated unit"))
    return findings


def _find_partials(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _finding(row, "info", "partial or incomplete translation")
        for row in rows
        if str(row["status"]) == "partial"
        or int(row["sparams"]) & int(SStrParam.INCOMPLETE_TRANS)
    ]


def _replay_validators(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        dest = row.get("dest")
        if not isinstance(dest, str) or dest == "":
            continue
        unit = TranslationUnit(
            plugin=str(row["plugin"]),
            formid=int(row["formid_int"]),
            formid_sanitized=int(row["formid_sanitized_int"]),
            edid=row["edid"] if isinstance(row["edid"], str) else None,
            signature=str(row["signature"]),
            field=str(row["field"]),
            source=str(row["source"]),
            index_n=int(row["index"]),
            index_max=int(row["index_max"]),
            list_index=int(row["list_index"]),
            strid=int(row["strid"]),
        )
        masked = build_masked_unit(unit)
        result = validate_item(masked, dest, _DNT_TERMS, ["utf-8"])
        hard_failures = [failure_item for failure_item in result.failures if not failure_item.soft]
        if hard_failures:
            findings.append(
                _finding(
                    row,
                    "error",
                    "validator replay failed",
                    gates=[failure_item.model_dump() for failure_item in hard_failures],
                )
            )
    return findings


def _check_cache_freshness(
    project_root: Path, project_data: dict[str, Any]
) -> list[dict[str, Any]]:
    project_block = project_data.get("project", {})
    if not isinstance(project_block, dict):
        return [_plain_finding("warn", "project.toml missing [project] block")]
    plugin_path_raw = project_block.get("source_plugin_path")
    if not isinstance(plugin_path_raw, str) or not plugin_path_raw:
        return [_plain_finding("warn", "project.toml has no source_plugin_path")]
    plugin_path = Path(plugin_path_raw)
    if not plugin_path.exists():
        return [_plain_finding("warn", f"source plugin is missing: {plugin_path}")]
    actual_sha = _sha256(plugin_path)
    expected_shas: list[tuple[str, str]] = []
    source_sha = project_block.get("source_plugin_sha256")
    if isinstance(source_sha, str) and source_sha:
        expected_shas.append(("project.toml", source_sha))
    for cache_file in sorted((project_root / "sources").glob("*.cache.toml")):
        data = _read_toml(cache_file)
        cache_sha = data.get("plugin_sha256")
        if isinstance(cache_sha, str) and cache_sha:
            expected_shas.append((cache_file.name, cache_sha))
    return [
        _plain_finding(
            "warn",
            f"plugin sha drift in {source}: expected {expected}, actual {actual_sha}",
            source=source,
            expected_sha256=expected,
            actual_sha256=actual_sha,
        )
        for source, expected in expected_shas
        if expected != actual_sha
    ]


def _find_coverage_gaps(rows: list[dict[str, Any]], game: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    schema = get_schema_for_game(game)
    actual_fields: dict[str, set[str]] = defaultdict(set)
    actual_counts = Counter(str(row["signature"]) for row in rows)
    for row in rows:
        actual_fields[str(row["signature"])].add(str(row["field"]))
    findings: list[dict[str, Any]] = []
    for signature in sorted(actual_fields):
        expected = {field.subrecord_sig for field in schema.get_translatable_subrecords(signature)}
        if not expected:
            continue
        missing = sorted(expected - actual_fields[signature])
        if missing:
            findings.append(
                _plain_finding(
                    "info",
                    f"signature {signature} lacks expected fields from schema",
                    signature=signature,
                    actual_count=int(actual_counts[signature]),
                    observed_fields=sorted(actual_fields[signature]),
                    missing_expected_fields=missing,
                )
            )
    return findings


def _diff_reference_entries(
    entries: list[SSTUnit], reference_entries: list[SSTUnit]
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    max_len = max(len(entries), len(reference_entries))
    for index in range(max_len):
        left = entries[index] if index < len(entries) else None
        right = reference_entries[index] if index < len(reference_entries) else None
        if left != right:
            diffs.append(
                {
                    "index": index,
                    "left": None if left is None else _sst_unit_key(left),
                    "right": None if right is None else _sst_unit_key(right),
                }
            )
    return diffs


def _sst_unit_key(unit: SSTUnit) -> dict[str, Any]:
    return {
        "signature": unit.signature,
        "field": unit.field,
        "formid": f"0x{unit.formid:08X}",
        "index": unit.index,
        "source": unit.source,
        "dest": unit.dest,
    }


def _writable_version(label: str) -> Literal["SSU8", "SSU9"]:
    if label not in {"SSU8", "SSU9"}:
        raise ValueError(f"round-trip writing is only supported for SSU8/SSU9, got {label}")
    return "SSU9" if label == "SSU9" else "SSU8"


def _project_game(project_data: dict[str, Any]) -> str:
    project_block = project_data.get("project", {})
    if isinstance(project_block, dict):
        game = project_block.get("game")
        if isinstance(game, str) and game:
            return game
    return "Starfield"


def _read_project_toml(project_root: Path) -> dict[str, Any]:
    path = project_root / "project.toml"
    if not path.exists():
        return {}
    return _read_toml(path)


def _read_toml(path: Path) -> dict[str, Any]:
    loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _row_to_unit(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    return {
        "row_id": row[0],
        "plugin": row[1],
        "formid": f"0x{int(row[2]):08X}",
        "formid_int": int(row[2]),
        "formid_sanitized": f"0x{int(row[3]):06X}",
        "formid_sanitized_int": int(row[3]),
        "edid": row[4],
        "signature": row[5],
        "field": row[6],
        "index": row[7],
        "index_max": row[8],
        "source": row[9],
        "list_index": row[10],
        "strid": row[11],
        "dest": row[12],
        "status": row[13],
        "updated_at": row[14],
        "sparams": row[15],
    }


def _finding(
    row: dict[str, Any], severity: Severity, message: str, **extra: Any
) -> dict[str, Any]:
    return {
        "severity": severity,
        "message": message,
        "row_id": row["row_id"],
        "signature": row["signature"],
        "field": row["field"],
        "status": row["status"],
        **extra,
    }


def _plain_finding(severity: Severity, message: str, **extra: Any) -> dict[str, Any]:
    return {"severity": severity, "message": message, **extra}


def _overall_severity(findings: dict[str, list[dict[str, Any]]]) -> Severity:
    severity: Severity = "info"
    for group in findings.values():
        for item in group:
            raw = item.get("severity", "info")
            candidate: Severity = raw if raw in _SEVERITY_ORDER else "info"
            if _SEVERITY_ORDER[candidate] > _SEVERITY_ORDER[severity]:
                severity = candidate
    return severity


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _emit_text(data: dict[str, Any]) -> None:
    typer.echo(f"severity: {data['severity']}")
    findings = data.get("findings", {})
    if isinstance(findings, dict):
        for name, items in findings.items():
            typer.echo(f"{name}: {len(items) if isinstance(items, list) else 0}")


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> NoReturn:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["validate_app"]
