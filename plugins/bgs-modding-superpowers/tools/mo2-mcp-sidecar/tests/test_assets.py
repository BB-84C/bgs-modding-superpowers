"""Unit tests for asset JSON-RPC methods. Uses fake WorldCache, no real engine."""
from types import SimpleNamespace
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
    fake_world.tree = SimpleNamespace(
        plugins=[object()],
        archives=[object(), object()],
        file_providers={"textures/a.dds": [], "meshes/b.nif": []},
        unattached_archives=[object()],
    )
    assets.init_assets(_fake_cache_with_world(fake_world))

    result = assets.assets_summary({"profile_dir": str(tmp_path / "Default")})

    assert result["profile_name"] == "Default"
    assert result["game"] == "FALLOUT4"
    assert result["mod_count"] == 3
    assert result["enabled_mod_count"] == 2
    assert result["plugin_count"] == 1
    assert result["archive_count"] == 2
    assert result["unattached_archive_count"] == 1
    assert result["file_count"] == 2


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


def test_register_wires_five_methods(tmp_path):
    fake_world = MagicMock(game="FALLOUT4", mods=[])
    assets.init_assets(_fake_cache_with_world(fake_world))

    assets.register()

    assert "assets.summary" in _METHODS
    assert "assets.conflicts" in _METHODS
    assert "assets.report_for_mod" in _METHODS
    assert "assets.resolve_file" in _METHODS
    assert "world.invalidate" in _METHODS


def test_assets_report_for_mod_groups_conflicts_and_winners_by_file(tmp_path):
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "Winner" / "textures").mkdir(parents=True)
    (mods / "Target" / "textures").mkdir(parents=True)
    (mods / "Target" / "meshes").mkdir(parents=True)
    (mods / "Loser" / "textures").mkdir(parents=True)
    (mods / "Winner" / "textures" / "shared_losing.dds").write_text("winner", encoding="utf-8")
    (mods / "Target" / "textures" / "shared_losing.dds").write_text("target", encoding="utf-8")
    (mods / "Target" / "textures" / "shared_winning.dds").write_text("target", encoding="utf-8")
    (mods / "Loser" / "textures" / "shared_winning.dds").write_text("loser", encoding="utf-8")
    (mods / "Target" / "meshes" / "unique.nif").write_text("unique", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+Winner\n+Target\n+Loser\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_report_for_mod({"profile_dir": str(profile), "mod_name": "Target"})

    assert result["mod"] == "Target"
    assert result["total_files"] == 3
    assert result["files_winning"] == 1
    assert result["files_losing"] == 1
    assert result["files_unique"] == 1
    assert result["overridden_by"] == [{"mod": "Winner", "files": 1}]
    assert result["overrides"] == [{"mod": "Loser", "files": 1}]
    assert result["winners_by_file"] == {
        "textures/shared_losing.dds": "Winner",
        "textures/shared_winning.dds": "Target",
        "meshes/unique.nif": "Target",
    }


def test_assets_report_for_mod_missing_mod_returns_empty_report(tmp_path):
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "OnlyMod").mkdir(parents=True)
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+OnlyMod\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_report_for_mod({"profile_dir": str(profile), "mod_name": "MissingMod"})

    assert result == {
        "mod": "MissingMod",
        "total_files": 0,
        "files_winning": 0,
        "files_losing": 0,
        "files_unique": 0,
        "overridden_by": [],
        "overrides": [],
        "winners_by_file": {},
    }


def test_assets_resolve_file_exposes_winning_owner_mod_at_top_level(tmp_path):
    """Resolve output exposes the winning provider directly."""
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

    assert result["winner"]["mod"] == "High"
    assert result["winner"]["source_type"] == "loose"


# --- BUG-25: Data/ prefix + case normalization in resolve_file + conflicts ---
# WL2 Lane 4D found mo2_assets_resolve returned winner=null on a path that
# definitely existed because mod_enumerator stores paths mod-relative AND
# lowercase, but the lookup didn't normalize either dimension.
# See _normalize_virtual_path() docstring in src/mo2_mcp_sidecar/assets.py.


def test_normalize_virtual_path_strips_leading_data_prefix():
    """BUG-25: 'Data/' is stripped regardless of case."""
    assert assets._normalize_virtual_path("Data/textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("data/textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("DATA/textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("DaTa/textures/foo.dds") == "textures/foo.dds"


def test_normalize_virtual_path_lowercases_output():
    """BUG-25: engine stores lowercase; .DDS / mixed-case must normalize."""
    assert assets._normalize_virtual_path("textures/Foo.DDS") == "textures/foo.dds"
    assert assets._normalize_virtual_path("Data/textures/BNS/FernGrass.DDS") == (
        "textures/bns/ferngrass.dds"
    )


def test_normalize_virtual_path_strips_leading_slashes():
    """BUG-25: '/Data/', '//Data/', and bare '/path' all collapse correctly."""
    assert assets._normalize_virtual_path("/Data/textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("//Data/textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("///Data/textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("/textures/foo.dds") == "textures/foo.dds"


def test_normalize_virtual_path_strips_residual_slashes_after_data():
    """BUG-25: 'Data//foo' -> '/foo' after step 3 -> 'foo' after step 4."""
    assert assets._normalize_virtual_path("Data//textures/foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("Data///textures/foo.dds") == "textures/foo.dds"


def test_normalize_virtual_path_preserves_nested_data_segment():
    """BUG-25: only LEADING 'Data/' is stripped; mid-path 'data/' is meaningful.

    A mod can legitimately ship 'textures/data/foo.dds' (e.g. some companion
    or quest mod has an internal 'data' subfolder). That nested segment must
    survive — only the runtime VFS 'Data/' prefix is artificial.
    """
    assert assets._normalize_virtual_path("textures/data/foo.dds") == "textures/data/foo.dds"
    assert assets._normalize_virtual_path("meshes/clutter/Data/bar.nif") == (
        "meshes/clutter/data/bar.nif"
    )


def test_normalize_virtual_path_normalizes_backslashes():
    """BUG-25: Windows-style separators converted defensively."""
    assert assets._normalize_virtual_path("Data\\textures\\foo.dds") == "textures/foo.dds"
    assert assets._normalize_virtual_path("textures\\foo.dds") == "textures/foo.dds"


def test_normalize_virtual_path_empty_string_passes_through():
    """BUG-25: empty input returns empty (callers treat empty as 'no filter')."""
    assert assets._normalize_virtual_path("") == ""


def test_normalize_virtual_path_handles_bare_data_segment():
    """BUG-25: 'Data/' alone collapses to '' — caller's responsibility to handle."""
    assert assets._normalize_virtual_path("Data/") == ""
    assert assets._normalize_virtual_path("/Data/") == ""


def test_normalize_virtual_path_short_string_not_misread_as_data():
    """BUG-25 regression guard: short paths that aren't 'Data/' are unchanged."""
    # Less than 5 chars, would crash an unchecked p[:5] comparison.
    assert assets._normalize_virtual_path("dat") == "dat"
    assert assets._normalize_virtual_path("data") == "data"  # no trailing slash
    assert assets._normalize_virtual_path("foo") == "foo"


def test_assets_resolve_file_strips_leading_data_prefix(tmp_path):
    """BUG-25 integration: 'Data/textures/...' resolves correctly via real engine."""
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "ModA" / "textures" / "bug25").mkdir(parents=True)
    (mods / "ModA" / "textures" / "bug25" / "tex.dds").write_text("ok", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_resolve_file({
        "profile_dir": str(profile),
        "virtual_path": "Data/textures/bug25/tex.dds",
    })

    assert result["winner"] is not None, (
        "BUG-25: 'Data/' prefix must be stripped before winners.get(...)"
    )
    assert result["winner"]["mod"] == "ModA"
    # Response echoes the original virtual_path so the caller sees what they asked for.
    assert result["virtual_path"] == "Data/textures/bug25/tex.dds"


def test_assets_resolve_file_mixed_case_extension_resolves(tmp_path):
    """BUG-25 integration: '.DDS' input matches engine's lowercased '.dds' storage.

    Mirrors the original WL2 Lane 4D failure where the caller's path ended in
    '.DDS' (matching the OS-level file name) and the engine had '.dds' stored.
    """
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "ModA" / "textures").mkdir(parents=True)
    (mods / "ModA" / "textures" / "case.dds").write_text("ok", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_resolve_file({
        "profile_dir": str(profile),
        "virtual_path": "Data/textures/Case.DDS",
    })

    assert result["winner"] is not None, (
        "BUG-25: mixed-case input must lowercase before lookup"
    )
    assert result["winner"]["mod"] == "ModA"


def test_assets_resolve_file_no_prefix_no_change_regression(tmp_path):
    """BUG-25 regression guard: pre-fix 'textures/foo' callers still work.

    The AT19 test above already covers the no-prefix happy path, but pin it
    explicitly under the BUG-25 namespace too — these normalization changes
    must NOT break callers that already pass the storage form.
    """
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "ModA" / "textures").mkdir(parents=True)
    (mods / "ModA" / "textures" / "noprefix.dds").write_text("ok", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_resolve_file({
        "profile_dir": str(profile),
        "virtual_path": "textures/noprefix.dds",
    })

    assert result["winner"] is not None
    assert result["winner"]["mod"] == "ModA"
    assert result["virtual_path"] == "textures/noprefix.dds"


def test_assets_conflicts_path_prefix_strips_data(tmp_path):
    """BUG-25 integration: assets_conflicts also normalizes path_prefix.

    'Data/textures/' (the VFS form a caller sees in MO2) must filter the same
    way as 'textures/' (the storage form). Pre-fix only 'textures/' worked.
    """
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "High" / "textures").mkdir(parents=True)
    (mods / "Low" / "textures").mkdir(parents=True)
    (mods / "High" / "textures" / "shared.dds").write_text("h", encoding="utf-8")
    (mods / "Low" / "textures" / "shared.dds").write_text("l", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+High\n+Low\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    with_data_prefix = assets.assets_conflicts({
        "profile_dir": str(profile),
        "path_prefix": "Data/textures/",
    })
    without_data_prefix = assets.assets_conflicts({
        "profile_dir": str(profile),
        "path_prefix": "textures/",
    })

    assert with_data_prefix["total_count"] >= 1, (
        "BUG-25: 'Data/textures/' path_prefix must be stripped before filtering"
    )
    # Both forms must produce identical filter results.
    assert with_data_prefix["total_count"] == without_data_prefix["total_count"]


def test_assets_conflicts_path_prefix_unset_unaffected(tmp_path):
    """BUG-25 regression guard: omitting path_prefix returns the conflict set."""
    from mo2_mcp_sidecar.world import WorldCache

    mods = tmp_path / "mods"
    profile = tmp_path / "profiles" / "Default"
    (mods / "ModA" / "textures").mkdir(parents=True)
    (mods / "ModA" / "textures" / "alone.dds").write_text("a", encoding="utf-8")
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("", encoding="utf-8")
    assets.init_assets(WorldCache(mods_root=mods, game="FALLOUT4"))

    result = assets.assets_conflicts({"profile_dir": str(profile)})
    assert result["total_count"] == 0
