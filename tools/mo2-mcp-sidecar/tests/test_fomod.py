"""Unit tests for fomod.parse_choices + fomod.resolve_files.

Most tests use synthetic FOMOD XML fixtures since pyfomod requires real
ModuleConfig.xml. Tests skip if pyfomod isn't installed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mo2_mcp_sidecar import fomod
from mo2_mcp_sidecar.envelope import _METHODS


pytestmark = pytest.mark.skipif(not fomod._PYFOMOD_AVAILABLE, reason="pyfomod not installed")


@pytest.fixture(autouse=True)
def clear_methods():
    _METHODS.clear()
    yield
    _METHODS.clear()


_MINIMAL_FOMOD = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>TestMod</moduleName>
  <installSteps order="Explicit">
    <installStep name="Step1">
      <optionalFileGroups order="Explicit">
        <group name="MainOptions" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="OptionA">
              <description>Option A description</description>
              <typeDescriptor><type name="Recommended"/></typeDescriptor>
            </plugin>
            <plugin name="OptionB">
              <description>Option B description</description>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


def _write_fomod(tmp_path: Path, module_config: str = _MINIMAL_FOMOD) -> Path:
    fomod_dir = tmp_path / "MyMod" / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(module_config, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>TestMod</Name><Version>1.0</Version></fomod>',
        encoding="utf-8",
    )
    return fomod_dir.parent


def test_parse_choices_returns_tree(tmp_path):
    archive_root = _write_fomod(tmp_path)

    result = fomod.fomod_parse_choices({"archive_path": str(archive_root)})

    assert result["fomod_name"] == "TestMod"
    assert result["fomod_version"] == "1.0"
    assert len(result["pages"]) == 1
    page = result["pages"][0]
    assert page["name"] == "Step1"
    assert len(page["groups"]) == 1
    group = page["groups"][0]
    assert group["name"] == "MainOptions"
    assert group["type"] == "SelectExactlyOne"
    assert len(group["options"]) == 2
    assert group["options"][0]["name"] == "OptionA"
    assert group["options"][0]["type"] == "Recommended"
    assert group["options"][0]["description"] == "Option A description"


def test_parse_choices_missing_archive_raises():
    with pytest.raises(FileNotFoundError):
        fomod.fomod_parse_choices({"archive_path": "/nonexistent/path"})


def test_parse_choices_non_fomod_dir_raises(tmp_path):
    """A dir without fomod/ModuleConfig.xml should raise not_a_fomod."""
    not_fomod = tmp_path / "plain"
    not_fomod.mkdir()
    (not_fomod / "readme.txt").write_text("no fomod here")

    with pytest.raises(RuntimeError, match="not_a_fomod"):
        fomod.fomod_parse_choices({"archive_path": str(not_fomod)})


def test_register_wires_parse_choices(tmp_path):
    fomod.register()
    assert "fomod.parse_choices" in _METHODS


# --- Task 28: fomod.resolve_files tests ---

_TWO_OPTION_FOMOD = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>TwoOption</moduleName>
  <installSteps order="Explicit">
    <installStep name="MainStep">
      <optionalFileGroups order="Explicit">
        <group name="Variant" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Standard">
              <description>standard variant</description>
              <files>
                <file source="standard.esp" destination="standard.esp"/>
              </files>
              <typeDescriptor><type name="Recommended"/></typeDescriptor>
            </plugin>
            <plugin name="HD">
              <description>HD variant</description>
              <files>
                <file source="hd.esp" destination="hd.esp"/>
              </files>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


def _write_two_option_fomod(tmp_path: Path) -> Path:
    fomod_dir = tmp_path / "TwoOptMod" / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_TWO_OPTION_FOMOD, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>TwoOpt</Name></fomod>', encoding="utf-8")
    archive_root = fomod_dir.parent
    # Drop source files so Installer can see them
    (archive_root / "standard.esp").write_text("standard")
    (archive_root / "hd.esp").write_text("hd")
    return archive_root


def test_resolve_files_selects_standard(tmp_path):
    archive_root = _write_two_option_fomod(tmp_path)

    result = fomod.fomod_resolve_files({
        "archive_path": str(archive_root),
        "choices": [
            {"page_name": "MainStep",
             "selected_options": [{"group_name": "Variant", "option_name": "Standard"}]}
        ],
    })

    assert result["file_count"] >= 1
    destinations = [f["destination"] for f in result["files"]]
    assert any("standard.esp" in d for d in destinations)


def test_resolve_files_selects_hd(tmp_path):
    archive_root = _write_two_option_fomod(tmp_path)

    result = fomod.fomod_resolve_files({
        "archive_path": str(archive_root),
        "choices": [
            {"page_name": "MainStep",
             "selected_options": [{"group_name": "Variant", "option_name": "HD"}]}
        ],
    })

    destinations = [f["destination"] for f in result["files"]]
    assert any("hd.esp" in d for d in destinations)


def test_resolve_files_missing_archive_raises():
    with pytest.raises(FileNotFoundError):
        fomod.fomod_resolve_files({"archive_path": "/nope", "choices": []})


def test_resolve_files_invalid_choices_type_raises(tmp_path):
    archive_root = _write_two_option_fomod(tmp_path)
    with pytest.raises(RuntimeError, match="invalid_choices"):
        fomod.fomod_resolve_files({"archive_path": str(archive_root), "choices": "not a list"})


def test_register_now_wires_both_methods():
    fomod.register()
    assert "fomod.parse_choices" in _METHODS
    assert "fomod.resolve_files" in _METHODS
