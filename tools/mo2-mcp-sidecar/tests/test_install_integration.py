"""Real-fixture integration test for install.conflict_preview against actual engine.

Skips if mo2_assets_engine isn't importable. Uses a tmp profile + real mods on disk
to verify the conflict preview detects overlap with real engine file enumeration.

NOTE: We import mo2_mcp_sidecar.world BEFORE the importorskip checks; world.py
applies the sibling-dep sys.path shim that makes mo2_assets_engine reachable.
Without that order the importorskip fires before the shim runs and the whole
integration suite skips even when the engine sits next to us in the worktree.
"""
from __future__ import annotations

import pytest

# Trigger world.py's sys.path shim before probing for the engine.
from mo2_mcp_sidecar import world as _world  # noqa: F401  (import-for-side-effects)

pytest.importorskip("mo2_assets_engine.mod_enumerator")
pytest.importorskip("mo2_assets_engine.archive_order")


@pytest.fixture
def real_profile(tmp_path):
    """Build a minimal real profile + 2 mods on disk."""
    mo2_root = tmp_path / "mo2"
    profile_dir = mo2_root / "profiles" / "Default"
    profile_dir.mkdir(parents=True)
    mods_dir = mo2_root / "mods"
    mods_dir.mkdir()

    # ModA: textures/foo.dds + meshes/bar.nif
    (mods_dir / "ModA").mkdir()
    (mods_dir / "ModA" / "textures").mkdir()
    (mods_dir / "ModA" / "textures" / "foo.dds").write_bytes(b"fake-dds")
    (mods_dir / "ModA" / "meshes").mkdir()
    (mods_dir / "ModA" / "meshes" / "bar.nif").write_bytes(b"fake-nif")

    # ModB: sound/baz.wav
    (mods_dir / "ModB").mkdir()
    (mods_dir / "ModB" / "sound").mkdir()
    (mods_dir / "ModB" / "sound" / "baz.wav").write_bytes(b"fake-wav")

    # modlist.txt: top of file = highest priority (per engine convention)
    (profile_dir / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile_dir / "plugins.txt").write_text("", encoding="utf-8")

    return {"mo2_root": mo2_root, "profile_dir": profile_dir, "mods_dir": mods_dir}


def test_real_engine_detects_textures_overlap(real_profile):
    """Stage a file at textures/foo.dds - should detect overlap with ModA."""
    from mo2_mcp_sidecar import install
    from mo2_mcp_sidecar.world import WorldCache

    cache = WorldCache(mods_root=real_profile["mods_dir"], game="FALLOUT4")
    install._cache = None  # reset module-level
    install.init_install(cache)

    result = install.install_conflict_preview({
        "profile_dir": str(real_profile["profile_dir"]),
        "staged_files": ["textures/foo.dds", "textures/brand_new.dds"],
        "target_priority": "bottom",
    })

    # Should find overlap with ModA on textures/foo.dds (and not ModB)
    assert result["staged_file_count"] == 2
    mod_a_conflicts = [c for c in result["conflicts"] if c["with_mod"] == "ModA"]
    assert len(mod_a_conflicts) == 1
    assert "textures/foo.dds" in mod_a_conflicts[0]["shared_files"]
    assert "textures/brand_new.dds" not in str(result["conflicts"])  # genuinely new


def test_real_engine_no_overlap_when_path_is_unique(real_profile):
    """Stage entirely new paths - should detect 0 conflicts."""
    from mo2_mcp_sidecar import install
    from mo2_mcp_sidecar.world import WorldCache

    cache = WorldCache(mods_root=real_profile["mods_dir"], game="FALLOUT4")
    install._cache = None
    install.init_install(cache)

    result = install.install_conflict_preview({
        "profile_dir": str(real_profile["profile_dir"]),
        "staged_files": ["interface/unique_widget.swf"],
    })

    assert result["staged_file_count"] == 1
    assert result["conflicts"] == []
