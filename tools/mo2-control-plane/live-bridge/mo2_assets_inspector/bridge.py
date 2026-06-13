"""Resolve mobase IOrganizer state to engine-call arguments.

Does NOT walk IModList / IPluginList / IFileTree - the engine reads the
same on-disk state and is the single source of truth. This module only
maps "which profile / which mods root / which game" so the plugin and
the CLI exercise the exact same engine code paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mo2_assets_engine.archive_order import Game


class UnsupportedGameError(RuntimeError):
    """Raised when the active game is not one the engine supports yet."""


@dataclass(frozen=True)
class PathsBundle:
    profile_dir: Path
    mods_root: Path
    game: Game


_GAME_SHORT_NAME_MAP: dict[str, Game] = {
    # Skyrim line.
    "Skyrim": Game.SKYRIM,
    "SkyrimSE": Game.SKYRIM,
    "SkyrimAE": Game.SKYRIM,
    "SkyrimVR": Game.SKYRIM,
    # Fallout 4 line.
    "Fallout4": Game.FALLOUT4,
    "Fallout4VR": Game.FALLOUT4,
    # Starfield.
    "Starfield": Game.STARFIELD,
    # Older Fallouts.
    "Fallout3": Game.FALLOUT3_FNV,
    "FalloutNV": Game.FALLOUT3_FNV,
}


def bundle_paths_from_organizer(organizer: Any) -> PathsBundle:
    profile_dir = Path(organizer.profilePath())
    mods_root = Path(organizer.modsPath())
    game_short = organizer.managedGame().gameShortName()
    game = _GAME_SHORT_NAME_MAP.get(game_short)
    if game is None:
        raise UnsupportedGameError(
            f"Game '{game_short}' is not in the engine's Phase-1 coverage. "
            f"Supported: {sorted(_GAME_SHORT_NAME_MAP)}"
        )
    return PathsBundle(profile_dir=profile_dir, mods_root=mods_root, game=game)
