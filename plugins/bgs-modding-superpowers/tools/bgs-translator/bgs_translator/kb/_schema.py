"""Expected bgs-kb pack SQLite schema for glossary-entry records.

This schema is the contract between bgs-translator (Chunk G) and bgs-kb-side
prep (AMENDMENTS §4.2). Translator reads from these tables; bgs-kb's build
pipeline writes them.

Source of truth: this module. If bgs-kb-side prep diverges, update here AND
file an AMENDMENT.
"""

from __future__ import annotations

import sqlite3

EXPECTED_TABLES = {
    "glossary_entries": """
        CREATE TABLE IF NOT EXISTS glossary_entries (
            record_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            scope TEXT NOT NULL,          -- 'vanilla' | 'mod' | 'player' | 'do_not_translate'
            scope_key TEXT,                -- mod slug for scope='mod'; NULL otherwise
            category TEXT,                 -- character | faction | place | item | spell | lore_term | ui_label | brand
            confidence TEXT NOT NULL,      -- canonical | preferred | candidate
            notes TEXT
        );
    """,
    "glossary_aliases": """
        CREATE TABLE IF NOT EXISTS glossary_aliases (
            record_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            alias_kind TEXT NOT NULL,      -- 'source' | 'target'
            FOREIGN KEY (record_id) REFERENCES glossary_entries(record_id)
        );
        CREATE INDEX IF NOT EXISTS idx_glossary_aliases_alias_lower
            ON glossary_aliases(LOWER(alias));
    """,
    # The translator also queries existing tables for filtering:
    "record_games": """
        CREATE TABLE IF NOT EXISTS record_games (
            record_id TEXT NOT NULL,
            game TEXT NOT NULL,
            confidence TEXT,
            PRIMARY KEY (record_id, game)
        );
    """,
    # And the existing records table for kind filtering:
    "records": """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            pack_id TEXT NOT NULL,
            kind TEXT NOT NULL,            -- 'glossary-entry' for our queries
            title TEXT,
            body_md TEXT
        );
    """,
}


def apply_stub_schema(conn: sqlite3.Connection) -> None:
    """Apply the expected schema to a SQLite connection for fixture pack DBs."""
    for statement in EXPECTED_TABLES.values():
        conn.executescript(statement)


__all__ = ["EXPECTED_TABLES", "apply_stub_schema"]
