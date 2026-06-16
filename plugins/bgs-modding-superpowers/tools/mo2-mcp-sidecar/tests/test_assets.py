"""Unit tests for asset JSON-RPC methods. Uses fake WorldCache, no real engine."""
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


# --- F-M2: assets reuses World.archive_order instead of re-discovering ---


def test_build_entries_by_mod_reuses_world_archive_order(monkeypatch):
    """F-M2: when w.archive_order is set, must NOT call discover_archives_for_plugins.

    Sets a real (empty) ArchiveLoadOrder on the fake world; spies on the engine's
    discover function via monkeypatch; asserts the spy is never invoked. This is
    the perf-critical fast path on multi-hundred-mod profiles.
    """
    # Force the sidecar's sibling-dep shim to run so we can import the engine.
    from mo2_mcp_sidecar import world as _w  # noqa: F401
    from mo2_assets_engine import archive_order as ao_module

    # Spy that fails the test if called.
    spy_calls = {"count": 0}

    def _spy_discover(*args, **kwargs):
        spy_calls["count"] += 1
        return ao_module.ArchiveLoadOrder()

    monkeypatch.setattr(ao_module, "discover_archives_for_plugins", _spy_discover)

    # Fake world with archive_order pre-populated (mirrors what WorldCache._build does)
    fake_world = MagicMock(game="FALLOUT4", mods=[])
    fake_world.archive_order = ao_module.ArchiveLoadOrder()  # non-None -> fast path

    result = assets._build_entries_by_mod(fake_world)

    assert result == {}, "empty mods list -> empty entries_by_mod"
    assert spy_calls["count"] == 0, (
        "F-M2 regression: discover_archives_for_plugins called despite "
        "w.archive_order being non-None"
    )


def test_assets_resolve_file_exposes_winning_owner_mod_at_top_level(tmp_path):
    """AT19 expects result.winner.owner_mod, not nested winner.winner.owner_mod."""
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "High" / "textures" / "acceptance").mkdir(parents=True)
    (mods / "Low" / "textures" / "acceptance").mkdir(parents=True)
    (mods / "High" / "textures" / "acceptance" / "at19.dds").write_text("high", encoding="utf-8")
    (mods / "Low" / "textures" / "acceptance" / "at19.dds").write_text("low", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+High\n+Low\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_resolve_file({
        "profile_dir": str(profile),
        "virtual_path": "textures/acceptance/at19.dds",
    })

    assert result["winner"]["owner_mod"] == "High"
