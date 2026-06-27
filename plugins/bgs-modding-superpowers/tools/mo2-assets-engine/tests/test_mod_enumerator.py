from pathlib import Path

from mo2_assets_engine.mod_enumerator import enumerate_projected_loose_paths
from mo2_assets_engine.types import Mod


def test_enumerates_projected_loose_files_recursively(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    (mod_root / "textures" / "test").mkdir(parents=True)
    (mod_root / "textures" / "test" / "foo.dds").write_bytes(b"x")
    (mod_root / "meshes").mkdir()
    (mod_root / "meshes" / "bar.nif").write_bytes(b"x")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)

    assert enumerate_projected_loose_paths(mod) == ["meshes/bar.nif", "textures/test/foo.dds"]


def test_skips_mod_root_meta_ini_but_keeps_nested(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    mod_root.mkdir()
    (mod_root / "meta.ini").write_text("[General]\nversion=1.0\n", encoding="utf-8")
    (mod_root / "textures").mkdir()
    (mod_root / "textures" / "foo.dds").write_bytes(b"x")
    (mod_root / "Data" / "Scripts").mkdir(parents=True)
    (mod_root / "Data" / "Scripts" / "meta.ini").write_text("nested", encoding="utf-8")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)
    paths = enumerate_projected_loose_paths(mod)

    assert "meta.ini" not in paths
    assert "textures/foo.dds" in paths
    assert "data/scripts/meta.ini" in paths


def test_skips_mohidden_subdirectories(tmp_path: Path) -> None:
    mod_root = tmp_path / "ExampleMod"
    (mod_root / "textures").mkdir(parents=True)
    (mod_root / "textures" / "kept.dds").write_bytes(b"x")
    (mod_root / "textures.mohidden").mkdir()
    (mod_root / "textures.mohidden" / "skipped.dds").write_bytes(b"x")
    (mod_root / "meshes" / "hidden.mohidden").mkdir(parents=True)
    (mod_root / "meshes" / "hidden.mohidden" / "skipped.nif").write_bytes(b"x")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)

    assert enumerate_projected_loose_paths(mod) == ["textures/kept.dds"]


def test_top_level_archives_are_projected_as_files(tmp_path: Path) -> None:
    """Mod-root .ba2/.bsa are projected by MO2 USVFS into Data/ as files.

    The conflict engine treats them as file-to-file collisions on the
    archive name itself — it does NOT open the archive. Two mods shipping
    the same `Foo.ba2` collide on the path `foo.ba2`; the higher mod_priority
    wins (USVFS hides the other). A nested .ba2 deeper in the mod tree is
    also a real projected path and is kept.
    """
    mod_root = tmp_path / "ExampleMod"
    mod_root.mkdir()
    (mod_root / "Example - Main.ba2").write_bytes(b"archive")
    (mod_root / "nested").mkdir()
    (mod_root / "nested" / "Example - Main.ba2").write_bytes(b"projected")

    mod = Mod(name="ExampleMod", priority=0, enabled=True, root=mod_root)

    assert sorted(enumerate_projected_loose_paths(mod)) == [
        "example - main.ba2",
        "nested/example - main.ba2",
    ]
