"""Tests for batch-side extraction from memory.sqlite."""

from __future__ import annotations

from pathlib import Path


def test_collect_units_for_run_filters_and_deduplicates(tmp_path: Path) -> None:
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.pipeline.extractor import collect_units_for_run

    conn = open_memory_db(tmp_path)
    insert_units(
        conn,
        [
            TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Sword"),
            TranslationUnit("A.esp", 2, 2, "B", "WEAP", "FULL", source="Sword"),
            TranslationUnit("A.esp", 3, 3, "C", "ARMO", "FULL", source="Armor"),
        ],
    )
    conn.execute("UPDATE units SET status = 'translated' WHERE formid = 3")

    units = collect_units_for_run(
        conn,
        statuses=["untranslated"],
        signatures=["WEAP"],
        fields=["FULL"],
    )

    assert len(units) == 1
    assert units[0].source == "Sword"
