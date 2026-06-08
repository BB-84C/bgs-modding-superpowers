"""SQLite-backed translation memory ownership."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bgs_translator.parsers.tes4_family import TranslationUnit

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);

CREATE TABLE IF NOT EXISTS units (
    row_id TEXT PRIMARY KEY,
    plugin TEXT NOT NULL,
    formid INTEGER NOT NULL,
    formid_sanitized INTEGER NOT NULL,
    edid TEXT,
    signature TEXT NOT NULL,
    field TEXT NOT NULL,
    index_n INTEGER NOT NULL DEFAULT 0,
    index_max INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    list_index INTEGER NOT NULL,
    strid INTEGER NOT NULL DEFAULT 0,
    rhash INTEGER NOT NULL,
    parent_context_json TEXT,
    dest TEXT,
    status TEXT NOT NULL,
    sparams INTEGER NOT NULL,
    via_llm BOOLEAN NOT NULL DEFAULT 0,
    profile_used TEXT,
    sdk_via TEXT,
    cost_estimate_usd REAL,
    cost_exact BOOLEAN,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_batch_id TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_units_signature ON units(signature, field);
CREATE INDEX IF NOT EXISTS idx_units_status ON units(status);
CREATE INDEX IF NOT EXISTS idx_units_edid ON units(edid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_units_natural
    ON units(plugin, formid, signature, field, index_n);

CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    profile_snapshot_json TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    cost_exact BOOLEAN,
    retry_count INTEGER DEFAULT 0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_batches_run ON batches(run_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    batches_total INTEGER NOT NULL,
    cost_total_usd REAL,
    cost_exact BOOLEAN
);
"""


def open_memory_db(project_root: Path) -> sqlite3.Connection:
    """Open or create ``memory/memory.sqlite`` under ``project_root``."""

    memory_dir = project_root / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(memory_dir / "memory.sqlite")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    version_count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    if version_count == 0:
        conn.execute("INSERT INTO schema_version VALUES (1)")
    conn.commit()
    return conn


def insert_units(conn: sqlite3.Connection, units: Iterable[TranslationUnit]) -> int:
    """Bulk insert translation units as untranslated rows, ignoring duplicates."""

    inserted = 0
    now = datetime.now(UTC).isoformat()
    for unit in units:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO units (
                row_id, plugin, formid, formid_sanitized, edid, signature, field,
                index_n, index_max, source, list_index, strid, rhash,
                parent_context_json, dest, status, sparams, via_llm, retry_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"r_{uuid.uuid4().hex}",
                unit.plugin,
                unit.formid,
                unit.formid_sanitized,
                unit.edid,
                unit.signature,
                unit.field,
                unit.index_n,
                unit.index_max,
                unit.source,
                unit.list_index,
                unit.strid,
                0,
                None,
                None,
                "untranslated",
                0,
                0,
                0,
                now,
            ),
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted


def update_unit_translation(
    conn: sqlite3.Connection,
    *,
    row_id: str,
    dest: str,
    status: str,
    sparams: int,
    via_llm: bool,
    profile_used: str | None,
    sdk_via: str,
    cost_estimate_usd: float | None,
    cost_exact: bool,
    retry_count: int,
    last_batch_id: str,
) -> None:
    """Persist a translated unit's dest and provenance back to memory.sqlite."""

    cursor = conn.execute(
        """
        UPDATE units SET
            dest = ?, status = ?, sparams = ?, via_llm = ?,
            profile_used = ?, sdk_via = ?, cost_estimate_usd = ?,
            cost_exact = ?, retry_count = ?, last_batch_id = ?,
            updated_at = ?
        WHERE row_id = ?
        """,
        (
            dest,
            status,
            sparams,
            1 if via_llm else 0,
            profile_used,
            sdk_via,
            cost_estimate_usd,
            1 if cost_exact else 0,
            retry_count,
            last_batch_id,
            datetime.now(UTC).isoformat(),
            row_id,
        ),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError(f"No memory.sqlite unit row updated for row_id={row_id!r}")
    conn.commit()


def get_unit_counts_by_signature(conn: sqlite3.Connection) -> dict[str, int]:
    """Return diagnostic unit counts grouped by record signature."""

    rows = conn.execute(
        "SELECT signature, COUNT(*) FROM units GROUP BY signature ORDER BY signature"
    ).fetchall()
    return {str(signature): int(count) for signature, count in rows}


def list_units(
    conn: sqlite3.Connection,
    *,
    sig: str | None = None,
    field: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return units with optional filters."""

    clauses: list[str] = []
    params: list[Any] = []
    if sig is not None:
        clauses.append("signature = ?")
        params.append(sig.upper())
    if field is not None:
        clauses.append("field = ?")
        params.append(field.upper())
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
               index_n, index_max, source, list_index, strid, dest, status, updated_at
        FROM units
        {where}
        ORDER BY signature, field, formid, index_n
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def count_units(
    conn: sqlite3.Connection,
    *,
    sig: str | None = None,
    field: str | None = None,
    status: str | None = None,
) -> int:
    """Count units with optional filters."""

    clauses: list[str] = []
    params: list[Any] = []
    if sig is not None:
        clauses.append("signature = ?")
        params.append(sig.upper())
    if field is not None:
        clauses.append("field = ?")
        params.append(field.upper())
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return int(conn.execute(f"SELECT COUNT(*) FROM units {where}", params).fetchone()[0])


def get_unit_by_row_id(conn: sqlite3.Connection, row_id: str) -> dict[str, Any] | None:
    """Return one unit by stable row id."""

    row = conn.execute(
        """
        SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
               index_n, index_max, source, list_index, strid, dest, status, updated_at
        FROM units
        WHERE row_id = ?
        """,
        (row_id,),
    ).fetchone()
    return None if row is None else _row_to_dict(row)


def select_units_filtered(
    conn: sqlite3.Connection,
    *,
    sigs: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    statuses: Sequence[str] | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """SELECT units with composable WHERE clauses for GUI filtering."""

    conn.row_factory = sqlite3.Row
    clauses: list[str] = []
    params: list[Any] = []

    normalized_sigs = _normalized_filter_values(sigs, upper=True)
    if normalized_sigs:
        clauses.append(f"signature IN ({','.join('?' for _ in normalized_sigs)})")
        params.extend(normalized_sigs)

    normalized_fields = _normalized_filter_values(fields, upper=True)
    if normalized_fields:
        clauses.append(f"field IN ({','.join('?' for _ in normalized_fields)})")
        params.extend(normalized_fields)

    normalized_statuses = _normalized_filter_values(statuses, upper=False)
    if normalized_statuses:
        clauses.append(f"status IN ({','.join('?' for _ in normalized_statuses)})")
        params.extend(normalized_statuses)

    if search is not None and search.strip():
        needle = f"%{search.strip().lower()}%"
        clauses.append(
            "(lower(coalesce(edid, '')) LIKE ? OR lower(source) LIKE ? "
            "OR lower(coalesce(dest, '')) LIKE ? OR lower(row_id) LIKE ?)"
        )
        params.extend([needle, needle, needle, needle])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    rows = conn.execute(
        f"""
        SELECT row_id, plugin, formid, formid_sanitized, edid, signature, field,
               index_n, index_max, source, list_index, strid, rhash,
               parent_context_json, dest, status, sparams, via_llm, profile_used,
               sdk_via, cost_estimate_usd, cost_exact, retry_count, last_batch_id,
               updated_at
        FROM units
        {where}
        ORDER BY signature, field, formid, index_n
        {limit_clause}
        """,
        params,
    ).fetchall()
    return list(rows)


def select_batches_for_run(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    """SELECT all batches belonging to one run."""

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT batch_id, run_id, plan_id, profile_snapshot_json, item_count,
               started_at, completed_at, status, tokens_in, tokens_out, cost_usd,
               cost_exact, retry_count, notes
        FROM batches
        WHERE run_id = ?
        ORDER BY started_at IS NULL, started_at, batch_id
        """,
        (run_id,),
    ).fetchall()
    return list(rows)


def list_recent_runs(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    """Return recent runs newest-first."""

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT run_id, project, plan_id, started_at, completed_at, status,
               batches_total, cost_total_usd, cost_exact
        FROM runs
        ORDER BY started_at DESC, run_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return list(rows)


def _normalized_filter_values(values: Sequence[str] | None, *, upper: bool) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        item = value.strip()
        if not item or item.lower() == "all":
            continue
        normalized.append(item.upper() if upper else item.lower())
    return normalized


def _row_to_dict(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
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
    }


__all__ = [
    "count_units",
    "get_unit_by_row_id",
    "get_unit_counts_by_signature",
    "insert_units",
    "list_recent_runs",
    "list_units",
    "open_memory_db",
    "select_batches_for_run",
    "select_units_filtered",
    "update_unit_translation",
]
