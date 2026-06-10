"""Project SST export status parity with xTranslator categories."""

from __future__ import annotations

from pathlib import Path


def test_project_export_skips_untranslated_and_all_protected_rows(tmp_path: Path) -> None:
    from bgs_translator.cli.project import _read_units_from_memory, _unit_row_to_sst_unit
    from bgs_translator.core.memory import insert_units, open_memory_db, update_unit_translation
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.sst.status import SStrParam

    conn = open_memory_db(tmp_path)
    insert_units(
        conn,
        [
            TranslationUnit("du_overtime.esm", 1, 1, "RealQuest", "QUST", "FULL", source="Repair Beacon"),
            TranslationUnit("du_overtime.esm", 2, 2, "NeedsWork", "QUST", "NNAM", source="Deliver Parts"),
            TranslationUnit(
                "du_overtime.esm",
                3,
                3,
                "AliasOnly",
                "QUST",
                "QMDP",
                source="<Alias=TargetLocation>",
            ),
            TranslationUnit("du_overtime.esm", 4, 4, "NumberOnly", "QUST", "QMDP", source="15"),
        ],
    )
    row_ids = {
        str(row[1]): str(row[0])
        for row in conn.execute("SELECT row_id, edid FROM units ORDER BY formid").fetchall()
    }
    update_unit_translation(
        conn,
        row_id=row_ids["RealQuest"],
        dest="修理信标",
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
    update_unit_translation(
        conn,
        row_id=row_ids["AliasOnly"],
        dest="<Alias=TargetLocation>",
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

    units = [_unit_row_to_sst_unit(row) for row in _read_units_from_memory(conn)]

    assert [(unit.source, unit.dest, unit.s_params) for unit in units] == [
        ("Repair Beacon", "修理信标", int(SStrParam.TRANSLATED)),
        ("Deliver Parts", "Deliver Parts", int(SStrParam.PENDING)),
        ("<Alias=TargetLocation>", "<Alias=TargetLocation>", int(SStrParam.LOCKED_TRANS)),
        ("15", "15", int(SStrParam.LOCKED_TRANS)),
    ]


def test_project_export_writes_orphan_strings_without_record_pointer(tmp_path: Path) -> None:
    from bgs_translator.cli.project import _read_units_from_memory, _unit_row_to_sst_unit
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = open_memory_db(tmp_path)
    insert_units(
        conn,
        [
            TranslationUnit(
                "Example.esm",
                2002,
                2002,
                "orphan:STRINGS:2002",
                "ORPH",
                "STRS",
                source="Loose menu label",
                list_index=0,
                strid=2002,
            ),
        ],
    )

    unit = _unit_row_to_sst_unit(_read_units_from_memory(conn)[0])

    assert unit.formid == 0
    assert unit.signature == ""
    assert unit.field == ""
    assert unit.index == 0
    assert unit.index_max == 0
    assert unit.rhash == 0
    assert unit.strid == 2002


def test_project_export_skips_orphan_when_string_id_has_record_pointer(
    tmp_path: Path,
) -> None:
    from bgs_translator.cli.project import _read_units_from_memory
    from bgs_translator.core.memory import insert_units, open_memory_db, update_unit_translation
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = open_memory_db(tmp_path)
    insert_units(
        conn,
        [
            TranslationUnit(
                "Example.esm",
                2002,
                2002,
                "orphan:DLSTRINGS:2002",
                "ORPH",
                "DLST",
                source="Quest log",
                list_index=1,
                strid=2002,
            ),
            TranslationUnit(
                "Example.esm",
                0x010AB62D,
                0x010AB62D,
                "QuestEdid",
                "QUST",
                "CNAM",
                source="Quest log",
                list_index=1,
                strid=2002,
            ),
        ],
    )
    for row_id in [row[0] for row in conn.execute("SELECT row_id FROM units")]:
        update_unit_translation(
            conn,
            row_id=row_id,
            dest="任务日志",
            status="translated",
            sparams=0,
            via_llm=False,
            profile_used="test",
            sdk_via="synthetic",
            cost_estimate_usd=None,
            cost_exact=False,
            retry_count=0,
            last_batch_id="batch-a",
        )

    rows = _read_units_from_memory(conn)

    assert [(row["signature"], row["field"], row["strid"]) for row in rows] == [
        ("QUST", "CNAM", 2002)
    ]


def test_project_export_hashes_no_edid_records_like_xtranslator(tmp_path: Path) -> None:
    from bgs_translator.cli.project import _read_units_from_memory, _unit_row_to_sst_unit
    from bgs_translator.core.memory import insert_units, open_memory_db, update_unit_translation
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.sst.hash import string_hash

    conn = open_memory_db(tmp_path)
    insert_units(
        conn,
        [
            TranslationUnit(
                "kinggathcreations_spaceship.esm",
                0x0109F92B,
                0x0009F92B,
                None,
                "INFO",
                "NAM1",
                source="I'm unsure.",
                list_index=2,
                strid=4984,
            ),
        ],
    )
    row_id = conn.execute("SELECT row_id FROM units").fetchone()[0]
    update_unit_translation(
        conn,
        row_id=row_id,
        dest="我不确定。",
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

    unit = _unit_row_to_sst_unit(_read_units_from_memory(conn)[0])

    assert unit.formid == 0x0109F92B
    assert unit.rhash == 0x96F2CA3E
    assert unit.rhash == string_hash("[0109F92B]")
