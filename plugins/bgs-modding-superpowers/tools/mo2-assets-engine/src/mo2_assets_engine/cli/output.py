"""Output formatters: human-readable and JSON.

JSON shape is the agent-facing contract and mirrors the future MO2 MCP
tool shape (`assets_summary`, `assets_mod_conflicts`, `assets_resolve_file`,
`assets_archive_inventory`).
"""

from __future__ import annotations

from typing import Any

from ..types import (
    ArchiveEntry,
    ConflictReport,
    FileEntry,
    Mod,
    ResolvedWinner,
)


def file_entry_to_dict(entry: FileEntry) -> dict[str, Any]:
    out: dict[str, Any] = {
        "path": entry.relative_path,
        "kind": entry.kind.value,
        "owner_mod": entry.owner_mod,
    }
    if entry.archive is not None:
        out["archive"] = archive_entry_to_dict(entry.archive)
    return out


def archive_entry_to_dict(archive: ArchiveEntry) -> dict[str, Any]:
    return {"name": archive.name, "kind": archive.kind.value, "load_order": archive.load_order}


def resolved_winner_to_dict(winner: ResolvedWinner) -> dict[str, Any]:
    return {
        "path": winner.relative_path,
        "bucket": winner.bucket.value,
        "winner": file_entry_to_dict(winner.winner),
        "losers": [file_entry_to_dict(loser) for loser in winner.losers],
    }


def conflict_report_to_dict(report: ConflictReport) -> dict[str, Any]:
    return {
        "mod": report.mod.name,
        "kept": [resolved_winner_to_dict(w) for w in report.kept],
        "overwritten": [resolved_winner_to_dict(w) for w in report.overwritten],
        "no_conflict": [entry.relative_path for entry in report.no_conflict],
    }


def mod_summary_to_dict(
    mod: Mod, total_files: int, total_conflicts: int
) -> dict[str, Any]:
    return {
        "name": mod.name,
        "priority": mod.priority,
        "total_files": total_files,
        "total_conflicts": total_conflicts,
    }


def render_summary_human(rows: list[dict[str, Any]]) -> str:
    lines = ["priority  name                              files   conflicts"]
    lines.extend(
        f"{row['priority']:>8}  {row['name']:<32}  {row['total_files']:>5}   {row['total_conflicts']:>5}"
        for row in rows
    )
    return "\n".join(lines)
