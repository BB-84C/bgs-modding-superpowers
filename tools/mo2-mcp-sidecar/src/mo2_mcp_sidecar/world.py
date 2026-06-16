"""World cache: profile + mods enumeration with mtime-based invalidation.

PLAN-PATCH applied:
- P-B7: WorldCache accepts `game` parameter (FALLOUT4 / SKYRIM_SE / etc.)
- P-F10: Per-key threading lock coalesces concurrent _build() calls so two
  parallel requests don't both trigger a full enumeration.
- P-B6 (this task): World now carries `archive_order` (ArchiveLoadOrder from
  the engine) so install.conflict_preview can call
  mo2_assets_engine.mod_enumerator.enumerate_mod_files for real overlap
  detection instead of relying on a non-existent Mod.files attribute.
"""
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


# Sidecar --game value -> engine Game string value.
# Oblivion is not represented in the engine's Game enum (its archive conventions
# differ from Skyrim's slightly); when game is OBLIVION, archive discovery is
# skipped and an empty ArchiveLoadOrder is used (loose files still enumerate).
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
    archive_fingerprint: str


@dataclass
class World:
    profile: Any
    mods: Any
    game: str
    # archive_order is an mo2_assets_engine.archive_order.ArchiveLoadOrder when
    # built by _build(); kept Any-typed + None-defaulted so existing test fakes
    # that construct World(profile=..., mods=..., game=...) keep working.
    archive_order: Any = None


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
            archive_fingerprint=self._archive_fingerprint(modlist),
        )

    def _archive_fingerprint(self, modlist: Path) -> str:
        """Return a cheap content fingerprint for enabled mod archives.

        The cache is primarily invalidated by profile files, but users can swap
        .ba2/.bsa files in an enabled mod without touching modlist.txt.  Include
        archive relative path, size, and mtime_ns so those replacements rebuild
        the world on the next asset query.
        """
        digest = hashlib.sha256()
        for mod_name in self._enabled_mod_names(modlist):
            mod_root = self.mods_root / mod_name
            if not mod_root.exists() or not mod_root.is_dir():
                continue
            archive_entries: list[tuple[str, int, int]] = []
            for archive in mod_root.rglob("*"):
                if not archive.is_file() or archive.suffix.lower() not in (".ba2", ".bsa"):
                    continue
                try:
                    stat = archive.stat()
                except OSError:
                    continue
                archive_entries.append((archive.relative_to(mod_root).as_posix(), stat.st_size, stat.st_mtime_ns))
            for rel_path, size, mtime_ns in sorted(archive_entries):
                digest.update(mod_name.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0")
                digest.update(rel_path.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0")
                digest.update(str(size).encode("ascii"))
                digest.update(b"\0")
                digest.update(str(mtime_ns).encode("ascii"))
                digest.update(b"\0")
        return digest.hexdigest()

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
                out.append(line[1:])
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
        """Build a World by reading profile + computing archive_order.

        P-B7: passes `game` to World.
        P-B6: discovers .bsa/.ba2 archives across enabled mods and builds an
        ArchiveLoadOrder so enumerate_mod_files() can attribute archived files.
        """
        # Lazy engine imports (sibling-dep shim above puts src/ on sys.path).
        from mo2_assets_engine.archive_order import (  # type: ignore[import-not-found]
            ArchiveLoadOrder,
            Game,
            discover_archives_for_plugins,
        )
        from mo2_assets_engine.profile import read_profile  # type: ignore[import-not-found]

        profile = read_profile(profile_dir=profile_dir, mods_root=self.mods_root)

        # Discover candidate archives (.bsa/.ba2) at the root of each enabled mod.
        # Same convention as mod_enumerator._enumerate_archives.
        candidate_archives: list[str] = []
        for mod in profile.enabled_mods:
            if not mod.root.exists():
                continue
            for child in sorted(mod.root.iterdir()):
                if child.is_file() and child.suffix.lower() in (".bsa", ".ba2"):
                    candidate_archives.append(child.name)

        engine_game_value = _ENGINE_GAME_VALUE.get(self.game)
        if engine_game_value is not None and candidate_archives:
            archive_order = discover_archives_for_plugins(
                plugins=profile.enabled_plugins,
                candidate_archives=candidate_archives,
                game=Game(engine_game_value),
            )
        else:
            # No archives to discover, or game not modeled by engine -> empty order.
            # Loose files still enumerate correctly; only archived members are skipped.
            archive_order = ArchiveLoadOrder()

        return World(
            profile=profile,
            mods=profile.enabled_mods,
            game=self.game,
            archive_order=archive_order,
        )
