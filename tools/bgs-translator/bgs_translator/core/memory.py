"""SQLite-backed translation memory ownership."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

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


def get_unit_counts_by_signature(conn: sqlite3.Connection) -> dict[str, int]:
    """Return diagnostic unit counts grouped by record signature."""

    rows = conn.execute(
        "SELECT signature, COUNT(*) FROM units GROUP BY signature ORDER BY signature"
    ).fetchall()
    return {str(signature): int(count) for signature, count in rows}


__all__ = ["get_unit_counts_by_signature", "insert_units", "open_memory_db"]
