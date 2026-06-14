"""Install pipeline JSON-RPC methods - PLAN-PATCH P-B6.

install.conflict_preview: preview conflicts between staged files and current
profile's enabled mods.
install.stage_fomod: (next task) combine fomod.resolve_files + extraction.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .envelope import register_method
from .world import WorldCache

_cache: WorldCache | None = None


def init_install(cache: WorldCache) -> None:
    """Wire the shared WorldCache (same one assets.py uses)."""
    global _cache
    _cache = cache


def _normalize_staged_paths(staged_files: list[Any]) -> set[str]:
    """staged_files may be list[str] (relative paths) or list[{source, destination}]."""
    normalized: set[str] = set()
    for f in staged_files:
        if isinstance(f, dict):
            dst = f.get("destination") or f.get("source")
            if dst:
                normalized.add(str(dst).replace("\\", "/").lstrip("/"))
        elif isinstance(f, str):
            normalized.add(f.replace("\\", "/").lstrip("/"))
    return normalized


def install_conflict_preview(params: dict) -> dict:
    """Preview conflicts between staged install content and current profile's mods.

    Args:
        params["profile_dir"]: absolute path to active profile dir
        params["staged_files"]: list of relative paths OR list of {source, destination}
        params["target_priority"]: "top" | "bottom" | int - where the staged mod would go

    Returns:
        {
          "summary": "<X> overlapping files across <Y> existing mods",
          "conflicts": [{"with_mod": str, "shared_count": int, "shared_files": [str]}],
          "staged_file_count": int,
        }
    """
    if _cache is None:
        return {"summary": "cache_not_initialized", "conflicts": [],
                "staged_file_count": 0, "error": "init_install not called"}

    profile_dir = Path(params["profile_dir"])
    staged_files = params.get("staged_files", [])
    target_priority = params.get("target_priority", "bottom")  # informational; not used for now

    staged_set = _normalize_staged_paths(staged_files)
    if not staged_set:
        return {"summary": "no staged files", "conflicts": [],
                "staged_file_count": 0, "target_priority": target_priority}

    world = _cache.get(profile_dir)
    mods = world.mods if world.mods else []

    conflicts = []
    for mod in mods:
        # mo2_assets_engine Mod objects may expose `files` (set/list of relative paths).
        # Adapt to whatever attribute name the engine actually uses.
        mod_files = getattr(mod, "files", None)
        if mod_files is None:
            # Try fallback attribute names
            mod_files = getattr(mod, "file_paths", None) or getattr(mod, "all_files", None)
        if not mod_files:
            continue
        # Normalize mod files to the same form as staged paths
        mod_set = {str(p).replace("\\", "/").lstrip("/") for p in mod_files}
        overlap = sorted(mod_set & staged_set)
        if overlap:
            conflicts.append({
                "with_mod": getattr(mod, "name", "<unknown>"),
                "shared_count": len(overlap),
                "shared_files": overlap[:50],  # cap per-mod sample for response budget
            })

    total_shared = sum(c["shared_count"] for c in conflicts)
    summary = f"{total_shared} overlapping files across {len(conflicts)} existing mods"
    return {
        "summary": summary,
        "conflicts": conflicts,
        "staged_file_count": len(staged_set),
        "target_priority": target_priority,
    }


def register() -> None:
    register_method("install.conflict_preview", install_conflict_preview)
    # stage_fomod registered in next task
