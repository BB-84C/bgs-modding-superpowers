"""Shared pytest fixtures for bgs-translator tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path

import pytest

GlossaryFixtureEntry = Mapping[str, object]
PackFactory = Callable[[str, Sequence[GlossaryFixtureEntry], bool], Path]


@pytest.fixture
def make_fixture_pack(tmp_path: Path) -> PackFactory:
    """Create a stub bgs-kb pack database under ``tmp_path/packs``."""

    def _make_pack(
        pack_id: str,
        entries: Sequence[GlossaryFixtureEntry] = (),
        is_user_pack: bool = False,
    ) -> Path:
        from bgs_translator.kb._schema import apply_stub_schema

        root_name = "user-packs" if is_user_pack else "packs"
        pack_root = tmp_path / root_name / pack_id
        pack_root.mkdir(parents=True, exist_ok=True)
        db_path = pack_root / "kb.sqlite"

        conn = sqlite3.connect(db_path)
        try:
            apply_stub_schema(conn)
            for entry in entries:
                record_id = str(entry["record_id"])
                kind = str(entry.get("kind", "glossary-entry"))
                conn.execute(
                    "INSERT INTO records (id, pack_id, kind, title, body_md) VALUES (?, ?, ?, ?, ?)",
                    (record_id, pack_id, kind, entry.get("title"), entry.get("body_md")),
                )
                conn.execute(
                    """
                    INSERT INTO glossary_entries (
                        record_id, source, source_lang, target, target_lang, scope,
                        scope_key, category, confidence, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        entry["source"],
                        entry.get("source_lang", "en"),
                        entry["target"],
                        entry.get("target_lang", "zh-cn"),
                        entry.get("scope", "vanilla"),
                        entry.get("scope_key"),
                        entry.get("category"),
                        entry.get("confidence", "canonical"),
                        entry.get("notes"),
                    ),
                )
                for alias in _as_strings(entry.get("source_aliases", [])):
                    conn.execute(
                        "INSERT INTO glossary_aliases (record_id, alias, alias_kind) VALUES (?, ?, ?)",
                        (record_id, alias, "source"),
                    )
                for alias in _as_strings(entry.get("target_aliases", [])):
                    conn.execute(
                        "INSERT INTO glossary_aliases (record_id, alias, alias_kind) VALUES (?, ?, ?)",
                        (record_id, alias, "target"),
                    )
                for game in _as_strings(entry.get("games", [])):
                    conn.execute(
                        "INSERT INTO record_games (record_id, game, confidence) VALUES (?, ?, ?)",
                        (record_id, game, entry.get("game_confidence")),
                    )
            conn.commit()
        finally:
            conn.close()

        return db_path

    return _make_pack


def _as_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value]
    return []
