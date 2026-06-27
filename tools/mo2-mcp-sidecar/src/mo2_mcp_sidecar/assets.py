"""JSON-RPC methods that wrap mo2_assets_engine via the WorldCache.

PLAN-PATCH P-B7: game is stored on the WorldCache (Task 25); each method
re-uses the cache so the engine sees consistent (profile_dir, game) per call.
"""
from __future__ import annotations

from collections import Counter
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


def _normalize_virtual_path(path: str) -> str:
    """Normalize a virtual path to mo2_assets_engine's storage convention.

    BUG-25 (WL2 Lane 4D, run-20260617T002922Z): mo2_assets_resolve returned
    {winner: null, providers: []} for inputs like
    'Data/textures/BNS/Landscape/Grass/FernGrass01_d.DDS' on an 803-mod WL2
    profile that demonstrably contained the file (mo2_assets_summary returned
    mod_count=803 against the same cache). Root cause: mod_enumerator.py:33
    stores each FileEntry.relative_path as

        path.relative_to(mod.root).as_posix().lower()

    i.e. paths are BOTH mod-relative (no 'Data/' prefix, matching MO2's VFS
    internal convention where mods/<Mod>/textures/foo.dds projects to
    Data/textures/foo.dds at runtime) AND lowercased. The winners dict
    returned by conflict_resolver.resolve_all_winners is keyed on those
    normalized values, but assets_resolve_file / assets_conflicts used to
    pass the agent's raw input straight through to winners.get(...) /
    str.startswith(...), so any caller that did the obvious "ask for the
    runtime path I see" thing got a silent miss.

    Normalization steps, in order:

    1. Convert backslashes to forward slashes (defensive: MO2 VFS is
       posix-style, but Windows-side callers and Pip-Boy displays
       occasionally mix separators).
    2. Strip leading slashes ('/Data/foo', '//Data/foo').
    3. Strip ONE leading 'Data/' segment, case-insensitive
       ('Data/', 'data/', 'DATA/', 'DaTa/'). Only the leading segment;
       a nested 'data/' deeper in the tree (e.g. 'textures/data/foo.dds',
       which is a real path a mod can legitimately ship) is preserved.
    4. Strip residual leading slashes that step 3 may have left behind
       (handles 'Data//foo' -> '/foo' -> 'foo').
    5. Lowercase the result so '.DDS' / 'Foo' / 'BNS' match the engine's
       lowercased storage.

    Empty input is returned as-is; callers handle empty as "no filter" /
    "no path".
    """
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


def _build_entries_by_mod(w: Any) -> dict[str, list[Any]]:
    """Enumerate files per mod using mo2_assets_engine (with archive order).

    F-M2: reuse World.archive_order computed once by WorldCache._build() instead
    of re-scanning the mods root and re-running discover_archives_for_plugins on
    every assets.* call. The candidate-archive scan is O(mods x dir-entries) and
    becomes painful on 800-mod profiles. The legacy fallback below only fires
    for test fakes / pre-F-B7 cached worlds where archive_order is unset.
    """
    from mo2_assets_engine.mod_enumerator import enumerate_mod_files  # type: ignore[import-not-found]

    archive_order = getattr(w, "archive_order", None)
    if archive_order is None:
        # Legacy fallback path: discover in place. Kept for backward compat with
        # older cached worlds and any test fixture that constructs World without
        # going through WorldCache._build().
        from mo2_assets_engine.archive_order import (  # type: ignore[import-not-found]
            Game as EngineGame,
            discover_archives_for_plugins,
        )
        engine_game = EngineGame(_GAME_MAP.get(w.game, "fallout4"))
        profile = w.profile
        plugins = profile.enabled_plugins if hasattr(profile, "enabled_plugins") else []
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
    # BUG-25: normalize path_prefix to engine convention (mod-relative, lowercase,
    # no 'Data/' prefix) so callers can pass either 'textures/' (already-correct
    # storage form) or 'Data/textures/' (the runtime VFS form they actually see)
    # and get the same filter. See _normalize_virtual_path() for full rationale.
    if path_prefix:
        path_prefix = _normalize_virtual_path(path_prefix)
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
    # BUG-25: normalize input for the winners-dict lookup. The original
    # virtual_path is echoed back in the response so callers see the path
    # they asked for, not the storage form.
    lookup_key = _normalize_virtual_path(virtual_path)
    w = _world(profile_dir)
    try:
        from mo2_assets_engine.conflict_resolver import resolve_all_winners  # type: ignore[import-not-found]
    except ImportError:
        return {"virtual_path": virtual_path, "winner": None, "providers": [],
                "error": "resolve_all_winners not importable"}
    entries_by_mod = _build_entries_by_mod(w)
    winners = resolve_all_winners(mods=w.mods or [], entries_by_mod=entries_by_mod)
    winner = winners.get(lookup_key)
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
    # Keep the detailed ResolvedWinner fields for compatibility, but expose the
    # actual winning FileEntry's owner directly.  The MCP contract is
    # `result.winner.owner_mod`; nesting it under `winner.winner.owner_mod`
    # made AT19 and human callers treat a valid winner as missing.
    entry["owner_mod"] = winner.winner.owner_mod
    entry["kind"] = str(winner.winner.kind)
    entry["archive"] = str(winner.winner.archive) if winner.winner.archive is not None else None
    return {"virtual_path": virtual_path, "winner": entry, "providers": providers}


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


def assets_report_for_mod(params: dict) -> dict:
    """Return a compact conflict preview report for one mod."""
    profile_dir = params["profile_dir"]
    mod_name = params["mod_name"]
    w = _world(profile_dir)
    mods = w.mods or []
    if not any(getattr(mod, "name", None) == mod_name for mod in mods):
        return _empty_report(mod_name)

    try:
        from mo2_assets_engine.conflict_resolver import ConflictResolver  # type: ignore[import-not-found]
    except ImportError:
        return {**_empty_report(mod_name), "error": "mo2_assets_engine.conflict_resolver not importable"}

    entries_by_mod = _build_entries_by_mod(w)
    try:
        report = ConflictResolver(mods=mods, entries_by_mod=entries_by_mod).report_for_mod(mod_name)
    except KeyError:
        return _empty_report(mod_name)

    overridden_by: Counter[str] = Counter()
    overrides: Counter[str] = Counter()
    winners_by_file: dict[str, str] = {}

    for item in report.overwritten:
        winner_mod = item.winner.owner_mod
        overridden_by[winner_mod] += 1
        winners_by_file[item.relative_path] = winner_mod

    for item in report.kept:
        winners_by_file[item.relative_path] = item.winner.owner_mod
        for loser in item.losers:
            overrides[loser.owner_mod] += 1

    for entry in report.no_conflict:
        winners_by_file[entry.relative_path] = entry.owner_mod

    total_files = len(report.kept) + len(report.overwritten) + len(report.no_conflict)
    return {
        "mod": report.mod.name,
        "total_files": total_files,
        "files_winning": len(report.kept),
        "files_losing": len(report.overwritten),
        "files_unique": len(report.no_conflict),
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
