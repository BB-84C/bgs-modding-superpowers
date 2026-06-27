from pathlib import Path

from mo2_assets_engine.archive_order import Game
from mo2_assets_engine.conflict_resolver import resolve_tree
from mo2_assets_engine.profile import read_profile
from mo2_assets_engine.virtual_data_tree import SourceType, build_virtual_data_tree


def _write_profile(profile: Path, mod_lines: list[str], plugin_lines: list[str]) -> None:
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("\n".join(mod_lines) + "\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("\n".join(plugin_lines) + "\n", encoding="utf-8")


def _profile(tmp_path: Path, mod_lines: list[str], plugin_lines: list[str]):
    profile_dir = tmp_path / "profiles" / "Default"
    mods_root = tmp_path / "mods"
    _write_profile(profile_dir, mod_lines, plugin_lines)
    return read_profile(profile_dir=profile_dir, mods_root=mods_root), mods_root


# ---------------------------------------------------------------------------
# Plugin / archive pool + attachment metadata (informational, unchanged)
# ---------------------------------------------------------------------------


def test_plugin_pool_attributes_each_plugin_to_its_source_mod(tmp_path: Path) -> None:
    profile, mods = _profile(
        tmp_path,
        ["+ArchivePartB", "+ArchivePartA", "+PluginCarrier"],
        ["*Starfield HD.esm"],
    )
    (mods / "PluginCarrier").mkdir(parents=True)
    (mods / "PluginCarrier" / "Starfield HD.esm").write_bytes(b"plugin")

    tree = build_virtual_data_tree(profile=profile, game=Game.STARFIELD)

    assert [p.name for p in tree.plugins] == ["Starfield HD.esm"]
    assert tree.plugins[0].source_mod == "PluginCarrier"


def test_archive_pool_collects_top_level_archives_across_mods(tmp_path: Path) -> None:
    """Archive metadata is populated regardless of folder boundary. Pool is
    the substrate for future BA2-member analysis; today it does not produce
    file_providers entries — those come from the projected-loose walk, which
    treats .ba2/.bsa as normal files at mod-root.
    """
    profile, mods = _profile(
        tmp_path,
        ["+ArchivePartA", "+ArchivePartB"],
        [],
    )
    (mods / "ArchivePartA").mkdir(parents=True)
    (mods / "ArchivePartA" / "Foo - Main.ba2").write_bytes(b"a")
    (mods / "ArchivePartB").mkdir(parents=True)
    (mods / "ArchivePartB" / "Foo - Textures01.ba2").write_bytes(b"b")

    tree = build_virtual_data_tree(profile=profile, game=Game.STARFIELD)

    assert {(a.name, a.source_mod) for a in tree.archives} == {
        ("Foo - Main.ba2", "ArchivePartA"),
        ("Foo - Textures01.ba2", "ArchivePartB"),
    }


def test_attachment_metadata_links_cross_folder_plugin_and_archives(
    tmp_path: Path,
) -> None:
    """Cross-folder attachment metadata is computed (plugin in one mod,
    archives in others). The metadata is informational only today; we do
    not enumerate archive members. The user can see WHICH archives belong
    to which plugin without the engine having to open them.
    """
    profile, mods = _profile(
        tmp_path,
        ["+ArchivePartB", "+ArchivePartA", "+PluginCarrier"],
        ["*Starfield HD.esm"],
    )
    (mods / "PluginCarrier").mkdir(parents=True)
    (mods / "PluginCarrier" / "Starfield HD.esm").write_bytes(b"plugin")
    (mods / "ArchivePartA").mkdir(parents=True)
    (mods / "ArchivePartA" / "Starfield HD - Main.ba2").write_bytes(b"a")
    (mods / "ArchivePartB").mkdir(parents=True)
    (mods / "ArchivePartB" / "Starfield HD - Textures01.ba2").write_bytes(b"b")

    tree = build_virtual_data_tree(profile=profile, game=Game.STARFIELD)

    assert tree.attachments == {
        "starfield hd - main.ba2": "Starfield HD.esm",
        "starfield hd - textures01.ba2": "Starfield HD.esm",
    }


def test_numbered_archive_variants_all_link(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+Archives", "+Plugin"], ["*Foo.esm"])
    (mods / "Plugin").mkdir(parents=True)
    (mods / "Plugin" / "Foo.esm").write_bytes(b"plugin")
    (mods / "Archives").mkdir(parents=True)
    for name in ("Foo - Textures01.ba2", "Foo - Textures02.ba2"):
        (mods / "Archives" / name).write_bytes(b"archive")

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert tree.attachments == {
        "foo - textures01.ba2": "Foo.esm",
        "foo - textures02.ba2": "Foo.esm",
    }


def test_two_mods_same_plugin_name_higher_mod_priority_wins(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+High", "+Low"], ["*Foo.esm"])
    (mods / "Low").mkdir(parents=True)
    (mods / "High").mkdir(parents=True)
    (mods / "Low" / "Foo.esm").write_bytes(b"low")
    (mods / "High" / "Foo.esm").write_bytes(b"high")

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert len(tree.plugins) == 1
    assert tree.plugins[0].source_mod == "High"


def test_archive_whose_plugin_is_disabled_is_unattached(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+ArchiveOnly"], [])
    (mods / "ArchiveOnly").mkdir(parents=True)
    (mods / "ArchiveOnly" / "Foo - Main.ba2").write_bytes(b"archive")

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert tree.attachments == {}
    assert [(a.name, a.source_mod, a.reason) for a in tree.unattached_archives] == [
        ("Foo - Main.ba2", "ArchiveOnly", "no_matching_plugin")
    ]


# ---------------------------------------------------------------------------
# Conflict semantics (file-to-file; archives treated as files)
# ---------------------------------------------------------------------------


def test_archives_are_projected_as_loose_files_and_never_opened(tmp_path: Path) -> None:
    """Mod-root .ba2 files MUST appear in file_providers as ordinary loose
    paths. The engine writes garbage into the file (NOT a valid BA2) so
    that the test ALSO acts as a guard against accidental archive opening:
    if any code path opens these files, the test will fail with a parse
    error instead of an assertion failure.
    """
    profile, mods = _profile(tmp_path, ["+ModA"], [])
    (mods / "ModA").mkdir(parents=True)
    (mods / "ModA" / "Foo.ba2").write_bytes(b"NOT-A-VALID-BA2")
    (mods / "ModA" / "Bar.bsa").write_bytes(b"NOT-A-VALID-BSA")

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert "foo.ba2" in tree.file_providers
    assert "bar.bsa" in tree.file_providers
    assert all(
        p.source_type is SourceType.LOOSE for p in tree.file_providers["foo.ba2"]
    )


def test_same_archive_name_in_two_mods_conflicts_at_archive_filename(
    tmp_path: Path,
) -> None:
    """Two mods shipping the same archive name = file-to-file conflict on
    the archive path. The higher mod_priority wins (USVFS hides the other
    archive entirely). No BA2 parsing involved.
    """
    profile, mods = _profile(tmp_path, ["+High", "+Low"], [])
    (mods / "Low").mkdir(parents=True)
    (mods / "High").mkdir(parents=True)
    (mods / "Low" / "Foo.ba2").write_bytes(b"low")
    (mods / "High" / "Foo.ba2").write_bytes(b"high")

    resolved = resolve_tree(build_virtual_data_tree(profile=profile, game=Game.FALLOUT4))

    assert resolved["foo.ba2"].is_conflict is True
    assert resolved["foo.ba2"].winner.source_mod == "High"
    assert [loser.source_mod for loser in resolved["foo.ba2"].losers] == ["Low"]


def test_loose_vs_loose_higher_mod_priority_wins(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+High", "+Low"], [])
    (mods / "High" / "textures").mkdir(parents=True)
    (mods / "Low" / "textures").mkdir(parents=True)
    (mods / "High" / "textures" / "same.dds").write_bytes(b"high")
    (mods / "Low" / "textures" / "same.dds").write_bytes(b"low")

    resolved = resolve_tree(build_virtual_data_tree(profile=profile, game=Game.FALLOUT4))

    assert resolved["textures/same.dds"].winner.source_mod == "High"


# ---------------------------------------------------------------------------
# Regression guards from prior fixes
# ---------------------------------------------------------------------------


def test_mod_root_meta_ini_excluded_but_nested_meta_ini_kept(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+ModA"], [])
    (mods / "ModA").mkdir(parents=True)
    (mods / "ModA" / "meta.ini").write_text("[General]\n", encoding="utf-8")
    (mods / "ModA" / "Data" / "Scripts").mkdir(parents=True)
    (mods / "ModA" / "Data" / "Scripts" / "meta.ini").write_text("nested", encoding="utf-8")

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert "meta.ini" not in tree.file_providers
    assert "data/scripts/meta.ini" in tree.file_providers


def test_separator_modlist_entries_do_not_contribute_files(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+ModA", "+UI_separator"], [])
    (mods / "ModA" / "textures").mkdir(parents=True)
    (mods / "ModA" / "textures" / "real.dds").write_bytes(b"real")
    (mods / "UI_separator").mkdir(parents=True)
    (mods / "UI_separator" / "phantom.dds").write_bytes(b"nope")

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert set(tree.file_providers) == {"textures/real.dds"}
