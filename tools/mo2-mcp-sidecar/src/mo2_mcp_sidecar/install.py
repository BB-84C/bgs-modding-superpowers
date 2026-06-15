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
        from mo2_assets_engine.archive_order import (  # type: ignore[import-untyped]
            ArchiveLoadOrder,
        )
        from mo2_assets_engine.mod_enumerator import (  # type: ignore[import-untyped]
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
        from mo2_assets_engine.types import Mod as EngineMod  # type: ignore[import-untyped]
    except ImportError:
        EngineMod = None

    if EngineMod is not None and isinstance(mod, EngineMod):
        # Production path
        paths = _enumerate_via_engine(mod, archive_order)
        return paths if paths is not None else set()

    # Legacy mock path (unit tests)
    mod_files = getattr(mod, "files", None)
    if not mod_files or not isinstance(mod_files, (list, tuple, set, frozenset)):
        return set()
    return {_normalize(p) for p in mod_files}


def install_conflict_preview(params: dict[str, Any]) -> dict[str, Any]:
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

    # Security audit: staged_files are only treated as logical relative names
    # for set comparison below. This function never joins them to profile_dir
    # or any other filesystem base, and it never writes staged content.
    staged_set = _normalize_staged_paths(staged_files)
    if not staged_set:
        return {"summary": "no staged files", "conflicts": [],
                "staged_file_count": 0, "target_priority": target_priority}

    world = _cache.get(profile_dir)
    mods = world.mods if world.mods else []
    archive_order = getattr(world, "archive_order", None)

    conflicts: list[dict[str, Any]] = []
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


def install_stage_fomod(params: dict[str, Any]) -> dict[str, Any]:
    """Stage a FOMOD archive into a directory using user-supplied choices.

    Pipeline:
    1. If archive_path is a .zip/.7z/.rar, extract to a temp scratch dir.
       Otherwise (directory) use it in place.
    2. Call fomod.fomod_resolve_files to get the {source, destination} list.
    3. For each pair, copy fomod_root/source -> staging_dir/destination.
    4. Clean up scratch dir (NOT staging_dir).

    Args:
        params["archive_path"]: absolute path to FOMOD archive (must be a directory
            with a fomod/ subdir, OR a .zip/.7z/.rar that contains one)
        params["choices"]: list of {page_name, selected_options: [{group_name, option_name}]}
        params["staging_dir"]: absolute path to destination - created if missing

    Returns:
        {
          "staging_dir": str,
          "file_count": int,
          "files": [{"source": str, "destination": str}],
          "archive_format": "directory" | "zip" | "7z" | "rar",
        }

    Raises:
        FileNotFoundError if archive missing
        RuntimeError("pyfomod_not_available") / ("not_a_fomod") / ("invalid_choices")
    """
    import shutil
    import tempfile

    from .archive import _validate_safe_member, archive_extract_all
    from .fomod import _PYFOMOD_AVAILABLE, fomod_resolve_files

    if not _PYFOMOD_AVAILABLE:
        raise RuntimeError("pyfomod_not_available")

    archive_path = Path(params["archive_path"])
    choices = params.get("choices", [])
    staging_dir = Path(params["staging_dir"])

    if not archive_path.exists():
        raise FileNotFoundError(f"archive not found: {archive_path}")
    if not isinstance(choices, list):
        raise RuntimeError("invalid_choices: choices must be a list")

    staging_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: pre-extracted directory vs archive
    scratch_dir: Path | None = None
    if archive_path.is_dir():
        fomod_root = archive_path
        archive_format = "directory"
    else:
        scratch_dir = Path(tempfile.mkdtemp(prefix="fomod-stage-"))
        extract_result = archive_extract_all({
            "archive_path": str(archive_path),
            "dest": str(scratch_dir),
        })
        archive_format = extract_result["format"]
        fomod_root = scratch_dir

    try:
        # Step 2: resolve files via pyfomod (reuses existing fomod.fomod_resolve_files)
        resolved = fomod_resolve_files({
            "archive_path": str(fomod_root),
            "choices": choices,
        })
        files = resolved.get("files", [])

        # Step 3: copy each source -> staging_dir/destination
        moved: list[dict[str, str]] = []
        for entry in files:
            src_rel = entry.get("source", "")
            dst_rel = entry.get("destination", "")
            if not src_rel or not dst_rel:
                continue
            src_path = _validate_safe_member(src_rel, fomod_root)
            dst_path = _validate_safe_member(dst_rel, staging_dir)
            if not src_path.exists():
                # FOMOD may reference files not in the extracted set (e.g. NotUsable
                # options) - silently skip rather than fail the whole stage.
                continue
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
                moved.append({"source": src_rel, "destination": dst_rel})
            elif src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                moved.append({"source": src_rel, "destination": dst_rel})

        return {
            "staging_dir": str(staging_dir),
            "file_count": len(moved),
            "files": moved,
            "archive_format": archive_format,
        }
    finally:
        # Step 4: clean up scratch dir (NOT staging_dir - that's the output)
        if scratch_dir is not None and scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)


def register() -> None:
    register_method("install.conflict_preview", install_conflict_preview)
    register_method("install.stage_fomod", install_stage_fomod)
