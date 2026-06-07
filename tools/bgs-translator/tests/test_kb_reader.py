"""Tests for direct bgs-kb glossary SQLite reading."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from conftest import PackFactory


def test_reader_returns_matching_entry_for_source_string(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "bgs-kb-l10n-skyrim-en-zhcn",
        [
            {
                "record_id": "l10n.skyrim.place.whiterun.en-zhcn",
                "source": "Whiterun",
                "target": "白漫城",
                "category": "place",
                "games": ["SkyrimSE"],
            }
        ],
    )

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        entries = reader.query_matching_entries(["Whiterun"], "zh-cn", "SkyrimSE")
    finally:
        reader.close()

    assert [entry.record_id for entry in entries] == ["l10n.skyrim.place.whiterun.en-zhcn"]
    assert entries[0].pack_id == "bgs-kb-l10n-skyrim-en-zhcn"


def test_reader_user_pack_overrides_canonical_pack(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    record_id = "l10n.skyrim.place.whiterun.en-zhcn"
    make_fixture_pack(
        "canonical",
        [{"record_id": record_id, "source": "Whiterun", "target": "白漫城", "games": []}],
    )
    make_fixture_pack(
        "translator-overrides-en-zhcn",
        [{"record_id": record_id, "source": "Whiterun", "target": "雪漫城", "scope": "player"}],
        is_user_pack=True,
    )

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        entries = reader.query_matching_entries(["Whiterun"], "zh-cn", "SkyrimSE")
    finally:
        reader.close()

    assert len(entries) == 1
    assert entries[0].target == "雪漫城"
    assert entries[0].pack_id == "translator-overrides-en-zhcn"


def test_reader_mod_entries_require_matching_mod_slug(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "requiem-pack",
        [
            {
                "record_id": "l10n.skyrim.item.requiem-token.en-zhcn",
                "source": "Requiem Token",
                "target": "安魂曲令牌",
                "scope": "mod",
                "scope_key": "requiem",
                "category": "item",
            }
        ],
    )

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        assert reader.query_matching_entries(["Requiem Token"], "zh-cn", "SkyrimSE") == []
        matched = reader.query_matching_entries(
            ["Requiem Token"], "zh-cn", "SkyrimSE", mod_slug="requiem"
        )
    finally:
        reader.close()

    assert [entry.scope_key for entry in matched] == ["requiem"]


def test_reader_filters_target_lang(tmp_path: Path, make_fixture_pack: PackFactory) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [{"record_id": "l10n.skyrim.place.whiterun.en-zhcn", "source": "Whiterun", "target": "白漫城"}],
    )

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        entries = reader.query_matching_entries(["Whiterun"], "fr", "SkyrimSE")
    finally:
        reader.close()

    assert entries == []


def test_reader_skips_missing_kb_sqlite(tmp_path: Path) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    (tmp_path / "packs" / "empty-pack").mkdir(parents=True)

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        assert reader.pack_dbs == []
        assert reader.query_matching_entries(["Whiterun"], "zh-cn", "SkyrimSE") == []
    finally:
        reader.close()


def test_reader_skips_pack_missing_glossary_tables(tmp_path: Path) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    pack_root = tmp_path / "packs" / "legacy-pack"
    pack_root.mkdir(parents=True)
    conn = sqlite3.connect(pack_root / "kb.sqlite")
    try:
        conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, pack_id TEXT NOT NULL)")
        conn.commit()
    finally:
        conn.close()

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        assert reader.query_matching_entries(["Whiterun"], "zh-cn", "SkyrimSE") == []
    finally:
        reader.close()
