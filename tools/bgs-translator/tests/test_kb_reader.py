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


def test_reader_global_user_scope_entries_only_come_from_user_packs(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "canonical",
        [
            {
                "record_id": "canonical-dnt",
                "source": "CanonicalOnly",
                "target": "CanonicalOnly",
                "scope": "do_not_translate",
            }
        ],
    )
    make_fixture_pack(
        "translator-overrides-en-zhcn",
        [
            {
                "record_id": "user-dnt",
                "source": "FC",
                "target": "FC",
                "scope": "do_not_translate",
            },
            {
                "record_id": "user-player",
                "source": "Starfield",
                "target": "星空",
                "scope": "player",
            },
        ],
        is_user_pack=True,
    )

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        entries = reader.query_user_scope_entries(
            "zh-cn",
            "Starfield",
            scopes={"player", "do_not_translate"},
        )
    finally:
        reader.close()

    assert [(entry.source, entry.scope) for entry in entries] == [
        ("FC", "do_not_translate"),
        ("Starfield", "player"),
    ]


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


def test_reader_chunks_large_candidate_prefilter_terms(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "bgs-l10n-starfield-zhhans",
        [
            {
                "record_id": "l10n.starfield.target-term",
                "source": "TargetTerm",
                "target": "目标术语",
                "category": "lore_term",
                "games": ["Starfield"],
            }
        ],
    )
    source = " ".join([f"token{i:03d}" for i in range(520)] + ["TargetTerm"])

    reader = KBGlossaryReader(
        kb_root=tmp_path,
        user_packs_root=tmp_path / "user-packs",
        candidate_source_term_limit=600,
    )
    try:
        entries = reader.query_candidate_entries("zh-cn", "Starfield", source_strings=[source])
    finally:
        reader.close()

    assert [entry.record_id for entry in entries] == ["l10n.starfield.target-term"]


def test_reader_large_pack_keeps_related_rag_candidates(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    make_fixture_pack(
        "bgs-l10n-starfield-zhhans",
        [
            {
                "record_id": "l10n.starfield.laser-turret",
                "source": "Laser Turret",
                "target": "激光炮塔",
                "category": "lore_term",
                "games": ["Starfield"],
            }
        ],
    )
    db_path = tmp_path / "packs" / "bgs-l10n-starfield-zhhans" / "kb.sqlite"

    reader = KBGlossaryReader(
        kb_root=tmp_path,
        user_packs_root=tmp_path / "user-packs",
        candidate_source_term_limit=20,
    )
    reader._glossary_count_cache[db_path] = 50_001
    try:
        entries = reader.query_candidate_entries(
            "zh-cn",
            "Starfield",
            source_strings=["Install a defensive Laser weapon near the Turret control node."],
        )
    finally:
        reader.close()

    assert [entry.record_id for entry in entries] == ["l10n.starfield.laser-turret"]


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
