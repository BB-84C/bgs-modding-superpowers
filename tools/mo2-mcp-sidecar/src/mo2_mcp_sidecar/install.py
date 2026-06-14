"""Install pipeline JSON-RPC methods - PLAN-PATCH P-B6.

install.conflict_preview: preview conflicts between staged files and current
profile's enabled mods. Uses the engine's real file enumerator
(mo2_assets_engine.mod_enumerator.enumerate_mod_files) so loose files AND
attached BSA/BA2 members are checked, not just a non-existent `Mod.files`
attribute (that was the dead branch flagged in last turn's CONCERNS).

install.stage_fomod: (next task) combine fomod.resolve_files + extraction.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .envelope import register_method
from .world import WorldCache

# Sibling-dep import shim (mirror of world.py's shim) so this module is
# importable even when the test runner hasn't touched world.py yet.
_engine_src = Path(__file__).resolve().parents[4] / "tools" / "mo2-assets-engine" / "src"
if _engine_src.exists() and str(_engine_src) not in sys.path:
    sys.path.insert(0, str(_engine_src))

_cache: WorldCache | None = None


def init_install(cache: WorldCache) -> None:
    """Wire the shared WorldCache (same one assets.py uses)."""
    global _cache
    _cache = cache


def _normalize(p: str) -> str:
    """Lowercase + forward-slash + no leading slash.

    Matches FileEntry.relative_path (which is already as_posix().lower()) so
    staged-vs-mod overlap comparison is case-insensitive (NTFS default).
    """
    return str(p).replace("\\", "/").lstrip("/").lower()


def _normalize_staged_paths(staged_files: list[Any]) -> set[str]:
    """staged_files may be list[str] (relative paths) or list[{source, destination}]."""
    normalized: set[str] = set()
    for f in staged_files:
        if isinstance(f, dict):
            dst = f.get("destination") or f.get("source")
            if dst:
                normalized.add(_normalize(dst))
        elif isinstance(f, str):
            normalized.add(_normalize(f))
    return normalized


def _enumerate_via_engine(mod: Any, archive_order: Any) -> set[str] | None:
    """Call engine's enumerate_mod_files on a real Mod; return None on import/call failure.

    Returns a set of normalized relative paths or None if the engine path could
    not be exercised (e.g. mod has no on-disk root, or engine itself raised).
    """
    try:
        from mo2_assets_engine.archive_order import (  # type: ignore[import-not-found]
            ArchiveLoadOrder,
        )
        from mo2_assets_engine.mod_enumerator import (  # type: ignore[import-not-found]
            enumerate_mod_files,
        )
    except ImportError:
        return None

    ao = archive_order if archive_order is not None else ArchiveLoadOrder()
    try:
        entries = enumerate_mod_files(mod=mod, archive_order=ao)
    except Exception:
        return None
    # FileEntry.relative_path is already lowercase-posix for loose; archive
    # members come straight from BSA/BA2 directories which may include
    # backslashes -> normalize defensively.
    return {_normalize(e.relative_path) for e in entries}


def _mod_files_set(mod: Any, archive_order: Any) -> set[str]:
    """Resolve the set of relative file paths for a mod.

    Real engine `Mod` dataclass (mo2_assets_engine.types.Mod) has no `files`
    field, so production must go through enumerate_mod_files. Unit-test fakes
    (MagicMock with `m.files = [...]`) supply the list directly; we dispatch
    on isinstance to keep both paths honest.
    """
    try:
        from mo2_assets_engine.types import Mod as EngineMod  # type: ignore[import-not-found]
    except ImportError:
        EngineMod = None  # type: ignore[assignment]

    if EngineMod is not None and isinstance(mod, EngineMod):
        # Production path
        paths = _enumerate_via_engine(mod, archive_order)
        return paths if paths is not None else set()

    # Legacy mock path (unit tests)
    mod_files = getattr(mod, "files", None)
    if not mod_files or not isinstance(mod_files, (list, tuple, set, frozenset)):
        return set()
    return {_normalize(p) for p in mod_files}


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
    archive_order = getattr(world, "archive_order", None)

    conflicts = []
    for mod in mods:
        mod_set = _mod_files_set(mod, archive_order)
        if not mod_set:
            continue
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
