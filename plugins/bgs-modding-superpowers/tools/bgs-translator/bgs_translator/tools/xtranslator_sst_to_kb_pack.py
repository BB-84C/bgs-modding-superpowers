"""Convert an xTranslator SST dictionary into a glossary KB pack.

This is intentionally a standalone one-shot tool rather than an ``xtl``
subcommand. It builds the SQLite shape that ``KBGlossaryReader`` already reads,
without requiring the bgs-kb MCP build pipeline to understand glossary records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bgs_translator.kb._schema import apply_stub_schema
from bgs_translator.sst.reader import read_sst
from bgs_translator.sst.writer import SSTUnit


@dataclass(slots=True)
class BuildStats:
    """Summary of an SST-to-KB conversion."""

    entries_seen: int = 0
    entries_inserted: int = 0
    empty_skipped: int = 0
    duplicate_skipped: int = 0
    conflict_skipped: int = 0
    categories: Counter[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries_seen": self.entries_seen,
            "entries_inserted": self.entries_inserted,
            "empty_skipped": self.empty_skipped,
            "duplicate_skipped": self.duplicate_skipped,
            "conflict_skipped": self.conflict_skipped,
            "categories": dict(self.categories or Counter()),
        }


def build_pack_from_sst(
    *,
    input_sst: Path,
    output_dir: Path,
    pack_id: str,
    display_name: str,
    game: str,
    source_lang: str,
    target_lang: str,
    prefer_newer: bool = False,
) -> BuildStats:
    """Build a glossary-entry KB pack from ``input_sst`` under ``output_dir``."""

    decoded = read_sst(input_sst)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "kb.sqlite"
    if db_path.exists():
        db_path.unlink()

    stats = BuildStats(categories=Counter())
    source_targets: dict[str, tuple[str, SSTUnit]] = {}
    for unit in decoded.entries:
        stats.entries_seen += 1
        source = _clean_text(unit.source)
        target = _clean_text(unit.dest)
        if not source or not target:
            stats.empty_skipped += 1
            continue
        existing = source_targets.get(source.casefold())
        if existing is not None:
            existing_target, _existing_unit = existing
            if existing_target == target:
                stats.duplicate_skipped += 1
                continue
            stats.conflict_skipped += 1
            if not prefer_newer:
                continue
        source_targets[source.casefold()] = (target, unit)

    with sqlite3.connect(db_path) as conn:
        apply_stub_schema(conn)
        for source_key in sorted(source_targets):
            target, unit = source_targets[source_key]
            source = _clean_text(unit.source)
            category = _category_for_unit(unit)
            stats.categories[category] += 1  # type: ignore[index]
            record_id = _record_id(pack_id, source, target)
            body = _body_md(source, target, unit)
            conn.execute(
                "INSERT INTO records (id, pack_id, kind, title, body_md) VALUES (?, ?, 'glossary-entry', ?, ?)",
                (record_id, pack_id, source[:120], body),
            )
            conn.execute(
                """
                INSERT INTO glossary_entries (
                    record_id, source, source_lang, target, target_lang, scope,
                    scope_key, category, confidence, notes
                ) VALUES (?, ?, ?, ?, ?, 'vanilla', NULL, ?, 'canonical', ?)
                """,
                (
                    record_id,
                    source,
                    source_lang,
                    target,
                    target_lang,
                    category,
                    _notes_for_unit(input_sst, unit),
                ),
            )
            conn.execute(
                "INSERT INTO record_games (record_id, game, confidence) VALUES (?, ?, 'canonical')",
                (record_id, game),
            )
            stats.entries_inserted += 1
        conn.commit()

    _write_pack_sidecars(
        output_dir=output_dir,
        db_path=db_path,
        pack_id=pack_id,
        display_name=display_name,
        game=game,
        source_lang=source_lang,
        target_lang=target_lang,
        stats=stats,
    )
    return stats


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())


def _record_id(pack_id: str, source: str, target: str) -> str:
    digest = hashlib.sha1(f"{source}\0{target}".encode()).hexdigest()[:20]
    return f"{pack_id}.{digest}"


def _category_for_unit(unit: SSTUnit) -> str:
    signature = (unit.signature or "").upper()
    field = (unit.field or "").upper()
    if signature in {"NPC_", "INFO"}:
        return "character"
    if signature in {"FACT", "RACE"}:
        return "faction"
    if signature in {"CELL", "WRLD", "LCTN", "REGN"}:
        return "place"
    if signature in {"WEAP", "ARMO", "AMMO", "ALCH", "BOOK", "MISC", "KEYM"}:
        return "item"
    if signature in {"MESG", "GMST"} or field in {"ITXT"}:
        return "ui_label"
    if signature in {"QUST", "PERK", "AVIF", "SPEL"}:
        return "lore_term"
    return "lore_term"


def _body_md(source: str, target: str, unit: SSTUnit) -> str:
    return "\n".join(
        [
            f"# {source}",
            "",
            f"- Source: `{source}`",
            f"- Target: `{target}`",
            f"- Record: `{unit.signature}:{unit.field}`",
            f"- FormID: `{unit.formid:08X}`",
        ]
    )


def _notes_for_unit(input_sst: Path, unit: SSTUnit) -> str:
    return (
        f"Imported from {input_sst.name}; record={unit.signature}:{unit.field}; "
        f"formid={unit.formid:08X}; list_index={unit.list_index}; strid={unit.strid}; rhash={unit.rhash}."
    )


def _write_pack_sidecars(
    *,
    output_dir: Path,
    db_path: Path,
    pack_id: str,
    display_name: str,
    game: str,
    source_lang: str,
    target_lang: str,
    stats: BuildStats,
) -> None:
    built_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    sha = _sha256(db_path)
    manifest = {
        "builtAt": built_at,
        "displayName": display_name,
        "domains": ["translation", "localization", "glossary"],
        "engineFamilies": ["Creation Engine 2"],
        "games": [game],
        "license": "Bethesda official localization data; redistribution policy follows project pack policy",
        "minPluginVersion": "0.2.0",
        "owner": "bgs-modding-superpowers maintainers",
        "packId": pack_id,
        "recordCount": stats.entries_inserted,
        "schemaVersion": 1,
        "sha256": {"kb.sqlite": sha},
        "sourceLang": source_lang,
        "targetLang": target_lang,
        "version": datetime.now(UTC).strftime("%Y.%m.%d"),
        "buildStats": stats.to_dict(),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    meta = "\n".join(
        [
            f"packId: {pack_id}",
            f"displayName: {display_name}",
            f"version: {manifest['version']}",
            "schemaVersion: 1",
            "minPluginVersion: 0.2.0",
            "owner: bgs-modding-superpowers maintainers",
            f"license: {manifest['license']}",
            f"sourceLang: {source_lang}",
            f"targetLang: {target_lang}",
            "",
        ]
    )
    (output_dir / "bgs-kb-meta.yml").write_text(meta, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Source .sst file")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output KB pack directory")
    parser.add_argument("--pack-id", required=True, help="Stable KB pack id")
    parser.add_argument("--display-name", required=True, help="Human-readable pack name")
    parser.add_argument("--game", required=True, help="Game name, e.g. Starfield")
    parser.add_argument("--source-lang", default="en", help="Source language code")
    parser.add_argument("--target-lang", default="zh-cn", help="Target language code")
    parser.add_argument("--prefer-newer", action="store_true", help="Keep later conflicting source translations")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    stats = build_pack_from_sst(
        input_sst=args.input,
        output_dir=args.output_dir,
        pack_id=args.pack_id,
        display_name=args.display_name,
        game=args.game,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        prefer_newer=args.prefer_newer,
    )
    print(json.dumps(stats.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
