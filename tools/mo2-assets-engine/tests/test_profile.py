from pathlib import Path

from mo2_assets_engine.profile import MO2Profile, read_profile


def test_read_profile_returns_enabled_mods_in_priority_order(sample_profile_dir: Path) -> None:
    profile = read_profile(profile_dir=sample_profile_dir, mods_root=sample_profile_dir.parent / "mods")
    names = [m.name for m in profile.enabled_mods]

    # Top of modlist.txt = highest priority.
    # ModC top -> prio 2; ModB -> 1; ModA -> 0. DisabledMod skipped.
    assert names == ["ModC", "ModB", "ModA"]
    assert [m.priority for m in profile.enabled_mods] == [2, 1, 0]


def test_read_profile_collects_enabled_plugin_load_order(sample_profile_dir: Path) -> None:
    profile = read_profile(profile_dir=sample_profile_dir, mods_root=sample_profile_dir.parent / "mods")

    # BGS asterisk-prefix format: starred lines are the enabled plugins.
    assert profile.enabled_plugins == ["ModB.esp", "ModA.esp"]


def test_read_profile_skips_separators_and_disabled(sample_profile_dir: Path) -> None:
    profile = read_profile(profile_dir=sample_profile_dir, mods_root=sample_profile_dir.parent / "mods")
    names = [m.name for m in profile.enabled_mods]
    assert "Separator_separator" not in names
    assert "DisabledMod" not in names


def test_mo2profile_is_pure_data() -> None:
    profile = MO2Profile(
        profile_dir=Path("/x"),
        mods_root=Path("/y"),
        enabled_mods=[],
        enabled_plugins=[],
    )
    assert profile.profile_dir == Path("/x")
