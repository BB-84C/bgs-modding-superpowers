from pathlib import Path

from mo2_assets_engine.archive_ini import IniArchiveLists
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


def test_plugin_in_one_mod_archives_in_other_mods_attach_globally(
    tmp_path: Path, synthetic_ba2_gnrl: Path
) -> None:
    profile, mods = _profile(
        tmp_path,
        ["+ArchivePartB", "+ArchivePartA", "+PluginCarrier"],
        ["*Starfield HD.esm"],
    )
    (mods / "PluginCarrier").mkdir(parents=True)
    (mods / "PluginCarrier" / "Starfield HD.esm").write_bytes(b"plugin")
    (mods / "ArchivePartA").mkdir(parents=True)
    (mods / "ArchivePartA" / "Starfield HD - Main.ba2").write_bytes(synthetic_ba2_gnrl.read_bytes())
    (mods / "ArchivePartB").mkdir(parents=True)
    (mods / "ArchivePartB" / "Starfield HD - Textures01.ba2").write_bytes(
        synthetic_ba2_gnrl.read_bytes()
    )

    tree = build_virtual_data_tree(profile=profile, game=Game.STARFIELD)

    assert tree.attachments == {
        "starfield hd - main.ba2": "Starfield HD.esm",
        "starfield hd - textures01.ba2": "Starfield HD.esm",
    }
    providers = tree.file_providers["materials/test/foo.bgsm"]
    assert {p.source_mod for p in providers if p.source_type is SourceType.ARCHIVE} == {
        "ArchivePartA",
        "ArchivePartB",
    }
    assert {p.attached_plugin for p in providers} == {"Starfield HD.esm"}


def test_numbered_archive_variants_all_link(tmp_path: Path, synthetic_ba2_gnrl: Path) -> None:
    profile, mods = _profile(tmp_path, ["+Archives", "+Plugin"], ["*Foo.esm"])
    (mods / "Plugin").mkdir(parents=True)
    (mods / "Plugin" / "Foo.esm").write_bytes(b"plugin")
    (mods / "Archives").mkdir(parents=True)
    for name in ("Foo - Textures01.ba2", "Foo - Textures02.ba2"):
        (mods / "Archives" / name).write_bytes(synthetic_ba2_gnrl.read_bytes())

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
    assert tree.plugins[0].name == "Foo.esm"
    assert tree.plugins[0].source_mod == "High"


def test_archive_whose_plugin_is_disabled_is_unattached(
    tmp_path: Path, synthetic_ba2_gnrl: Path
) -> None:
    profile, mods = _profile(tmp_path, ["+ArchiveOnly"], [])
    (mods / "ArchiveOnly").mkdir(parents=True)
    (mods / "ArchiveOnly" / "Foo - Main.ba2").write_bytes(synthetic_ba2_gnrl.read_bytes())

    tree = build_virtual_data_tree(profile=profile, game=Game.FALLOUT4)

    assert tree.attachments == {}
    assert [(a.name, a.source_mod, a.reason) for a in tree.unattached_archives] == [
        ("Foo - Main.ba2", "ArchiveOnly", "no_matching_plugin")
    ]
    assert "materials/test/foo.bgsm" not in tree.file_providers


def test_ini_list_claims_archive_without_plugin(tmp_path: Path, synthetic_ba2_gnrl: Path) -> None:
    profile, mods = _profile(tmp_path, ["+ArchiveOnly"], [])
    (mods / "ArchiveOnly").mkdir(parents=True)
    (mods / "ArchiveOnly" / "LooseArchive.ba2").write_bytes(synthetic_ba2_gnrl.read_bytes())


    tree = build_virtual_data_tree(
        profile=profile,
        game=Game.STARFIELD,
        ini_archive_lists=IniArchiveLists(explicit_archives=["LooseArchive.ba2"]),
    )

    assert tree.unattached_archives == []
    provider = tree.file_providers["materials/test/foo.bgsm"][0]
    assert provider.source_type is SourceType.ARCHIVE
    assert provider.archive_name == "LooseArchive.ba2"
    assert provider.attached_plugin is None
    assert provider.attached_plugin_load_order is None


def test_loose_wins_over_archive_on_same_virtual_path(
    tmp_path: Path, synthetic_ba2_gnrl: Path
) -> None:
    profile, mods = _profile(tmp_path, ["+Loose", "+Archive", "+Plugin"], ["*Foo.esm"])
    (mods / "Plugin").mkdir(parents=True)
    (mods / "Plugin" / "Foo.esm").write_bytes(b"plugin")
    (mods / "Archive").mkdir(parents=True)
    (mods / "Archive" / "Foo - Main.ba2").write_bytes(synthetic_ba2_gnrl.read_bytes())
    (mods / "Loose" / "materials" / "test").mkdir(parents=True)
    (mods / "Loose" / "materials" / "test" / "foo.bgsm").write_bytes(b"loose")

    resolved = resolve_tree(build_virtual_data_tree(profile=profile, game=Game.FALLOUT4))

    assert resolved["materials/test/foo.bgsm"].winner.source_mod == "Loose"
    assert resolved["materials/test/foo.bgsm"].winner.source_type is SourceType.LOOSE


def test_archive_vs_archive_higher_plugin_load_order_wins(
    tmp_path: Path, synthetic_ba2_gnrl: Path
) -> None:
    profile, mods = _profile(
        tmp_path,
        ["+ArchiveB", "+ArchiveA", "+PluginB", "+PluginA"],
        ["*A.esm", "*B.esm"],
    )
    for mod_name, plugin_name in (("PluginA", "A.esm"), ("PluginB", "B.esm")):
        (mods / mod_name).mkdir(parents=True)
        (mods / mod_name / plugin_name).write_bytes(b"plugin")
    (mods / "ArchiveA").mkdir(parents=True)
    (mods / "ArchiveB").mkdir(parents=True)
    (mods / "ArchiveA" / "A - Main.ba2").write_bytes(synthetic_ba2_gnrl.read_bytes())
    (mods / "ArchiveB" / "B - Main.ba2").write_bytes(synthetic_ba2_gnrl.read_bytes())

    resolved = resolve_tree(build_virtual_data_tree(profile=profile, game=Game.FALLOUT4))

    assert resolved["materials/test/foo.bgsm"].winner.source_mod == "ArchiveB"


def test_loose_vs_loose_higher_mod_priority_wins(tmp_path: Path) -> None:
    profile, mods = _profile(tmp_path, ["+High", "+Low"], [])
    (mods / "High" / "textures").mkdir(parents=True)
    (mods / "Low" / "textures").mkdir(parents=True)
    (mods / "High" / "textures" / "same.dds").write_bytes(b"high")
    (mods / "Low" / "textures" / "same.dds").write_bytes(b"low")

    resolved = resolve_tree(build_virtual_data_tree(profile=profile, game=Game.FALLOUT4))

    assert resolved["textures/same.dds"].winner.source_mod == "High"


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
