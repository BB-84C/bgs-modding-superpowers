"""JSON-RPC methods that wrap mo2_assets_engine via the WorldCache.

PLAN-PATCH P-B7: game is stored on the WorldCache (Task 25); each method
re-uses the cache so the engine sees consistent (profile_dir, game) per call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .envelope import register_method
from .world import WorldCache

_cache: WorldCache | None = None

# Map sidecar --game choices to mo2_assets_engine Game enum values.
_GAME_MAP: dict[str, str] = {
    "FALLOUT4": "fallout4",
    "SKYRIM_SE": "skyrim",
    "SKYRIM_LE": "skyrim",
    "STARFIELD": "starfield",
    "OBLIVION": "oblivion",
    "FALLOUT_NV": "fallout3-fnv",
}


def init_assets(cache: WorldCache) -> None:
    """Called once from __main__.py after parsing CLI args."""
    global _cache
    _cache = cache


def _world(profile_dir: str):
    if _cache is None:
        raise RuntimeError("assets module not initialized; init_assets() must run first")
    return _cache.get(Path(profile_dir))


def _build_entries_by_mod(w: Any) -> dict[str, list[Any]]:
    """Enumerate files per mod using mo2_assets_engine (with archive order)."""
    from mo2_assets_engine.archive_order import (  # type: ignore[import-not-found]
        Game as EngineGame,
        discover_archives_for_plugins,
    )
    from mo2_assets_engine.mod_enumerator import enumerate_mod_files  # type: ignore[import-not-found]

    engine_game = EngineGame(_GAME_MAP.get(w.game, "fallout4"))
    profile = w.profile
    plugins = profile.enabled_plugins if hasattr(profile, "enabled_plugins") else []

    # Discover attached archives from the mods root
    candidate_archives: list[str] = []
    mods_root = _cache.mods_root if _cache else Path(".")
    for mod in (w.mods or []):
        mod_path = mod.root if hasattr(mod, "root") else mods_root / str(mod)
        if not mod_path.exists():
            continue
        for child in mod_path.iterdir():
            if child.is_file() and child.suffix.lower() in (".bsa", ".ba2"):
                candidate_archives.append(child.name.lower())

    archive_order = discover_archives_for_plugins(
        plugins=plugins,
        candidate_archives=list(set(candidate_archives)),
        game=engine_game,
    )

    entries_by_mod: dict[str, list[Any]] = {}
    for mod in w.mods or []:
        mod_name = mod.name if hasattr(mod, "name") else str(mod)
        try:
            entries = enumerate_mod_files(mod=mod, archive_order=archive_order)
        except Exception:
            entries = []
        entries_by_mod[mod_name] = entries
    return entries_by_mod


def assets_summary(params: dict) -> dict:
    """Return summary counts for a profile."""
    profile_dir = params["profile_dir"]
    w = _world(profile_dir)
    return {
        "profile_name": Path(profile_dir).name,
        "game": w.game,
        "mod_count": len(w.mods) if w.mods else 0,
        "enabled_mod_count": sum(1 for m in (w.mods or []) if getattr(m, "enabled", False)),
    }


def assets_conflicts(params: dict) -> dict:
    """Compute conflict resolution. Bounded output via max_results (default 10000)."""
    profile_dir = params["profile_dir"]
    max_results = params.get("max_results", 10000)
    path_prefix = params.get("path_prefix")
    w = _world(profile_dir)
    try:
        from mo2_assets_engine.conflict_resolver import resolve_all_winners  # type: ignore[import-not-found]
    except ImportError:
        return {"conflicts": [], "total_count": 0, "truncated": False,
                "error": "mo2_assets_engine.conflict_resolver not importable"}
    entries_by_mod = _build_entries_by_mod(w)
    winners = resolve_all_winners(mods=w.mods or [], entries_by_mod=entries_by_mod)
    conflicts = list(winners.values())
    if path_prefix:
        conflicts = [c for c in conflicts if c.relative_path.startswith(path_prefix)]
    truncated = len(conflicts) > max_results
    # Convert ResolvedWinner dataclass instances to dicts for JSON
    out = []
    for c in conflicts[:max_results]:
        entry = {}
        for k, v in c.__dict__.items():
            if hasattr(v, "__dict__"):
                entry[k] = {sk: str(sv) for sk, sv in v.__dict__.items()}
            elif isinstance(v, list):
                entry[k] = [
                    {sk: str(sv) for sk, sv in item.__dict__.items()}
                    if hasattr(item, "__dict__") else item
                    for item in v
                ]
            else:
                entry[k] = str(v) if v is not None and not isinstance(v, (str, int, float, bool, list, dict)) else v
        out.append(entry)
    return {"conflicts": out, "total_count": len(conflicts), "truncated": truncated}


def assets_resolve_file(params: dict) -> dict:
    """Resolve a single virtual_path to winner + providers."""
    profile_dir = params["profile_dir"]
    virtual_path = params["virtual_path"]
    w = _world(profile_dir)
    try:
        from mo2_assets_engine.conflict_resolver import resolve_all_winners  # type: ignore[import-not-found]
    except ImportError:
        return {"virtual_path": virtual_path, "winner": None, "providers": [],
                "error": "resolve_all_winners not importable"}
    entries_by_mod = _build_entries_by_mod(w)
    winners = resolve_all_winners(mods=w.mods or [], entries_by_mod=entries_by_mod)
    winner = winners.get(virtual_path)
    if winner is None:
        return {"virtual_path": virtual_path, "winner": None, "providers": []}
    providers = [entry.owner_mod for entry in winner.losers] + [winner.winner.owner_mod]
    entry = {}
    for k, v in winner.__dict__.items():
        if hasattr(v, "__dict__"):
            entry[k] = {sk: str(sv) for sk, sv in v.__dict__.items()}
        elif isinstance(v, list):
            entry[k] = []
        else:
            entry[k] = str(v) if v is not None else v
    return {"virtual_path": virtual_path, "winner": entry, "providers": providers}


def world_invalidate(params: dict) -> dict:
    """Explicit cache invalidation — called by MCP after T2/T3 apply."""
    profile_dir = params["profile_dir"]
    if _cache is None:
        return {"invalidated": False, "reason": "cache_not_init"}
    _cache.invalidate(Path(profile_dir))
    return {"invalidated": True, "profile_dir": profile_dir}


def register() -> None:
    """Register all asset JSON-RPC methods. Call after init_assets()."""
    register_method("assets.summary", assets_summary)
    register_method("assets.conflicts", assets_conflicts)
    register_method("assets.resolve_file", assets_resolve_file)
    register_method("world.invalidate", world_invalidate)
