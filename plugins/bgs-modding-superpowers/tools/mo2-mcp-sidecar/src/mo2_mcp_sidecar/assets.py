"""JSON-RPC methods that expose the mo2_assets_engine virtual Data tree."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .envelope import register_method
from .world import WorldCache

_cache: WorldCache | None = None


def init_assets(cache: WorldCache) -> None:
    """Called once from __main__.py after parsing CLI args."""
    global _cache
    _cache = cache


def _world(profile_dir: str):
    if _cache is None:
        raise RuntimeError("assets module not initialized; init_assets() must run first")
    return _cache.get(Path(profile_dir))


def _normalize_virtual_path(path: str) -> str:
    """Normalize a virtual path to the engine's storage convention."""
    if not path:
        return path
    p = path.replace("\\", "/")
    while p.startswith("/"):
        p = p[1:]
    if len(p) >= 5 and p[:5].lower() == "data/":
        p = p[5:]
        while p.startswith("/"):
            p = p[1:]
    return p.lower()


def _provider_to_wire(provider: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "mod": provider.source_mod,
        "source_type": provider.source_type.value,
    }
    if provider.archive_name is not None:
        out["archive_name"] = provider.archive_name
    return out


def _resolved_to_wire(resolved: Any) -> dict[str, Any]:
    return {
        "relative_path": resolved.relative_path,
        "winner": _provider_to_wire(resolved.winner),
        "losers": [_provider_to_wire(loser) for loser in resolved.losers],
        "is_conflict": resolved.is_conflict,
    }


def _empty_report(mod_name: str) -> dict:
    return {
        "mod": mod_name,
        "total_files": 0,
        "files_winning": 0,
        "files_losing": 0,
        "files_unique": 0,
        "overridden_by": [],
        "overrides": [],
        "winners_by_file": {},
    }


def _counter_to_sorted_list(counter: Counter[str]) -> list[dict[str, int | str]]:
    return [
        {"mod": mod, "files": count}
        for mod, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
    ]


def assets_summary(params: dict) -> dict:
    """Return summary counts for a profile."""
    profile_dir = params["profile_dir"]
    w = _world(profile_dir)
    tree = w.tree
    return {
        "profile_name": Path(profile_dir).name,
        "game": w.game,
        "mod_count": len(w.mods) if w.mods else 0,
        "enabled_mod_count": sum(1 for m in (w.mods or []) if getattr(m, "enabled", False)),
        "plugin_count": len(tree.plugins),
        "archive_count": len(tree.archives),
        "attached_archive_count": _attached_archive_count(tree),
        "unattached_archive_count": len(tree.unattached_archives),
        "file_count": len(tree.file_providers),
    }


def _attached_archive_count(tree: Any) -> int:
    loaded = {
        provider.archive_name.lower()
        for providers in tree.file_providers.values()
        for provider in providers
        if provider.archive_name is not None
    }
    return len(loaded)


def assets_conflicts(params: dict) -> dict:
    """Compute conflict resolution. Bounded output via max_results (default 10000)."""
    profile_dir = params["profile_dir"]
    max_results = params.get("max_results", 10000)
    path_prefix = params.get("path_prefix")
    if path_prefix:
        path_prefix = _normalize_virtual_path(path_prefix)
    w = _world(profile_dir)
    from mo2_assets_engine.conflict_resolver import resolve_tree  # type: ignore[import-not-found]

    resolved = [item for item in resolve_tree(w.tree).values() if item.is_conflict]
    if path_prefix:
        resolved = [item for item in resolved if item.relative_path.startswith(path_prefix)]
    resolved.sort(key=lambda item: item.relative_path)
    truncated = len(resolved) > max_results
    return {
        "conflicts": [_resolved_to_wire(item) for item in resolved[:max_results]],
        "total_count": len(resolved),
        "truncated": truncated,
    }


def assets_resolve_file(params: dict) -> dict:
    """Resolve a single virtual_path to winner + loser providers."""
    profile_dir = params["profile_dir"]
    virtual_path = params["virtual_path"]
    lookup_key = _normalize_virtual_path(virtual_path)
    w = _world(profile_dir)
    from mo2_assets_engine.conflict_resolver import resolve_tree  # type: ignore[import-not-found]

    resolved = resolve_tree(w.tree).get(lookup_key)
    if resolved is None:
        return {
            "virtual_path": virtual_path,
            "relative_path": lookup_key,
            "winner": None,
            "losers": [],
            "is_conflict": False,
        }
    return {"virtual_path": virtual_path, **_resolved_to_wire(resolved)}


def assets_report_for_mod(params: dict) -> dict:
    """Return a compact conflict preview report for one mod."""
    profile_dir = params["profile_dir"]
    mod_name = params["mod_name"]
    w = _world(profile_dir)
    mods = w.mods or []
    if not any(getattr(mod, "name", None) == mod_name for mod in mods):
        return _empty_report(mod_name)

    from mo2_assets_engine.conflict_resolver import resolve_tree  # type: ignore[import-not-found]

    resolved = resolve_tree(w.tree)
    overridden_by: Counter[str] = Counter()
    overrides: Counter[str] = Counter()
    winners_by_file: dict[str, str] = {}
    files_winning = 0
    files_losing = 0
    files_unique = 0
    total_files = 0

    for path, providers in sorted(w.tree.file_providers.items()):
        if not any(provider.source_mod == mod_name for provider in providers):
            continue
        total_files += 1
        item = resolved[path]
        winners_by_file[path] = item.winner.source_mod
        if not item.is_conflict:
            files_unique += 1
        elif item.winner.source_mod == mod_name:
            files_winning += 1
            for loser in item.losers:
                if loser.source_mod != mod_name:
                    overrides[loser.source_mod] += 1
        else:
            files_losing += 1
            overridden_by[item.winner.source_mod] += 1

    return {
        "mod": mod_name,
        "total_files": total_files,
        "files_winning": files_winning,
        "files_losing": files_losing,
        "files_unique": files_unique,
        "overridden_by": _counter_to_sorted_list(overridden_by),
        "overrides": _counter_to_sorted_list(overrides),
        "winners_by_file": winners_by_file,
    }


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
    register_method("assets.report_for_mod", assets_report_for_mod)
    register_method("assets.resolve_file", assets_resolve_file)
    register_method("world.invalidate", world_invalidate)
