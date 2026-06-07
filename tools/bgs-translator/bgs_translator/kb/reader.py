"""Read-only SQLite reader for bgs-kb pack stores."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from bgs_translator.config import paths
from bgs_translator.kb.models import GlossaryEntry


class KBGlossaryReader:
    """Reads glossary-entry records from bgs-kb pack SQLite stores."""

    def __init__(
        self,
        kb_root: Path | None = None,
        *,
        user_packs_root: Path | None = None,
    ) -> None:
        """Discover pack DBs.

        Per AMENDMENTS §4.1: filename is ``kb.sqlite``, not ``store.sqlite``.
        Per PRD §3.3: ``$BGS_KB_USER_PACKS`` can override user-packs root.
        """
        self.kb_root = kb_root or paths.kb_root()
        self.user_packs_root = user_packs_root or paths.kb_user_packs_root()
        self.pack_dbs: list[tuple[str, Path]] = []
        self.user_pack_dbs: list[tuple[str, Path]] = []
        self._discover()
        self._conns: dict[Path, sqlite3.Connection] = {}

    def _discover(self) -> None:
        """Scan installed and user pack roots for ``kb.sqlite`` files."""
        self.pack_dbs = self._discover_under(self.kb_root / "packs")
        self.user_pack_dbs = self._discover_under(self.user_packs_root)

    @staticmethod
    def _discover_under(root: Path) -> list[tuple[str, Path]]:
        if not root.exists() or not root.is_dir():
            return []
        discovered: list[tuple[str, Path]] = []
        for pack_dir in sorted(child for child in root.iterdir() if child.is_dir()):
            db_path = pack_dir / "kb.sqlite"
            if db_path.is_file():
                discovered.append((pack_dir.name, db_path))
        return discovered

    def _conn(self, path: Path) -> sqlite3.Connection:
        """Return a lazily opened, cached read-only connection."""
        cached = self._conns.get(path)
        if cached is not None:
            return cached
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        self._conns[path] = conn
        return conn

    def query_matching_entries(
        self,
        source_strings: list[str],
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None = None,
    ) -> list[GlossaryEntry]:
        """Return glossary entries matching any source string.

        Matching is case-insensitive and checks whether an entry source form
        (canonical source or source alias) appears as a substring of any batch
        source string. Deduplication is by ``record_id``; user packs are applied
        after canonical packs so user-pack rows override earlier rows.
        """
        if not source_strings:
            return []

        deduped: dict[str, GlossaryEntry] = {}
        for pack_id, db_path in [*self.pack_dbs, *self.user_pack_dbs]:
            for entry in self._query_pack(
                pack_id,
                db_path,
                source_strings,
                target_lang,
                game,
                mod_slug=mod_slug,
            ):
                deduped[entry.record_id] = entry

        return sorted(
            deduped.values(),
            key=lambda entry: (-_scope_sort_weight(entry.scope), entry.source.casefold(), entry.record_id),
        )

    def _query_pack(
        self,
        pack_id: str,
        db_path: Path,
        source_strings: list[str],
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None,
    ) -> list[GlossaryEntry]:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"records", "glossary_entries"}):
                return []
            rows = conn.execute(
                """
                SELECT
                    ge.record_id,
                    ge.source,
                    ge.source_lang,
                    ge.target,
                    ge.target_lang,
                    ge.scope,
                    ge.scope_key,
                    ge.category,
                    ge.confidence,
                    ge.notes,
                    r.pack_id AS row_pack_id
                FROM glossary_entries ge
                JOIN records r ON r.id = ge.record_id
                WHERE r.kind = 'glossary-entry'
                  AND LOWER(ge.target_lang) = LOWER(?)
                """,
                (target_lang,),
            ).fetchall()
        except sqlite3.Error:
            return []

        entries: list[GlossaryEntry] = []
        for row in rows:
            if row["scope"] == "mod" and (not mod_slug or row["scope_key"] != mod_slug):
                continue

            source_aliases = self._aliases(db_path, str(row["record_id"]), "source")
            target_aliases = self._aliases(db_path, str(row["record_id"]), "target")
            games = self._games(db_path, str(row["record_id"]))
            if games and game not in games:
                continue

            entry = GlossaryEntry(
                record_id=str(row["record_id"]),
                source=str(row["source"]),
                source_aliases=source_aliases,
                source_lang=str(row["source_lang"]),
                target=str(row["target"]),
                target_aliases=target_aliases,
                target_lang=str(row["target_lang"]),
                scope=row["scope"],
                scope_key=row["scope_key"],
                category=row["category"],
                confidence=row["confidence"],
                notes=row["notes"],
                pack_id=str(row["row_pack_id"] or pack_id),
                games=games,
            )
            if _entry_matches_source_strings(entry, source_strings):
                entries.append(entry)

        return entries

    def _aliases(self, db_path: Path, record_id: str, alias_kind: str) -> list[str]:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"glossary_aliases"}):
                return []
            rows = conn.execute(
                """
                SELECT alias
                FROM glossary_aliases
                WHERE record_id = ? AND alias_kind = ?
                ORDER BY rowid
                """,
                (record_id, alias_kind),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [str(row["alias"]) for row in rows]

    def _games(self, db_path: Path, record_id: str) -> list[str]:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"record_games"}):
                return []
            rows = conn.execute(
                "SELECT game FROM record_games WHERE record_id = ? ORDER BY game",
                (record_id,),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [str(row["game"]) for row in rows]

    def close(self) -> None:
        """Close all cached connections."""
        for conn in self._conns.values():
            conn.close()
        self._conns.clear()


def _has_tables(conn: sqlite3.Connection, table_names: set[str]) -> bool:
    placeholders = ",".join("?" for _ in table_names)
    rows = conn.execute(
        f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
        tuple(table_names),
    ).fetchall()
    found = {str(row["name"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows}
    return table_names <= found


def _entry_matches_source_strings(entry: GlossaryEntry, source_strings: list[str]) -> bool:
    haystacks = [source_string.casefold() for source_string in source_strings]
    for form in entry.all_source_forms:
        needle = form.casefold()
        if needle and any(needle in haystack for haystack in haystacks):
            return True
    return False


def _scope_sort_weight(scope: str) -> int:
    return {"do_not_translate": 4, "player": 3, "mod": 2, "vanilla": 1}.get(scope, 0)


__all__ = ["KBGlossaryReader"]
