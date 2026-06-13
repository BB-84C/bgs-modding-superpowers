"""Resolve archive load order from plugins.txt + naming convention.

Phase 1 scope: convention-based attachment only. `SArchiveList` INI handling
is deferred to Phase 3. Archives with no matching enabled plugin are flagged
as `unattached` (would not load in the real game without explicit INI list).

Per-game naming convention:
    Skyrim LE / SE / AE / VR:
        <base>.bsa
        <base> - Textures.bsa
    Fallout 3 / Fallout New Vegas:
        <base>.bsa
        <base> - Textures.bsa
    Fallout 4 / Fallout 4 VR:
        <base> - Main.ba2
        <base> - Textures.ba2
    Starfield:
        <base> - Main.ba2
        <base> - Textures.ba2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Game(StrEnum):
    SKYRIM = "skyrim"  # LE / SE / AE / VR (same archive convention)
    FALLOUT3_FNV = "fallout3-fnv"
    FALLOUT4 = "fallout4"  # incl. VR
    STARFIELD = "starfield"


_NAMING_CONVENTIONS: dict[Game, tuple[tuple[str, str], ...]] = {
    Game.SKYRIM: ((".bsa", " - Textures.bsa"),),
    Game.FALLOUT3_FNV: ((".bsa", " - Textures.bsa"),),
    Game.FALLOUT4: ((" - Main.ba2", " - Textures.ba2"),),
    Game.STARFIELD: ((" - Main.ba2", " - Textures.ba2"),),
}


@dataclass(frozen=True)
class ArchiveLoadOrder:
    ordered_archives: list[str] = field(default_factory=list)
    unattached_archives: list[str] = field(default_factory=list)

    def rank_of(self, archive_name: str) -> int | None:
        try:
            return self.ordered_archives.index(archive_name)
        except ValueError:
            return None


def discover_archives_for_plugins(
    *,
    plugins: list[str],
    candidate_archives: list[str],
    game: Game,
) -> ArchiveLoadOrder:
    conventions = _NAMING_CONVENTIONS[game]
    candidate_set = set(candidate_archives)
    ordered: list[str] = []
    matched: set[str] = set()

    for plugin_name in plugins:
        base = _strip_plugin_suffix(plugin_name)
        for main_suffix, textures_suffix in conventions:
            main_archive = f"{base}{main_suffix}"
            textures_archive = f"{base}{textures_suffix}"
            if main_archive in candidate_set:
                ordered.append(main_archive)
                matched.add(main_archive)
            if textures_archive in candidate_set:
                ordered.append(textures_archive)
                matched.add(textures_archive)

    unattached = [a for a in candidate_archives if a not in matched]
    return ArchiveLoadOrder(ordered_archives=ordered, unattached_archives=unattached)


def _strip_plugin_suffix(plugin_name: str) -> str:
    for suffix in (".esp", ".esm", ".esl"):
        if plugin_name.lower().endswith(suffix):
            return plugin_name[: -len(suffix)]
    return plugin_name
