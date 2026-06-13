"""Unit tests for the mobase bridge.

The bridge is tested against a fake IOrganizer that mimics the mobase API
shape - we do NOT depend on a real MO2 process for these tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from Mo2AssetsInspector.bridge import (
    PathsBundle,
    UnsupportedGameError,
    bundle_paths_from_organizer,
)


def _fake_organizer(profile_path: str, mods_path: str, game_short: str) -> MagicMock:
    organizer = MagicMock()
    organizer.profilePath.return_value = profile_path
    organizer.modsPath.return_value = mods_path
    organizer.managedGame.return_value.gameShortName.return_value = game_short
    return organizer


@pytest.mark.parametrize(
    "game_short, expected_game_value",
    [
        ("Fallout4", "fallout4"),
        ("Fallout4VR", "fallout4"),
        ("SkyrimSE", "skyrim"),
        ("SkyrimAE", "skyrim"),
        ("SkyrimVR", "skyrim"),
        ("Skyrim", "skyrim"),
        ("Starfield", "starfield"),
        ("Fallout3", "fallout3-fnv"),
        ("FalloutNV", "fallout3-fnv"),
    ],
)
def test_bridge_maps_known_games(game_short: str, expected_game_value: str) -> None:
    organizer = _fake_organizer(r"C:\MO2\profiles\Default", r"C:\MO2\mods", game_short)
    bundle = bundle_paths_from_organizer(organizer)
    assert isinstance(bundle, PathsBundle)
    assert bundle.profile_dir == Path(r"C:\MO2\profiles\Default")
    assert bundle.mods_root == Path(r"C:\MO2\mods")
    assert bundle.game.value == expected_game_value


def test_bridge_raises_unsupported_game() -> None:
    organizer = _fake_organizer(r"C:\MO2\profiles\Default", r"C:\MO2\mods", "TES3Morrowind")
    with pytest.raises(UnsupportedGameError) as excinfo:
        bundle_paths_from_organizer(organizer)
    assert "TES3Morrowind" in str(excinfo.value)
