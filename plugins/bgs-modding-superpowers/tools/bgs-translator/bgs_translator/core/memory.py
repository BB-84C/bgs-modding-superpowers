"""SQLite-backed translation memory ownership."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.sst.status import normalize_params_for_status

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
    last_run_id TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_units_signature ON units(signature, field);
CREATE INDEX IF NOT EXISTS idx_units_status ON units(status);
CREATE INDEX IF NOT EXISTS idx_units_edid ON units(edid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_units_natural
    ON units(plugin, formid, signature, field, index_n);

CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT NOT NULL,
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
    notes TEXT,
    PRIMARY KEY (run_id, batch_id)
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

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    batch_id TEXT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    emitted_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);

CREATE INDEX IF NOT EXISTS idx_events_run_emitted ON events (run_id, event_id);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events (kind);
"""


def open_memory_db(project_root: Path) -> sqlite3.Connection:
    """Open or create ``memory/memory.sqlite`` under ``project_root``."""

    memory_dir = project_root / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(memory_dir / "memory.sqlite")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    _ensure_batches_composite_key(conn)
    _ensure_units_run_id_column(conn)
    version_count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    if version_count == 0:
        conn.execute("INSERT INTO schema_version VALUES (1)")
    conn.commit()
    return conn


def _ensure_batches_composite_key(conn: sqlite3.Connection) -> None:
    """Migrate legacy ``batches(batch_id PRIMARY KEY)`` to per-run keys."""

    rows = conn.execute("PRAGMA table_info(batches)").fetchall()
    if not rows:
        return
    pk_columns = [str(row[1]) for row in rows if int(row[5]) > 0]
    if pk_columns == ["run_id", "batch_id"]:
        return
    if pk_columns != ["batch_id"]:
        return
    conn.execute("ALTER TABLE batches RENAME TO batches_legacy_single_key")
    conn.execute(
        """
        CREATE TABLE batches (
            batch_id TEXT NOT NULL,
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
            notes TEXT,
            PRIMARY KEY (run_id, batch_id)
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO batches (
            batch_id, run_id, plan_id, profile_snapshot_json, item_count,
            started_at, completed_at, status, tokens_in, tokens_out, cost_usd,
            cost_exact, retry_count, notes
        )
        SELECT batch_id, run_id, plan_id, profile_snapshot_json, item_count,
               started_at, completed_at, status, tokens_in, tokens_out, cost_usd,
               cost_exact, retry_count, notes
        FROM batches_legacy_single_key
        """
    )
    conn.execute("DROP TABLE batches_legacy_single_key")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_batches_run ON batches(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status)")
    conn.commit()


def _ensure_units_run_id_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(units)").fetchall()
    column_names = {str(row[1]) for row in rows}
    if "last_run_id" not in column_names:
        conn.execute("ALTER TABLE units ADD COLUMN last_run_id TEXT")
        conn.commit()


def insert_units(conn: sqlite3.Connection, units: Iterable[TranslationUnit]) -> int:
    """Bulk insert translation units as untranslated rows.

    Existing rows keep their translation/status data, but parser-derived
    metadata is refreshed so a source rescan can repair SST pointer fields
    such as ``index_max`` after schema coverage changes.
    """

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
        if cursor.rowcount:
            inserted += 1
            continue
        conn.execute(
            """
            UPDATE units SET
                formid_sanitized = ?,
                edid = ?,
                index_max = ?,
                source = ?,
                list_index = ?,
                strid = ?,
                updated_at = ?
            WHERE plugin = ?
              AND formid = ?
              AND signature = ?
              AND field = ?
              AND index_n = ?
            """,
            (
                unit.formid_sanitized,
                unit.edid,
                unit.index_max,
                unit.source,
                unit.list_index,
                unit.strid,
                now,
                unit.plugin,
                unit.formid,
                unit.signature,
                unit.field,
                unit.index_n,
            ),
        )
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
    last_run_id: str | None = None,
) -> None:
    """Persist a translated unit's dest and provenance back to memory.sqlite."""

    normalized_sparams = int(normalize_params_for_status(status, sparams))
    cursor = conn.execute(
        """
        UPDATE units SET
            dest = ?, status = ?, sparams = ?, via_llm = ?,
            profile_used = ?, sdk_via = ?, cost_estimate_usd = ?,
            cost_exact = ?, retry_count = ?, last_batch_id = ?, last_run_id = ?,
            updated_at = ?
        WHERE row_id = ?
        """,
        (
            dest,
            status,
            normalized_sparams,
            1 if via_llm else 0,
            profile_used,
            sdk_via,
            cost_estimate_usd,
            1 if cost_exact else 0,
            retry_count,
            last_batch_id,
            last_run_id,
            datetime.now(UTC).isoformat(),
            row_id,
        ),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError(f"No memory.sqlite unit row updated for row_id={row_id!r}")
    conn.commit()


def discard_run_translations(conn: sqlite3.Connection, run_id: str) -> int:
    """Clear translations written by one completed or in-progress batch run."""

    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        UPDATE units SET
            dest = NULL,
            status = 'untranslated',
            sparams = 0,
            via_llm = 0,
            profile_used = NULL,
            sdk_via = NULL,
            cost_estimate_usd = NULL,
            cost_exact = NULL,
            retry_count = 0,
            last_batch_id = NULL,
            last_run_id = NULL,
            updated_at = ?
        WHERE last_run_id = ?
        """,
        (now, run_id),
    )
    conn.execute(
        """
        UPDATE runs SET
            status = 'discarded',
            completed_at = COALESCE(completed_at, ?)
        WHERE run_id = ?
        """,
        (now, run_id),
    )
    conn.commit()
    return int(cursor.rowcount)


def insert_run(
    conn: sqlite3.Connection,
    run_id: str,
    plan_id: str,
    started_at: str,
    batches_total: int,
    status: str = "running",
    *,
    project: str = "",
) -> None:
    """Insert or replace one run lifecycle row."""

    conn.execute(
        """
        INSERT OR REPLACE INTO runs (
            run_id, project, plan_id, started_at, completed_at, status,
            batches_total, cost_total_usd, cost_exact
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, NULL, NULL)
        """,
        (run_id, project, plan_id, started_at, status, batches_total),
    )
    conn.commit()


def update_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    finished_at: str | None,
    cost_total_usd: float | None,
    cost_exact: bool,
    succeeded: int,
    retried: int,
    manual_review: int,
    cancelled: int,
) -> None:
    """Update one run lifecycle row.

    Summary counts are accepted to keep the runner call-site explicit. The
    current PRD schema stores those counts in run sidecar artifacts rather than
    in the ``runs`` table, so only table-backed columns are updated here.
    """

    del succeeded, retried, manual_review, cancelled
    cursor = conn.execute(
        """
        UPDATE runs SET
            completed_at = ?, status = ?, cost_total_usd = ?, cost_exact = ?
        WHERE run_id = ?
        """,
        (finished_at, status, cost_total_usd, 1 if cost_exact else 0, run_id),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError(f"No memory.sqlite run row updated for run_id={run_id!r}")
    conn.commit()


def insert_batch(
    conn: sqlite3.Connection,
    batch_id: str,
    run_id: str,
    started_at: str,
    item_count: int,
    status: str = "running",
    *,
    plan_id: str = "",
    profile_snapshot_json: str = "{}",
) -> None:
    """Insert or replace one batch lifecycle row."""

    conn.execute(
        """
        INSERT OR REPLACE INTO batches (
            batch_id, run_id, plan_id, profile_snapshot_json, item_count,
            started_at, completed_at, status, tokens_in, tokens_out, cost_usd,
            cost_exact, retry_count, notes
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL, 0, NULL)
        """,
        (batch_id, run_id, plan_id, profile_snapshot_json, item_count, started_at, status),
    )
    conn.commit()


def update_batch(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    run_id: str,
    status: str,
    finished_at: str | None,
    tokens_in: int | None,
    tokens_out: int | None,
    cost_usd: float | None,
    cost_exact: bool = False,
    retry_count: int = 0,
) -> None:
    """Update one batch lifecycle row."""

    cursor = conn.execute(
        """
        UPDATE batches SET
            completed_at = ?, status = ?, tokens_in = ?, tokens_out = ?,
            cost_usd = ?, cost_exact = ?, retry_count = ?
        WHERE run_id = ? AND batch_id = ?
        """,
        (
            finished_at,
            status,
            tokens_in,
            tokens_out,
            cost_usd,
            1 if cost_exact else 0,
            retry_count,
            run_id,
            batch_id,
        ),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise ValueError(
            f"No memory.sqlite batch row updated for run_id={run_id!r} batch_id={batch_id!r}"
        )
    conn.commit()


def insert_event(conn: sqlite3.Connection, event: Any) -> int:
    """Persist one GUI event and return its autoincrement id."""

    payload = getattr(event, "payload", {}) or {}
    cursor = conn.execute(
        """
        INSERT INTO events (run_id, batch_id, kind, payload_json, emitted_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            getattr(event, "run_id", None) or "",
            getattr(event, "batch_id", None),
            str(getattr(event, "kind", "")),
            _json_dumps(payload),
            getattr(event, "timestamp", datetime.now(UTC)).isoformat(),
        ),
    )
    conn.commit()
    event_id = cursor.lastrowid
    if event_id is None:
        raise sqlite3.DatabaseError("SQLite did not return an event row id")
    return int(event_id)


def fetch_events_for_run(
    conn: sqlite3.Connection,
    run_id: str,
    since_event_id: int = 0,
) -> list[dict[str, Any]]:
    """Return persisted events for one run after ``since_event_id``."""

    rows = conn.execute(
        """
        SELECT event_id, run_id, batch_id, kind, payload_json, emitted_at
        FROM events
        WHERE run_id = ? AND event_id > ?
        ORDER BY event_id ASC
        """,
        (run_id, since_event_id),
    ).fetchall()
    return [
        {
            "event_id": int(row[0]),
            "run_id": str(row[1]),
            "batch_id": row[2],
            "kind": str(row[3]),
            "payload": _json_loads(str(row[4])),
            "emitted_at": str(row[5]),
        }
        for row in rows
    ]


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
            "OR lower(coalesce(dest, '')) LIKE ? OR lower(row_id) LIKE ? "
            "OR lower(printf('%08X', formid)) LIKE ? "
            "OR lower(printf('%06X', formid_sanitized)) LIKE ? "
            "OR CAST(strid AS TEXT) LIKE ?)"
        )
        strid_needle = f"%{search.strip()}%"
        params.extend([needle, needle, needle, needle, needle, needle, strid_needle])

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
               last_run_id,
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


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


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
    "discard_run_translations",
    "fetch_events_for_run",
    "get_unit_by_row_id",
    "get_unit_counts_by_signature",
    "insert_batch",
    "insert_event",
    "insert_run",
    "insert_units",
    "list_recent_runs",
    "list_units",
    "open_memory_db",
    "select_batches_for_run",
    "select_units_filtered",
    "update_batch",
    "update_run",
    "update_unit_translation",
]
