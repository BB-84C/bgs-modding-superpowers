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
