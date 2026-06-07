"""Tests for absent bgs-kb pack roots."""

from __future__ import annotations

from pathlib import Path


def test_empty_kb_root_returns_no_glossary_results(tmp_path: Path) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    reader = KBGlossaryReader(kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
    try:
        assert reader.pack_dbs == []
        assert reader.user_pack_dbs == []
        assert reader.query_matching_entries(["Whiterun"], "zh-cn", "SkyrimSE") == []
    finally:
        reader.close()


def test_discovery_is_robust_to_missing_directories(tmp_path: Path) -> None:
    from bgs_translator.kb.reader import KBGlossaryReader

    reader = KBGlossaryReader(kb_root=tmp_path / "missing-kb", user_packs_root=tmp_path / "missing-user")
    try:
        assert reader.pack_dbs == []
        assert reader.user_pack_dbs == []
    finally:
        reader.close()
