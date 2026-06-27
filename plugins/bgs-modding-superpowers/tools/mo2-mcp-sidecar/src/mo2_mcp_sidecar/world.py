"""World cache: profile + virtual Data tree with mtime-based invalidation."""
from __future__ import annotations

import sys
import threading
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Sibling-dep import shim for mo2_assets_engine (Option A from Task 25 spec)
_engine_src = Path(__file__).resolve().parents[4] / "tools" / "mo2-assets-engine" / "src"
if _engine_src.exists() and str(_engine_src) not in sys.path:
    sys.path.insert(0, str(_engine_src))


# Sidecar --game value -> engine Game string value.  Oblivion is not represented
# in the engine's Game enum; for that case the tree still projects loose files,
# but convention archive attachment is skipped.
_ENGINE_GAME_VALUE: dict[str, str | None] = {
    "FALLOUT4": "fallout4",
    "STARFIELD": "starfield",
    "SKYRIM_SE": "skyrim",
    "SKYRIM_LE": "skyrim",
    "FALLOUT_NV": "fallout3-fnv",
    "OBLIVION": None,
}


@dataclass(frozen=True)
class WorldKey:
    profile_dir: str
    modlist_mtime_ns: int
    plugins_mtime_ns: int
    content_fingerprint: str
    ini_fingerprint: str


@dataclass
class World:
    profile: Any
    mods: Any
    game: str
    tree: Any = None


class WorldCache:
    """Mtime-keyed cache of enumerated mods per profile, locked for concurrent safety."""

    def __init__(self, mods_root: Path, game: str) -> None:
        self.mods_root = Path(mods_root)
        self.game = game  # P-B7: passed to engine on each _build
        self._cache: dict[str, tuple[WorldKey, World]] = {}
        self._build_locks: dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()  # guards _build_locks dict mutation

    def _compute_key(self, profile_dir: Path) -> WorldKey:
        modlist = profile_dir / "modlist.txt"
        plugins = profile_dir / "plugins.txt"
        return WorldKey(
            profile_dir=str(profile_dir),
            modlist_mtime_ns=modlist.stat().st_mtime_ns if modlist.exists() else 0,
            plugins_mtime_ns=plugins.stat().st_mtime_ns if plugins.exists() else 0,
            content_fingerprint=self._content_fingerprint(modlist),
            ini_fingerprint=self._ini_fingerprint(profile_dir),
        )

    def _content_fingerprint(self, modlist: Path) -> str:
        """Return a cheap content fingerprint for enabled projected inputs.

        The tree depends on top-level plugins/archives and projected loose files.
        Include relative path, size, and mtime_ns so out-of-band file edits rebuild
        the world on the next asset query.
        """
        digest = hashlib.sha256()
        for mod_name in self._enabled_mod_names(modlist):
            mod_root = self.mods_root / mod_name
            if not mod_root.exists() or not mod_root.is_dir():
                continue
            file_entries: list[tuple[str, int, int]] = []
            for path in mod_root.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                file_entries.append((path.relative_to(mod_root).as_posix(), stat.st_size, stat.st_mtime_ns))
            for rel_path, size, mtime_ns in sorted(file_entries):
                digest.update(mod_name.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0")
                digest.update(rel_path.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0")
                digest.update(str(size).encode("ascii"))
                digest.update(b"\0")
                digest.update(str(mtime_ns).encode("ascii"))
                digest.update(b"\0")
        return digest.hexdigest()

    def _ini_fingerprint(self, profile_dir: Path) -> str:
        digest = hashlib.sha256()
        for ini_path in self._archive_ini_paths(profile_dir):
            digest.update(str(ini_path).encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
            if ini_path.exists():
                try:
                    stat = ini_path.stat()
                except OSError:
                    digest.update(b"error")
                else:
                    digest.update(str(stat.st_mtime_ns).encode("ascii"))
                    digest.update(b"\0")
                    digest.update(str(stat.st_size).encode("ascii"))
            else:
                digest.update(b"missing")
            digest.update(b"\0")
        return digest.hexdigest()

    def _archive_ini_paths(self, profile_dir: Path) -> list[Path]:
        base = _GAME_INI_BASENAME.get(self.game)
        if base is None:
            return []
        return [
            profile_dir / f"{base}.ini",
            profile_dir / f"{base}Prefs.ini",
            profile_dir / f"{base}Custom.ini",
        ]

    @staticmethod
    def _enabled_mod_names(modlist: Path) -> list[str]:
        if not modlist.exists():
            return []
        out: list[str] = []
        for raw_line in modlist.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or len(line) < 2:
                continue
            if line[0] == "+":
                name = line[1:]
                if not name.endswith("_separator"):
                    out.append(name)
        return out

    def _get_lock(self, key_str: str) -> threading.Lock:
        with self._registry_lock:
            lock = self._build_locks.get(key_str)
            if lock is None:
                lock = threading.Lock()
                self._build_locks[key_str] = lock
            return lock

    def get(self, profile_dir: Path) -> World:
        """Return cached World or rebuild if mtime changed. Lock coalesces concurrent builds."""
        key_str = str(profile_dir)
        lock = self._get_lock(key_str)
        with lock:
            current_key = self._compute_key(profile_dir)
            cached = self._cache.get(key_str)
            if cached and cached[0] == current_key:
                return cached[1]
            world = self._build(profile_dir)
            self._cache[key_str] = (current_key, world)
            return world

    def invalidate(self, profile_dir: Path) -> None:
        """Explicit invalidation (called by MCP after T2/T3 apply)."""
        key_str = str(profile_dir)
        with self._get_lock(key_str):
            self._cache.pop(key_str, None)

    def _build(self, profile_dir: Path) -> World:
        """Build a World by reading profile + constructing a virtual Data tree."""
        # Lazy engine imports (sibling-dep shim above puts src/ on sys.path).
        from mo2_assets_engine.archive_ini import read_archive_lists  # type: ignore[import-not-found]
        from mo2_assets_engine.archive_order import Game  # type: ignore[import-not-found]
        from mo2_assets_engine.profile import read_profile  # type: ignore[import-not-found]
        from mo2_assets_engine.virtual_data_tree import (  # type: ignore[import-not-found]
            build_virtual_data_tree,
        )

        profile = read_profile(profile_dir=profile_dir, mods_root=self.mods_root)
        engine_game_value = _ENGINE_GAME_VALUE.get(self.game)
        engine_game = Game(engine_game_value) if engine_game_value is not None else None
        ini_lists = read_archive_lists(self._archive_ini_paths(profile_dir))
        tree = build_virtual_data_tree(
            profile=profile,
            game=engine_game,
            ini_archive_lists=ini_lists,
        )

        return World(
            profile=profile,
            mods=profile.enabled_mods,
            game=self.game,
            tree=tree,
        )


_GAME_INI_BASENAME: dict[str, str] = {
    "FALLOUT4": "Fallout4",
    "STARFIELD": "Starfield",
    "SKYRIM_SE": "Skyrim",
    "SKYRIM_LE": "Skyrim",
    "FALLOUT_NV": "FalloutNV",
    "OBLIVION": "Oblivion",
}
