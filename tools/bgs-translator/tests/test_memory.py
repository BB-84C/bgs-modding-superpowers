"""Tests for translation memory persistence."""

from __future__ import annotations

from pathlib import Path


def test_memory_insert_and_counts(tmp_path: Path) -> None:
    from bgs_translator.core.memory import (
        get_unit_counts_by_signature,
        insert_units,
        open_memory_db,
    )
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = open_memory_db(tmp_path)
    units = [
        TranslationUnit("A.esm", 1, 1, "A", "WEAP", "FULL", source="Sword"),
        TranslationUnit("A.esm", 2, 2, "B", "ARMO", "FULL", source="Armor"),
        TranslationUnit("A.esm", 3, 3, "C", "WEAP", "DESC", source="Description", list_index=1),
    ]

    assert insert_units(conn, units) == 3
    assert insert_units(conn, [units[0]]) == 0

    rows = conn.execute("SELECT plugin, formid, signature, field, source, status FROM units").fetchall()
    assert len(rows) == 3
    assert rows[0][5] == "untranslated"
    assert get_unit_counts_by_signature(conn) == {"ARMO": 1, "WEAP": 2}
