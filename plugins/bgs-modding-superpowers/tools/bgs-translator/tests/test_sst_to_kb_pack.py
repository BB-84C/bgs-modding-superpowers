"""SST-to-glossary-KB pack conversion tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def test_sst_to_kb_pack_builds_reader_visible_vanilla_glossary(tmp_path: Path) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader
    from bgs_translator.sst.writer import SSTUnit, write_sst
    from bgs_translator.tools.xtranslator_sst_to_kb_pack import build_pack_from_sst

    sst_path = tmp_path / "starfield_en_zhhans.sst"
    write_sst(
        sst_path,
        [
            SSTUnit(
                list_index=0,
                strid=0,
                formid=0x00012345,
                signature="FACT",
                field="FULL",
                source="United Colonies",
                dest="联合殖民地",
            ),
            SSTUnit(
                list_index=0,
                strid=1,
                formid=0x00012345,
                signature="FACT",
                field="FULL",
                source="United Colonies",
                dest="联合殖民地",
            ),
            SSTUnit(
                list_index=0,
                strid=2,
                formid=0x00023456,
                signature="CELL",
                field="FULL",
                source="New Atlantis",
                dest="新亚特兰蒂斯",
            ),
        ],
        ["Starfield.esm"],
    )
    pack_dir = tmp_path / "kb" / "packs" / "bgs-l10n-starfield-zhhans"

    stats = build_pack_from_sst(
        input_sst=sst_path,
        output_dir=pack_dir,
        pack_id="bgs-l10n-starfield-zhhans",
        display_name="BGS Localization Glossary - Starfield zh-Hans",
        game="Starfield",
        source_lang="en",
        target_lang="zh-cn",
    )

    assert stats.entries_seen == 3
    assert stats.entries_inserted == 2
    assert stats.duplicate_skipped == 1
    assert (pack_dir / "kb.sqlite").exists()
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["recordCount"] == 2
    assert manifest["games"] == ["Starfield"]

    conn = sqlite3.connect(pack_dir / "kb.sqlite")
    try:
        row = conn.execute(
            "SELECT source, target, scope, category FROM glossary_entries WHERE source = ?",
            ("United Colonies",),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("United Colonies", "联合殖民地", "vanilla", "faction")

    reader = KBGlossaryReader(kb_root=tmp_path / "kb", user_packs_root=tmp_path / "user-packs")
    try:
        entries = reader.query_matching_entries(["Travel to New Atlantis"], "zh-cn", "Starfield")
    finally:
        reader.close()

    assert [(entry.source, entry.target, entry.scope) for entry in entries] == [
        ("New Atlantis", "新亚特兰蒂斯", "vanilla")
    ]
