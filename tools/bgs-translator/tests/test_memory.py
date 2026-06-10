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

    rows = conn.execute(
        "SELECT plugin, formid, signature, field, source, status FROM units"
    ).fetchall()
    assert len(rows) == 3
    assert rows[0][5] == "untranslated"
    assert get_unit_counts_by_signature(conn) == {"ARMO": 1, "WEAP": 2}


def test_memory_rescan_refreshes_parser_metadata_without_clobbering_translation(
    tmp_path: Path,
) -> None:
    from bgs_translator.core.memory import (
        insert_units,
        open_memory_db,
        update_unit_translation,
    )
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = open_memory_db(tmp_path)
    old_unit = TranslationUnit(
        "A.esm",
        1,
        1,
        "WeaponEdid",
        "WEAP",
        "FULL",
        source="Old Source",
        index_n=0,
        index_max=0,
        list_index=0,
        strid=1001,
    )
    assert insert_units(conn, [old_unit]) == 1
    row_id = str(conn.execute("SELECT row_id FROM units").fetchone()[0])
    update_unit_translation(
        conn,
        row_id=row_id,
        dest="旧译文",
        status="translated",
        sparams=0,
        via_llm=True,
        profile_used="profile",
        sdk_via="synthetic",
        cost_estimate_usd=None,
        cost_exact=False,
        retry_count=0,
        last_batch_id="batch-a",
    )

    refreshed_unit = TranslationUnit(
        "A.esm",
        1,
        1,
        "WeaponEdid",
        "WEAP",
        "FULL",
        source="Standard",
        index_n=0,
        index_max=21,
        list_index=0,
        strid=2001,
    )
    assert insert_units(conn, [refreshed_unit]) == 0

    row = conn.execute(
        """
        SELECT source, strid, index_max, dest, status
        FROM units
        WHERE row_id = ?
        """,
        (row_id,),
    ).fetchone()
    assert row == ("Standard", 2001, 21, "旧译文", "translated")


def test_discard_run_translations_clears_only_matching_run(tmp_path: Path) -> None:
    from bgs_translator.core.memory import (
        discard_run_translations,
        insert_run,
        insert_units,
        open_memory_db,
        update_unit_translation,
    )
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = open_memory_db(tmp_path)
    insert_units(
        conn,
        [
            TranslationUnit("A.esm", 1, 1, "A", "WEAP", "FULL", source="Sword"),
            TranslationUnit("A.esm", 2, 2, "B", "ARMO", "FULL", source="Armor"),
        ],
    )
    row_ids = [
        str(row[0]) for row in conn.execute("SELECT row_id FROM units ORDER BY formid").fetchall()
    ]
    insert_run(conn, "run-a", "plan", "2026-06-09T00:00:00+00:00", 1, project="demo")
    update_unit_translation(
        conn,
        row_id=row_ids[0],
        dest="剑",
        status="translated",
        sparams=0,
        via_llm=True,
        profile_used="profile",
        sdk_via="synthetic",
        cost_estimate_usd=0.01,
        cost_exact=True,
        retry_count=0,
        last_batch_id="batch-a",
        last_run_id="run-a",
    )
    update_unit_translation(
        conn,
        row_id=row_ids[1],
        dest="甲",
        status="translated",
        sparams=0,
        via_llm=True,
        profile_used="profile",
        sdk_via="synthetic",
        cost_estimate_usd=0.01,
        cost_exact=True,
        retry_count=0,
        last_batch_id="batch-b",
        last_run_id="run-b",
    )

    assert discard_run_translations(conn, "run-a") == 1

    rows = conn.execute(
        "SELECT row_id, dest, status, via_llm, last_batch_id, last_run_id FROM units ORDER BY formid"
    ).fetchall()
    run_status = conn.execute("SELECT status FROM runs WHERE run_id = 'run-a'").fetchone()[0]
    assert rows[0] == (row_ids[0], None, "untranslated", 0, None, None)
    assert rows[1] == (row_ids[1], "甲", "translated", 1, "batch-b", "run-b")
    assert run_status == "discarded"


def test_update_unit_translation_derives_xtranslator_sparams(tmp_path: Path) -> None:
    from bgs_translator.core.memory import insert_units, open_memory_db, update_unit_translation
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.sst.status import SStrParam

    conn = open_memory_db(tmp_path)
    insert_units(conn, [TranslationUnit("A.esm", 1, 1, "A", "WEAP", "FULL", source="Sword")])
    row_id = str(conn.execute("SELECT row_id FROM units").fetchone()[0])

    update_unit_translation(
        conn,
        row_id=row_id,
        dest="剑",
        status="translated",
        sparams=0,
        via_llm=True,
        profile_used="profile",
        sdk_via="synthetic",
        cost_estimate_usd=None,
        cost_exact=False,
        retry_count=0,
        last_batch_id="batch-a",
    )

    assert conn.execute("SELECT sparams FROM units WHERE row_id = ?", (row_id,)).fetchone()[
        0
    ] == int(SStrParam.TRANSLATED)
