"""Unit tests for fomod.parse_choices.

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
