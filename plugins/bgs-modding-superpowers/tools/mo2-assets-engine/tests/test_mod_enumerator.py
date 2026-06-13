from pathlib import Path

from mo2_assets_engine.archive_order import ArchiveLoadOrder
from mo2_assets_engine.mod_enumerator import enumerate_mod_files
from mo2_assets_engine.types import ArchiveKind, FileEntryKind, Mod


def test_enumerates_loose_files_recursively(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    (mod_root / "textures" / "test").mkdir(parents=True)
    (mod_root / "textures" / "test" / "foo.dds").write_bytes(b"x")
    (mod_root / "meshes").mkdir()
    (mod_root / "meshes" / "bar.nif").write_bytes(b"x")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=ArchiveLoadOrder())

    paths = sorted(e.relative_path for e in entries)
    assert paths == ["meshes/bar.nif", "textures/test/foo.dds"]
    assert all(e.kind is FileEntryKind.LOOSE for e in entries)
    assert all(e.owner_mod == "ExampleMod" for e in entries)


def test_skips_mohidden_subdirectories(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    (mod_root / "textures").mkdir(parents=True)
    (mod_root / "textures" / "kept.dds").write_bytes(b"x")
    (mod_root / "textures.mohidden").mkdir()
    (mod_root / "textures.mohidden" / "skipped.dds").write_bytes(b"x")
    (mod_root / "meshes" / "hidden.mohidden").mkdir(parents=True)
    (mod_root / "meshes" / "hidden.mohidden" / "skipped.nif").write_bytes(b"x")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=ArchiveLoadOrder())
    paths = sorted(e.relative_path for e in entries)
    assert paths == ["textures/kept.dds"]


def test_enumerates_ba2_members(synthetic_ba2_gnrl: Path, tmp_path: Path) -> None:
    mod_root = tmp_path / "ArchiveMod"
    mod_root.mkdir()
    target = mod_root / "ArchiveMod - Main.ba2"
    target.write_bytes(synthetic_ba2_gnrl.read_bytes())

    archive_order = ArchiveLoadOrder(ordered_archives=["ArchiveMod - Main.ba2"])
    mod = Mod(name="ArchiveMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=archive_order)

    archived = [e for e in entries if e.kind is FileEntryKind.ARCHIVED]
    assert len(archived) == 3
    sample = archived[0]
    assert sample.archive is not None
    assert sample.archive.name == "ArchiveMod - Main.ba2"
    assert sample.archive.kind is ArchiveKind.BA2_GENERAL
    assert sample.archive.load_order == 0


def test_skips_unattached_archives(synthetic_ba2_gnrl: Path, tmp_path: Path) -> None:
    mod_root = tmp_path / "OrphanMod"
    mod_root.mkdir()
    target = mod_root / "Unattached - Main.ba2"
    target.write_bytes(synthetic_ba2_gnrl.read_bytes())

    archive_order = ArchiveLoadOrder(unattached_archives=["Unattached - Main.ba2"])
    mod = Mod(name="OrphanMod", priority=0, enabled=True, root=mod_root)
    entries = enumerate_mod_files(mod=mod, archive_order=archive_order)

    # Loose enumeration still happens (none here); archived entries skipped.
    assert all(e.kind is FileEntryKind.LOOSE for e in entries)
