"""Output formatters: human-readable and JSON."""

from __future__ import annotations

from typing import Any

from ..conflict_resolver import ResolvedFile
from ..types import Mod
from ..virtual_data_tree import Provider


def provider_to_dict(provider: Provider) -> dict[str, Any]:
    out: dict[str, Any] = {
        "mod": provider.source_mod,
        "source_type": provider.source_type.value,
    }
    if provider.archive_name is not None:
        out["archive_name"] = provider.archive_name
    if provider.attached_plugin is not None:
        out["attached_plugin"] = provider.attached_plugin
        out["attached_plugin_load_order"] = provider.attached_plugin_load_order
    return out


def resolved_file_to_dict(resolved: ResolvedFile) -> dict[str, Any]:
    return {
        "path": resolved.relative_path,
        "winner": provider_to_dict(resolved.winner),
        "losers": [provider_to_dict(loser) for loser in resolved.losers],
        "is_conflict": resolved.is_conflict,
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
