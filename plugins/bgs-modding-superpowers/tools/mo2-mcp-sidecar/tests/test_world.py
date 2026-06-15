"""Unit tests for WorldCache. No real engine call — uses tmp_path fixtures with monkeypatched build."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from mo2_mcp_sidecar.world import WorldCache, World


@pytest.fixture
def fake_world_factory(monkeypatch):
    """Replace WorldCache._build with a counter to test cache + lock behavior."""
    counter = {"calls": 0}

    def _fake_build(self, profile_dir):
        counter["calls"] += 1
        return World(profile=f"profile@{profile_dir}", mods=["A", "B"], game=self.game)

    monkeypatch.setattr(WorldCache, "_build", _fake_build)
    return counter


def _make_profile(tmp_path: Path) -> Path:
    profile = tmp_path / "Default"
    profile.mkdir()
    (profile / "modlist.txt").write_text("+ModA\n")
    (profile / "plugins.txt").write_text("*Fallout4.esm\n")
    return profile


def test_cache_hit_on_unchanged_mtime(tmp_path, fake_world_factory):
    profile = _make_profile(tmp_path)
    cache = WorldCache(mods_root=tmp_path / "mods", game="FALLOUT4")

    w1 = cache.get(profile)
    w2 = cache.get(profile)

    assert w1 is w2  # same object, cache hit
    assert fake_world_factory["calls"] == 1


def test_cache_invalidates_on_mtime_change(tmp_path, fake_world_factory):
    profile = _make_profile(tmp_path)
    cache = WorldCache(mods_root=tmp_path / "mods", game="FALLOUT4")

    w1 = cache.get(profile)
    time.sleep(0.05)  # mtime resolution headroom on Windows NTFS
    (profile / "modlist.txt").write_text("+ModA\n+ModB\n")

    w2 = cache.get(profile)

    assert w1 is not w2
    assert fake_world_factory["calls"] == 2


def test_invalidate_method_clears_cache(tmp_path, fake_world_factory):
    profile = _make_profile(tmp_path)
    cache = WorldCache(mods_root=tmp_path / "mods", game="FALLOUT4")

    cache.get(profile)
    cache.invalidate(profile)
    cache.get(profile)

    assert fake_world_factory["calls"] == 2


def test_game_param_carried_into_world(tmp_path, fake_world_factory):
    """P-B7: game must reach the constructed World."""
    profile = _make_profile(tmp_path)
    cache = WorldCache(mods_root=tmp_path / "mods", game="STARFIELD")

    w = cache.get(profile)
    assert w.game == "STARFIELD"


def test_real_build_populates_archive_order(tmp_path):
    """P-B6: _build must populate world.archive_order with an ArchiveLoadOrder.

    Uses a real (empty) profile fixture on disk + monkeypatch nothing — exercises
    the lazy engine imports inside _build so the wiring is verified end-to-end.
    """
    profile = _make_profile(tmp_path)
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir(exist_ok=True)
    (mods_dir / "ModA").mkdir(exist_ok=True)  # match the "+ModA" in modlist.txt

    cache = WorldCache(mods_root=mods_dir, game="FALLOUT4")
    world = cache.get(profile)

    # Engine's ArchiveLoadOrder is a frozen dataclass; even empty, the instance
    # must exist (not None) so install.conflict_preview can pass it through.
    assert world.archive_order is not None
    assert hasattr(world.archive_order, "ordered_archives")
    assert hasattr(world.archive_order, "rank_of")


def test_concurrent_get_coalesces_builds(tmp_path, monkeypatch):
    """P-F10: two parallel get() calls on same profile_dir must trigger _build only once."""
    import threading

    counter = {"calls": 0}
    enter_event = threading.Event()
    proceed_event = threading.Event()

    def _slow_build(self, profile_dir):
        counter["calls"] += 1
        enter_event.set()
        proceed_event.wait(timeout=2)
        return World(profile="x", mods=[], game=self.game)

    monkeypatch.setattr(WorldCache, "_build", _slow_build)

    profile = _make_profile(tmp_path)
    cache = WorldCache(mods_root=tmp_path / "mods", game="FALLOUT4")

    result1, result2 = [], []
    t1 = threading.Thread(target=lambda: result1.append(cache.get(profile)))
    t2 = threading.Thread(target=lambda: result2.append(cache.get(profile)))

    t1.start()
    enter_event.wait(timeout=2)  # ensure t1 entered _build
    t2.start()
    time.sleep(0.1)  # give t2 a chance to reach lock acquire
    proceed_event.set()
    t1.join(timeout=3)
    t2.join(timeout=3)

    assert counter["calls"] == 1  # P-F10: lock coalesces
    assert result1[0] is result2[0]
