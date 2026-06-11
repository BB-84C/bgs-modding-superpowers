"""Edit CLI commands for translation-memory updates."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import typer

from bgs_translator.cli.envelopes import Envelope, failure, success
from bgs_translator.config import paths
from bgs_translator.core.memory import open_memory_db
from bgs_translator.sst.status import SStrParam

edit_app = typer.Typer(no_args_is_help=True)

PROJECT_ARGUMENT = typer.Argument(...)
ROW_ID_ARGUMENT = typer.Argument(...)
DEST_OPTION = typer.Option(..., "--dest", help="New destination text")
STATUS_OPTION = typer.Option(None, "--status", help="translated | partial | locked")
REASON_OPTION = typer.Option("", "--reason", help="Audit-trail note")
INPUT_OPTION = typer.Option(..., "--input", "-i", help="JSONL edit file")
SIG_FILTER_OPTION = typer.Option(None, "--sig")
FIELD_FILTER_OPTION = typer.Option(None, "--field")
CURRENT_STATUS_OPTION = typer.Option(None, "--current-status")
YES_OPTION = typer.Option(False, "--yes")

VALID_STATUSES: set[str] = {"translated", "partial", "locked"}


@edit_app.command("entry")
def edit_entry(
    project: str = PROJECT_ARGUMENT,
    row_id: str = ROW_ID_ARGUMENT,
    dest: str = DEST_OPTION,
    status: str | None = STATUS_OPTION,
    reason: str = REASON_OPTION,
) -> None:
    """Update a single TranslationUnit's dest + status in memory.sqlite."""

    project_root = _project_root_or_exit(project)
    conn = open_memory_db(project_root)
    try:
        before = _get_unit_or_exit(conn, row_id)
        new_status = _validated_status(status) if status is not None else str(before["status"])
        conn.execute("BEGIN")
        after = _apply_edit(conn, row_id, dest=dest, status=new_status)
        conn.commit()
        _append_audit(project_root, row_id=row_id, before=before, after=after, reason=reason)
    except sqlite3.Error as exc:
        conn.rollback()
        _emit_failure("memory_update_failed", str(exc), {"row_id": row_id})
    finally:
        conn.close()

    _emit_success({"project": project, "unit": after})


@edit_app.command("bulk")
def edit_bulk(
    project: str = PROJECT_ARGUMENT,
    input_file: Path = INPUT_OPTION,
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Apply many edits at once. JSONL format for streamability."""

    if not input_file.exists():
        _emit_failure("input_not_found", f"Input file not found: {input_file}", {"input": str(input_file)})

    project_root = _project_root_or_exit(project)
    conn = open_memory_db(project_root)
    applied_count = 0
    would_apply_count = 0
    errors: list[dict[str, Any]] = []
    try:
        for line_no, raw_line in _iter_jsonl(input_file):
            try:
                payload = _parse_bulk_payload(raw_line)
                before = _get_unit(conn, payload["row_id"])
                if before is None:
                    raise ValueError(f"entry not found: {payload['row_id']}")
                status = payload.get("status")
                new_status = _validated_status(status) if status is not None else str(before["status"])
                if dry_run:
                    would_apply_count += 1
                    continue
                conn.execute("BEGIN")
                after = _apply_edit(conn, payload["row_id"], dest=payload["dest"], status=new_status)
                conn.commit()
                _append_audit(
                    project_root,
                    row_id=payload["row_id"],
                    before=before,
                    after=after,
                    reason=str(payload.get("reason", "")),
                )
                applied_count += 1
            except (json.JSONDecodeError, ValueError, sqlite3.Error) as exc:
                conn.rollback()
                errors.append({"line": line_no, "error": str(exc)})
    finally:
        conn.close()

    _emit_success(
        {
            "project": project,
            "applied_count": applied_count,
            "would_apply_count": would_apply_count,
            "skipped_count": len(errors),
            "errors": errors,
        }
    )


@edit_app.command("status")
def edit_status(
    project: str = PROJECT_ARGUMENT,
    new_status: str = typer.Argument(...),
    sig: list[str] | None = SIG_FILTER_OPTION,
    field: list[str] | None = FIELD_FILTER_OPTION,
    current_status: str | None = CURRENT_STATUS_OPTION,
    yes: bool = YES_OPTION,
) -> None:
    """Bulk status update by filter. Use --yes to skip confirmation."""

    status = _validated_status(new_status)
    project_root = _project_root_or_exit(project)
    conn = open_memory_db(project_root)
    where, params = _filter_where(sig=sig, field=field, current_status=current_status)
    try:
        count = int(conn.execute(f"SELECT COUNT(*) FROM units {where}", params).fetchone()[0])
        sample_rows = conn.execute(
            f"""
            SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
                   index_n, index_max, source, list_index, strid, dest, status, updated_at, sparams
            FROM units {where}
            ORDER BY signature, field, formid, index_n
            LIMIT 10
            """,
            params,
        ).fetchall()
        sample = [_row_to_unit(row) for row in sample_rows]
        if not yes:
            typer.echo(json.dumps({"matched": count, "sample": sample}, ensure_ascii=False, indent=2))
            if not typer.confirm("Apply status update?"):
                _emit_success({"project": project, "affected_count": 0})
                return
        now = _now()
        cursor = conn.execute(
            f"""
            UPDATE units
            SET status = ?, sparams = ?, via_llm = 0, profile_used = 'manual-edit', updated_at = ?
            {where}
            """,
            [status, _sparams_for_status(status), now, *params],
        )
        conn.commit()
        _emit_success({"project": project, "affected_count": int(cursor.rowcount)})
    finally:
        conn.close()


@edit_app.command("revert")
def edit_revert(
    project: str = PROJECT_ARGUMENT,
    row_id: str = ROW_ID_ARGUMENT,
    audit_entry: str | None = typer.Option(
        None, "--audit-entry", help="Specific audit JSONL entry to revert to"
    ),
) -> None:
    """Revert to the last (or specified) audit entry."""

    project_root = _project_root_or_exit(project)
    audit = _find_audit_entry(project_root, row_id=row_id, audit_entry=audit_entry)
    if audit is None:
        _emit_failure("audit_entry_not_found", f"No manual edit audit for {row_id}", {"row_id": row_id})
    target = audit["before"]
    if not isinstance(target, dict):
        _emit_failure("invalid_audit_entry", "Audit entry has no before state", {"row_id": row_id})
    conn = open_memory_db(project_root)
    try:
        before = _get_unit_or_exit(conn, row_id)
        conn.execute("BEGIN")
        after = _apply_edit(
            conn,
            row_id,
            dest=_nullable_str(target.get("dest")),
            status=str(target.get("status", "untranslated")),
        )
        conn.commit()
        _append_audit(
            project_root,
            row_id=row_id,
            before=before,
            after=after,
            reason=f"revert to audit {audit.get('audit_id', '')}",
            operation="revert",
        )
    except sqlite3.Error as exc:
        conn.rollback()
        _emit_failure("memory_update_failed", str(exc), {"row_id": row_id})
    finally:
        conn.close()
    _emit_success({"project": project, "unit": after})


def _iter_jsonl(path: Path) -> Iterable[tuple[int, str]]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            yield line_no, line


def _parse_bulk_payload(line: str) -> dict[str, str]:
    raw = json.loads(line)
    if not isinstance(raw, dict):
        raise ValueError("line must be a JSON object")
    row_id = raw.get("row_id")
    dest = raw.get("dest")
    if not isinstance(row_id, str) or not row_id:
        raise ValueError("row_id must be a non-empty string")
    if not isinstance(dest, str):
        raise ValueError("dest must be a string")
    parsed: dict[str, str] = {"row_id": row_id, "dest": dest}
    for key in ("status", "reason"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string when present")
            parsed[key] = value
    return parsed


def _project_root_or_exit(project: str) -> Path:
    project_root = paths.project_root(project)
    if not project_root.exists():
        _emit_failure("project_not_found", f"Project not found: {project}", {"project": project})
    return project_root


def _get_unit_or_exit(conn: sqlite3.Connection, row_id: str) -> dict[str, Any]:
    row = _get_unit(conn, row_id)
    if row is None:
        _emit_failure("entry_not_found", f"Entry not found: {row_id}", {"row_id": row_id})
    return row


def _get_unit(conn: sqlite3.Connection, row_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
               index_n, index_max, source, list_index, strid, dest, status, updated_at, sparams
        FROM units
        WHERE row_id = ?
        """,
        (row_id,),
    ).fetchone()
    return None if row is None else _row_to_unit(row)


def _apply_edit(conn: sqlite3.Connection, row_id: str, *, dest: str | None, status: str) -> dict[str, Any]:
    now = _now()
    conn.execute(
        """
        UPDATE units
        SET dest = ?, status = ?, sparams = ?, via_llm = 0, profile_used = 'manual-edit', updated_at = ?
        WHERE row_id = ?
        """,
        (dest, status, _sparams_for_status(status), now, row_id),
    )
    after = _get_unit(conn, row_id)
    if after is None:
        raise sqlite3.IntegrityError(f"entry disappeared during update: {row_id}")
    return after


def _sparams_for_status(status: str) -> int:
    mapping = {
        "translated": SStrParam.TRANSLATED,
        "partial": SStrParam.INCOMPLETE_TRANS,
        "locked": SStrParam.LOCKED_TRANS,
        "untranslated": SStrParam.NONE,
    }
    return int(mapping.get(status, SStrParam.NONE))


def _validated_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in VALID_STATUSES:
        raise typer.BadParameter(f"status must be one of {sorted(VALID_STATUSES)}")
    return normalized


def _filter_where(
    *, sig: list[str] | None, field: list[str] | None, current_status: str | None
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if sig:
        clauses.append(f"signature IN ({','.join('?' for _ in sig)})")
        params.extend(item.upper() for item in sig)
    if field:
        clauses.append(f"field IN ({','.join('?' for _ in field)})")
        params.extend(item.upper() for item in field)
    if current_status is not None:
        clauses.append("status = ?")
        params.append(current_status.lower())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _append_audit(
    project_root: Path,
    *,
    row_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
    operation: str = "edit",
) -> None:
    timestamp = _now()
    audit_dir = project_root / "batches" / "manual-edits"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"{timestamp[:10]}.jsonl"
    entry = {
        "audit_id": uuid.uuid4().hex,
        "operation": operation,
        "row_id": row_id,
        "before": before,
        "after": after,
        "reason": reason,
        "timestamp": timestamp,
    }
    with audit_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _find_audit_entry(
    project_root: Path, *, row_id: str, audit_entry: str | None
) -> dict[str, Any] | None:
    matches = [entry for entry in _iter_audit_entries(project_root) if entry.get("row_id") == row_id]
    if audit_entry is not None:
        for entry in matches:
            if audit_entry in {str(entry.get("audit_id", "")), str(entry.get("timestamp", ""))}:
                return entry
        candidate = Path(audit_entry)
        if candidate.exists():
            for raw_line in candidate.read_text(encoding="utf-8").splitlines():
                entry = json.loads(raw_line)
                if isinstance(entry, dict) and entry.get("row_id") == row_id:
                    return entry
        return None
    return matches[-1] if matches else None


def _iter_audit_entries(project_root: Path) -> Iterable[dict[str, Any]]:
    audit_dir = project_root / "batches" / "manual-edits"
    if not audit_dir.exists():
        return
    for path in sorted(audit_dir.glob("*.jsonl")):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            loaded = json.loads(raw_line)
            if isinstance(loaded, dict):
                yield loaded


def _nullable_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _row_to_unit(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    return {
        "row_id": row[0],
        "plugin": row[1],
        "formid": f"0x{int(row[2]):08X}",
        "formid_sanitized": f"0x{int(row[3]):06X}",
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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _emit_success(data: dict[str, Any]) -> None:
    _echo_envelope(success(data))


def _emit_failure(code: str, message: str, details: dict[str, Any]) -> NoReturn:
    _echo_envelope(failure(code, message, details=details))
    raise typer.Exit(1)


def _echo_envelope(envelope: Envelope) -> None:
    typer.echo(json.dumps(envelope.model_dump(), ensure_ascii=False, indent=2))


__all__ = ["edit_app"]
