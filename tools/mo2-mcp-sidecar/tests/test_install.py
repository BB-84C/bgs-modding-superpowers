"""Unit tests for install.conflict_preview."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mo2_mcp_sidecar import install
from mo2_mcp_sidecar.envelope import _METHODS


@pytest.fixture(autouse=True)
def reset_state():
    install._cache = None
    _METHODS.clear()
    yield
    install._cache = None
    _METHODS.clear()


def _world_with_mods(mods_data):
    """mods_data: list of (name, files: list[str])."""
    world = MagicMock()
    world.mods = []
    for name, files in mods_data:
        m = MagicMock()
        m.name = name
        m.files = files
        world.mods.append(m)
    return world


def _cache_returning(world):
    c = MagicMock(spec=["get", "invalidate"])
    c.get.return_value = world
    return c


def test_preview_no_init_returns_error():
    result = install.install_conflict_preview({"profile_dir": "/tmp/p", "staged_files": []})
    assert result["summary"] == "cache_not_initialized"


def test_preview_no_staged_files_returns_empty(tmp_path):
    install.init_install(_cache_returning(_world_with_mods([])))
    result = install.install_conflict_preview({
        "profile_dir": str(tmp_path / "Default"),
        "staged_files": [],
    })
    assert result["conflicts"] == []
    assert result["staged_file_count"] == 0


def test_preview_finds_overlap(tmp_path):
    world = _world_with_mods([
        ("ExistingMod", ["textures/foo.dds", "meshes/bar.nif"]),
        ("OtherMod", ["sound/baz.wav"]),
    ])
    install.init_install(_cache_returning(world))

    result = install.install_conflict_preview({
        "profile_dir": str(tmp_path / "Default"),
        "staged_files": ["textures/foo.dds", "textures/new.dds"],
        "target_priority": "bottom",
    })

    assert result["staged_file_count"] == 2
    assert len(result["conflicts"]) == 1
    conf = result["conflicts"][0]
    assert conf["with_mod"] == "ExistingMod"
    assert conf["shared_count"] == 1
    assert "textures/foo.dds" in conf["shared_files"]


def test_preview_handles_dict_staged_files(tmp_path):
    """Accept FOMOD-resolver shape: [{source, destination}]."""
    world = _world_with_mods([("ModA", ["nested/path.txt"])])
    install.init_install(_cache_returning(world))

    result = install.install_conflict_preview({
        "profile_dir": str(tmp_path / "Default"),
        "staged_files": [{"source": "src.txt", "destination": "nested/path.txt"}],
    })

    assert result["conflicts"][0]["shared_count"] == 1


def test_preview_path_separator_normalization(tmp_path):
    """Backslash vs forward-slash should not cause false negatives."""
    # NOTE: "dir\\file.txt" in Python source = the 12-char string r"dir\file.txt"
    # (one literal backslash). install._normalize_staged_paths replaces \ with /.
    world = _world_with_mods([("ModA", ["dir\\file.txt"])])
    install.init_install(_cache_returning(world))

    result = install.install_conflict_preview({
        "profile_dir": str(tmp_path / "Default"),
        "staged_files": ["dir/file.txt"],
    })

    # Both should normalize to dir/file.txt
    assert result["conflicts"][0]["shared_count"] == 1


def test_preview_caps_shared_files_at_50(tmp_path):
    world = _world_with_mods([("BigMod", [f"path/file{i}.txt" for i in range(60)])])
    install.init_install(_cache_returning(world))

    result = install.install_conflict_preview({
        "profile_dir": str(tmp_path / "Default"),
        "staged_files": [f"path/file{i}.txt" for i in range(60)],
    })

    conf = result["conflicts"][0]
    assert conf["shared_count"] == 60
    assert len(conf["shared_files"]) == 50  # capped


def test_register_wires_install_conflict_preview(tmp_path):
    install.init_install(_cache_returning(_world_with_mods([])))
    install.register()
    assert "install.conflict_preview" in _METHODS
