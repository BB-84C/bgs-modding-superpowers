"""Unit tests for asset JSON-RPC methods. Uses fake WorldCache, no real engine."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mo2_mcp_sidecar import assets
from mo2_mcp_sidecar.envelope import _METHODS


@pytest.fixture(autouse=True)
def reset_state():
    assets._cache = None
    _METHODS.clear()
    yield
    assets._cache = None
    _METHODS.clear()


def _fake_cache_with_world(world):
    cache = MagicMock()
    cache.get.return_value = world
    return cache


def test_init_assets_required_before_use():
    with pytest.raises(RuntimeError, match="not initialized"):
        assets.assets_summary({"profile_dir": "/tmp/p"})


def test_assets_summary_returns_counts_and_game(tmp_path):
    fake_world = MagicMock()
    fake_world.game = "FALLOUT4"
    fake_world.mods = [MagicMock(enabled=True), MagicMock(enabled=False), MagicMock(enabled=True)]
    assets.init_assets(_fake_cache_with_world(fake_world))

    result = assets.assets_summary({"profile_dir": str(tmp_path / "Default")})

    assert result["profile_name"] == "Default"
    assert result["game"] == "FALLOUT4"
    assert result["mod_count"] == 3
    assert result["enabled_mod_count"] == 2


def test_world_invalidate_calls_cache(tmp_path):
    cache = MagicMock()
    assets.init_assets(cache)

    result = assets.world_invalidate({"profile_dir": str(tmp_path / "Default")})

    assert result["invalidated"] is True
    cache.invalidate.assert_called_once()


def test_world_invalidate_without_init_returns_uninitialized():
    result = assets.world_invalidate({"profile_dir": "/tmp/p"})
    assert result["invalidated"] is False
    assert result["reason"] == "cache_not_init"


def test_register_wires_four_methods(tmp_path):
    fake_world = MagicMock(game="FALLOUT4", mods=[])
    assets.init_assets(_fake_cache_with_world(fake_world))

    assets.register()

    assert "assets.summary" in _METHODS
    assert "assets.conflicts" in _METHODS
    assert "assets.resolve_file" in _METHODS
    assert "world.invalidate" in _METHODS
