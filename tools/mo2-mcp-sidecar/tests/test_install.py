"""Unit tests for install.conflict_preview."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mo2_assets_engine.virtual_data_tree import Provider, SourceType, VirtualDataTree

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
    file_providers = {}
    for name, files in mods_data:
        m = MagicMock()
        m.name = name
        world.mods.append(m)
        for path in files:
            normalized = path.replace("\\", "/").lower()
            file_providers.setdefault(normalized, []).append(
                Provider(
                    source_mod=name,
                    source_type=SourceType.LOOSE,
                    mod_priority=0,
                )
            )
    world.tree = VirtualDataTree(file_providers=file_providers, game="fallout4")
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


# --- P-B6 method 3: install.stage_fomod ---

from mo2_mcp_sidecar import fomod as _fomod  # noqa: E402  (skipif marker reads constant)


_STAGE_FOMOD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>StageTest</moduleName>
  <installSteps order="Explicit">
    <installStep name="Choose">
      <optionalFileGroups order="Explicit">
        <group name="Variant" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Light">
              <description>Light variant</description>
              <files><file source="light.esp" destination="light.esp"/></files>
              <typeDescriptor><type name="Recommended"/></typeDescriptor>
            </plugin>
            <plugin name="Heavy">
              <description>Heavy variant</description>
              <files><file source="heavy.esp" destination="heavy.esp"/></files>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""

_TRAVERSAL_DEST_FOMOD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>TraversalDest</moduleName>
  <installSteps order="Explicit">
    <installStep name="Choose">
      <optionalFileGroups order="Explicit">
        <group name="Variant" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Escape">
              <description>Escapes staging</description>
              <files><file source="payload.esp" destination="../escape.esp"/></files>
              <typeDescriptor><type name="Recommended"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


@pytest.mark.skipif(not _fomod._PYFOMOD_AVAILABLE, reason="pyfomod not installed")
def test_stage_fomod_from_directory_extracts_selected_only(tmp_path):
    """Pre-extracted FOMOD directory + choices -> only selected files in staging."""
    fomod_root = tmp_path / "MyFomod"
    fomod_dir = fomod_root / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_STAGE_FOMOD_XML, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>StageTest</Name></fomod>', encoding="utf-8")
    (fomod_root / "light.esp").write_text("light-data", encoding="utf-8")
    (fomod_root / "heavy.esp").write_text("heavy-data", encoding="utf-8")

    staging = tmp_path / "staging"

    from mo2_mcp_sidecar.install import install_stage_fomod
    result = install_stage_fomod({
        "archive_path": str(fomod_root),
        "choices": [{"page_name": "Choose",
                     "selected_options": [{"group_name": "Variant",
                                           "option_name": "Light"}]}],
        "staging_dir": str(staging),
    })

    assert result["archive_format"] == "directory"
    assert (staging / "light.esp").exists()
    assert (staging / "light.esp").read_text() == "light-data"
    # Heavy should NOT be staged
    assert not (staging / "heavy.esp").exists()


@pytest.mark.skipif(not _fomod._PYFOMOD_AVAILABLE, reason="pyfomod not installed")
def test_fomod_install_with_info_xml_uses_fomod_parser(tmp_path):
    """Archive FOMOD + choices should stage selected files through pyfomod."""
    import zipfile

    archive_path = tmp_path / "fomod.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("fomod/ModuleConfig.xml", _STAGE_FOMOD_XML)
        zf.writestr("fomod/info.xml", '<?xml version="1.0"?><fomod><Name>StageTest</Name></fomod>')
        zf.writestr("light.esp", "light-data")
        zf.writestr("heavy.esp", "heavy-data")
    staging = tmp_path / "staging"

    from mo2_mcp_sidecar.install import install_stage_fomod
    result = install_stage_fomod({
        "archive_path": str(archive_path),
        "choices": [{"page_name": "Choose",
                     "selected_options": [{"group_name": "Variant",
                                           "option_name": "Light"}]}],
        "staging_dir": str(staging),
    })

    assert result["archive_format"] == "zip"
    assert result["file_count"] == 1
    assert (staging / "light.esp").read_text() == "light-data"
    assert not (staging / "heavy.esp").exists()


@pytest.mark.skipif(not _fomod._PYFOMOD_AVAILABLE, reason="pyfomod not installed")
def test_stage_fomod_rejects_destination_parent_traversal(tmp_path):
    """FOMOD destination paths must not escape staging_dir."""
    fomod_root = tmp_path / "TraversalFomod"
    fomod_dir = fomod_root / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_TRAVERSAL_DEST_FOMOD_XML, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>TraversalDest</Name></fomod>', encoding="utf-8")
    (fomod_root / "payload.esp").write_text("payload", encoding="utf-8")
    staging = tmp_path / "staging"

    from mo2_mcp_sidecar.install import install_stage_fomod

    with pytest.raises(ValueError, match="path_traversal_blocked"):
        install_stage_fomod({
            "archive_path": str(fomod_root),
            "choices": [{"page_name": "Choose",
                         "selected_options": [{"group_name": "Variant",
                                               "option_name": "Escape"}]}],
            "staging_dir": str(staging),
        })

    assert not (tmp_path / "escape.esp").exists()
    assert not any(staging.rglob("*"))


def test_stage_fomod_missing_archive_raises(tmp_path):
    from mo2_mcp_sidecar.install import install_stage_fomod
    with pytest.raises(FileNotFoundError):
        install_stage_fomod({
            "archive_path": "/nope", "choices": [], "staging_dir": str(tmp_path / "out"),
        })


def test_stage_fomod_invalid_choices_type_raises(tmp_path):
    from mo2_mcp_sidecar.install import install_stage_fomod
    fake = tmp_path / "fake"
    fake.mkdir()
    with pytest.raises(RuntimeError, match="invalid_choices"):
        install_stage_fomod({
            "archive_path": str(fake),
            "choices": "not a list",
            "staging_dir": str(tmp_path / "out"),
        })


def test_register_wires_stage_fomod_too(tmp_path):
    install.init_install(_cache_returning(_world_with_mods([])))
    install.register()
    assert "install.stage_fomod" in _METHODS
    assert "install.conflict_preview" in _METHODS
