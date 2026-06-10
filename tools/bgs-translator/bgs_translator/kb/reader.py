"""Read-only SQLite reader for bgs-kb pack stores."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from collections.abc import Collection
from pathlib import Path

from bgs_translator.config import paths
from bgs_translator.kb.models import GlossaryEntry

_SOURCE_PREFILTER_CHUNK_SIZE = 400
_LARGE_GLOSSARY_PACK_THRESHOLD = 50_000
_READER_STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "identify",
    "just",
    "not",
    "read",
    "that",
    "the",
    "there",
    "this",
    "was",
    "were",
    "while",
    "with",
    "you",
    "your",
}


class KBGlossaryReader:
    """Reads glossary-entry records from bgs-kb pack SQLite stores."""

    def __init__(
        self,
        kb_root: Path | None = None,
        *,
        user_packs_root: Path | None = None,
        candidate_source_term_limit: int = 32,
    ) -> None:
        """Discover pack DBs.

        Per AMENDMENTS §4.1: filename is ``kb.sqlite``, not ``store.sqlite``.
        Per PRD §3.3: ``$BGS_KB_USER_PACKS`` can override user-packs root.
        """
        self.kb_root = kb_root or paths.kb_root()
        self.user_packs_root = user_packs_root or paths.kb_user_packs_root()
        self.candidate_source_term_limit = max(1, int(candidate_source_term_limit))
        self.pack_dbs: list[tuple[str, Path]] = []
        self.user_pack_dbs: list[tuple[str, Path]] = []
        self._discover()
        self._conns: dict[Path, sqlite3.Connection] = {}
        self._candidate_cache: dict[
            tuple[str, Path, str, str, str | None, tuple[str, ...] | None],
            list[GlossaryEntry],
        ] = {}
        self._glossary_count_cache: dict[Path, int] = {}
        self._large_pack_entries_cache: dict[tuple[Path, str, str], list[GlossaryEntry]] = {}

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

    def query_user_scope_entries(
        self,
        target_lang: str,
        game: str,
        *,
        scopes: Collection[str],
    ) -> list[GlossaryEntry]:
        """Return user-pack entries for scopes that behave as player preferences.

        Canonical vanilla/mod packs can be large, so the normal batch collector
        keeps them source-matched. User-maintained player and do-not-translate
        overlays are intentionally small and high priority; loading them as
        global preferences keeps the next plan aligned with what the user just
        added in the GUI.
        """
        normalized_scopes = {scope for scope in scopes if scope}
        if not normalized_scopes:
            return []

        deduped: dict[str, GlossaryEntry] = {}
        for pack_id, db_path in self.user_pack_dbs:
            for entry in self._query_pack(
                pack_id,
                db_path,
                [],
                target_lang,
                game,
                mod_slug=None,
                require_source_match=False,
            ):
                if entry.scope in normalized_scopes:
                    deduped[entry.record_id] = entry

        return sorted(
            deduped.values(),
            key=lambda entry: (-_scope_sort_weight(entry.scope), entry.source.casefold(), entry.record_id),
        )

    def query_candidate_entries(
        self,
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None = None,
        source_strings: list[str] | None = None,
    ) -> list[GlossaryEntry]:
        """Return all glossary entries eligible for a batch-level retriever.

        Unlike :meth:`query_matching_entries`, this method performs no source
        substring matching. The higher-level retriever owns exact, normalized,
        rule, RAG, dedupe, and prompt-budget behavior. Results are cached by
        DB/language/game/mod scope because large vanilla packs are reused across
        many entries while planning a run.
        """
        source_terms = tuple(_candidate_source_terms(source_strings or [], self.candidate_source_term_limit)) or None
        exact_forms = tuple(_candidate_exact_forms(source_strings or [], self.candidate_source_term_limit)) or None
        deduped: dict[str, GlossaryEntry] = {}
        for root_kind, pack_id, db_path in [
            *[("canonical", pack_id, db_path) for pack_id, db_path in self.pack_dbs],
            *[("user", pack_id, db_path) for pack_id, db_path in self.user_pack_dbs],
        ]:
            prefilter_terms = None if root_kind == "user" else source_terms
            if root_kind == "canonical" and source_terms is None:
                continue
            cached = self._query_candidate_pack_cached(
                root_kind,
                pack_id,
                db_path,
                target_lang,
                game,
                mod_slug=mod_slug,
                source_prefilter_terms=prefilter_terms,
                source_exact_forms=exact_forms if root_kind == "canonical" else None,
            )
            for entry in cached:
                deduped[entry.record_id] = entry

        return sorted(
            deduped.values(),
            key=lambda entry: (-_scope_sort_weight(entry.scope), entry.source.casefold(), entry.record_id),
        )

    def _query_candidate_pack_cached(
        self,
        root_kind: str,
        pack_id: str,
        db_path: Path,
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None,
        source_prefilter_terms: tuple[str, ...] | None,
        source_exact_forms: tuple[str, ...] | None = None,
    ) -> list[GlossaryEntry]:
        deduped: dict[str, GlossaryEntry] = {}
        for chunk in _chunks(source_exact_forms or (), _SOURCE_PREFILTER_CHUNK_SIZE):
            key = (f"{root_kind}:exact", db_path, target_lang.casefold(), game, mod_slug, chunk)
            cached = self._candidate_cache.get(key)
            if cached is None:
                cached = self._query_pack(
                    pack_id,
                    db_path,
                    [],
                    target_lang,
                    game,
                    mod_slug=mod_slug,
                    require_source_match=False,
                    alias_mode="bulk",
                    source_exact_forms=chunk,
                )
                self._candidate_cache[key] = cached
            for entry in cached:
                deduped[entry.record_id] = entry
        if self._is_large_glossary_pack(db_path):
            for entry in self._query_large_candidate_pack_cached(
                root_kind,
                pack_id,
                db_path,
                target_lang,
                game,
                mod_slug=mod_slug,
                source_prefilter_terms=source_prefilter_terms,
            ):
                deduped[entry.record_id] = entry
            return list(deduped.values())

        chunks = (
            _chunks(source_prefilter_terms, _SOURCE_PREFILTER_CHUNK_SIZE)
            if source_prefilter_terms
            else [None]
        )
        for chunk in chunks:
            key = (f"{root_kind}:prefilter", db_path, target_lang.casefold(), game, mod_slug, chunk)
            cached = self._candidate_cache.get(key)
            if cached is None:
                cached = self._query_pack(
                    pack_id,
                    db_path,
                    [],
                    target_lang,
                    game,
                    mod_slug=mod_slug,
                    require_source_match=False,
                    alias_mode="bulk",
                    source_prefilter_terms=chunk,
                )
                self._candidate_cache[key] = cached
            for entry in cached:
                deduped[entry.record_id] = entry
        return list(deduped.values())

    def _query_large_candidate_pack_cached(
        self,
        root_kind: str,
        pack_id: str,
        db_path: Path,
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None,
        source_prefilter_terms: tuple[str, ...] | None,
    ) -> list[GlossaryEntry]:
        if not source_prefilter_terms:
            return []
        key = (
            f"{root_kind}:large-prefilter",
            db_path,
            target_lang.casefold(),
            game,
            mod_slug,
            source_prefilter_terms,
        )
        cached = self._candidate_cache.get(key)
        if cached is not None:
            return cached
        source_terms = set(source_prefilter_terms)
        cached = [
            entry
            for entry in self._large_pack_entries(pack_id, db_path, target_lang, game, mod_slug=mod_slug)
            if _entry_source_related_to_terms(entry.source, source_terms)
        ]
        self._candidate_cache[key] = cached
        return cached

    def _query_pack(
        self,
        pack_id: str,
        db_path: Path,
        source_strings: list[str],
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None,
        require_source_match: bool = True,
        alias_mode: str = "per-record",
        source_prefilter_terms: tuple[str, ...] | None = None,
        source_exact_forms: tuple[str, ...] | None = None,
    ) -> list[GlossaryEntry]:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"records", "glossary_entries"}):
                return []
            where = [
                "r.kind = 'glossary-entry'",
                "LOWER(ge.target_lang) = LOWER(?)",
            ]
            params: list[object] = [target_lang]
            if source_exact_forms:
                placeholders = ",".join("?" for _ in source_exact_forms)
                where.append(f"LOWER(ge.source) IN ({placeholders})")
                params.extend(form.casefold() for form in source_exact_forms)
            if source_prefilter_terms:
                include_alias_prefilter = self._has_source_aliases(db_path)
                clauses = []
                for term in source_prefilter_terms:
                    clauses.append("LOWER(ge.source) LIKE ?")
                    params.append(f"%{term}%")
                    if include_alias_prefilter:
                        clauses.append(
                            """
                            EXISTS (
                                SELECT 1 FROM glossary_aliases ga
                                WHERE ga.record_id = ge.record_id
                                  AND ga.alias_kind = 'source'
                                  AND LOWER(ga.alias) LIKE ?
                            )
                            """
                        )
                        params.append(f"%{term}%")
                where.append(f"({' OR '.join(clauses)})")
            rows = conn.execute(
                f"""
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
                WHERE {' AND '.join(where)}
                """,
                params,
            ).fetchall()
        except sqlite3.Error:
            return []

        entries: list[GlossaryEntry] = []
        alias_map: dict[str, dict[str, list[str]]] = {}
        games_map: dict[str, list[str]] | None = None
        if alias_mode == "bulk":
            alias_map = self._aliases_map(db_path)
            games_map = self._games_map(db_path)
        for row in rows:
            if row["scope"] == "mod" and (not mod_slug or row["scope_key"] != mod_slug):
                continue

            record_id = str(row["record_id"])
            if alias_mode == "bulk":
                source_aliases = alias_map.get(record_id, {}).get("source", [])
                target_aliases = alias_map.get(record_id, {}).get("target", [])
                games = [] if games_map is None else games_map.get(record_id, [])
            else:
                source_aliases = self._aliases(db_path, record_id, "source")
                target_aliases = self._aliases(db_path, record_id, "target")
                games = self._games(db_path, record_id)
            if games and game not in games:
                continue

            entry = GlossaryEntry(
                record_id=record_id,
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
            if not require_source_match or _entry_matches_source_strings(entry, source_strings):
                entries.append(entry)

        return entries

    def _aliases_map(self, db_path: Path) -> dict[str, dict[str, list[str]]]:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"glossary_aliases"}):
                return {}
            rows = conn.execute(
                """
                SELECT record_id, alias, alias_kind
                FROM glossary_aliases
                ORDER BY rowid
                """
            ).fetchall()
        except sqlite3.Error:
            return {}

        grouped: dict[str, dict[str, list[str]]] = {}
        for row in rows:
            grouped.setdefault(str(row["record_id"]), {}).setdefault(str(row["alias_kind"]), []).append(
                str(row["alias"])
            )
        return grouped

    def _has_source_aliases(self, db_path: Path) -> bool:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"glossary_aliases"}):
                return False
            row = conn.execute(
                "SELECT 1 FROM glossary_aliases WHERE alias_kind = 'source' LIMIT 1"
            ).fetchone()
        except sqlite3.Error:
            return False
        return row is not None

    def _large_pack_entries(
        self,
        pack_id: str,
        db_path: Path,
        target_lang: str,
        game: str,
        *,
        mod_slug: str | None,
    ) -> list[GlossaryEntry]:
        cache_key = (db_path, target_lang.casefold(), game)
        cached = self._large_pack_entries_cache.get(cache_key)
        if cached is not None:
            entries = cached
        else:
            try:
                conn = self._conn(db_path)
                if not _has_tables(conn, {"records", "glossary_entries"}):
                    entries = []
                else:
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
                          AND (
                            EXISTS (
                              SELECT 1
                              FROM record_games rg
                              WHERE rg.record_id = ge.record_id
                                AND rg.game = ?
                            )
                            OR NOT EXISTS (
                              SELECT 1
                              FROM record_games rg_any
                              WHERE rg_any.record_id = ge.record_id
                            )
                          )
                        """,
                        (target_lang, game),
                    ).fetchall()
                    alias_map = self._aliases_map(db_path) if self._has_source_aliases(db_path) else {}
                    games_map = self._games_map(db_path)
                    entries = []
                    for row in rows:
                        record_id = str(row["record_id"])
                        source_aliases = alias_map.get(record_id, {}).get("source", [])
                        target_aliases = alias_map.get(record_id, {}).get("target", [])
                        games = games_map.get(record_id, [])
                        entries.append(
                            GlossaryEntry(
                                record_id=record_id,
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
                        )
            except sqlite3.Error:
                entries = []
            self._large_pack_entries_cache[cache_key] = entries

        if not mod_slug:
            return [entry for entry in entries if entry.scope != "mod"]
        return [
            entry
            for entry in entries
            if entry.scope != "mod" or entry.scope_key == mod_slug
        ]

    def _is_large_glossary_pack(self, db_path: Path) -> bool:
        cached = self._glossary_count_cache.get(db_path)
        if cached is not None:
            return cached > _LARGE_GLOSSARY_PACK_THRESHOLD
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"glossary_entries"}):
                self._glossary_count_cache[db_path] = 0
                return False
            count = int(conn.execute("SELECT COUNT(*) FROM glossary_entries").fetchone()[0])
        except sqlite3.Error:
            count = 0
        self._glossary_count_cache[db_path] = count
        return count > _LARGE_GLOSSARY_PACK_THRESHOLD

    def _games_map(self, db_path: Path) -> dict[str, list[str]]:
        try:
            conn = self._conn(db_path)
            if not _has_tables(conn, {"record_games"}):
                return {}
            rows = conn.execute(
                "SELECT record_id, game FROM record_games ORDER BY record_id, game"
            ).fetchall()
        except sqlite3.Error:
            return {}

        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(str(row["record_id"]), []).append(str(row["game"]))
        return grouped

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
        self._candidate_cache.clear()
        self._large_pack_entries_cache.clear()


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


def _candidate_source_terms(source_strings: list[str], limit: int) -> list[str]:
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    order = 0
    for source in source_strings:
        for raw_token in re.findall(r"[A-Za-z0-9]+", source):
            token = raw_token.casefold()
            if token in _READER_STOP_WORDS:
                continue
            if len(raw_token) < 3 and not (len(raw_token) >= 2 and raw_token.isupper()):
                continue
            counts[token] += 1
            first_seen.setdefault(token, order)
            order += 1
    return [
        token
        for token, _count in sorted(
            counts.items(),
            key=lambda item: (-item[1], first_seen[item[0]], item[0]),
        )[:limit]
    ]


def _candidate_exact_forms(source_strings: list[str], limit: int) -> list[str]:
    forms: list[str] = []
    for source in source_strings:
        clean = " ".join(source.strip().split())
        if clean:
            forms.append(clean)
        tokens = re.findall(r"[A-Za-z0-9]+", source)
        if len(tokens) > 12:
            continue
        for width in (2, 3, 4):
            for index in range(0, max(0, len(tokens) - width + 1)):
                forms.append(" ".join(tokens[index : index + width]))
    deduped = list(dict.fromkeys(form for form in forms if form and len(form) >= 2))
    return deduped[:limit]


def _chunks(values: tuple[str, ...], size: int) -> list[tuple[str, ...]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _entry_source_related_to_terms(source: str, source_terms: set[str]) -> bool:
    entry_terms = _entry_candidate_terms(source)
    if not entry_terms:
        return False
    required_overlap = min(2, len(entry_terms))
    return len(entry_terms & source_terms) >= required_overlap


def _entry_candidate_terms(source: str) -> set[str]:
    if len(source) > 80 or any(marker in source for marker in (".", "?", "!", ",", ";", ":")):
        return set()
    raw_tokens = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", source)}
    if raw_tokens & _READER_STOP_WORDS:
        return set()
    terms = {token for token in raw_tokens if len(token) >= 3 and token not in _READER_STOP_WORDS}
    if len(terms) < 2 or len(terms) > 6:
        return set()
    return terms


__all__ = ["KBGlossaryReader"]
