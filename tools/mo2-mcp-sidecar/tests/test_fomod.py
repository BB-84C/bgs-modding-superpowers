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


# --- Lane V3 FOMOD-EXT: mo2_state-aware dependency evaluation ---

# A FOMOD whose Option type is dynamic (Required if CBBE.esp is Active, otherwise NotUsable).
# This pattern is extremely common in real Bethesda mod FOMODs that gate variants on
# what the user already has installed.
_DYNAMIC_TYPE_FOMOD = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>CBBEPatch</moduleName>
  <installSteps order="Explicit">
    <installStep name="Main">
      <optionalFileGroups order="Explicit">
        <group name="BodyPatch" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="CBBE Compatibility Patch">
              <description>Requires CBBE.esp</description>
              <files>
                <file source="cbbe_patch.esp" destination="cbbe_patch.esp"/>
              </files>
              <typeDescriptor>
                <dependencyType>
                  <defaultType name="NotUsable"/>
                  <patterns>
                    <pattern>
                      <dependencies operator="And">
                        <fileDependency file="CBBE.esp" state="Active"/>
                      </dependencies>
                      <type name="Recommended"/>
                    </pattern>
                  </patterns>
                </dependencyType>
              </typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


def _write_dynamic_type_fomod(tmp_path: Path) -> Path:
    fomod_dir = tmp_path / "DynamicMod" / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_DYNAMIC_TYPE_FOMOD, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>CBBEPatch</Name></fomod>', encoding="utf-8")
    archive_root = fomod_dir.parent
    (archive_root / "cbbe_patch.esp").write_text("patch")
    return archive_root


def test_parse_choices_evaluates_file_dependencies_met(tmp_path):
    """When CBBE.esp is in enabled_plugins, the dynamic option becomes Recommended (met)."""
    archive_root = _write_dynamic_type_fomod(tmp_path)

    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {
            "enabled_plugins": ["CBBE.esp"],
            "provided_files": [],
            "game_version": None,
        },
    })

    page = result["pages"][0]
    option = page["groups"][0]["options"][0]
    assert option["type"] == "Recommended"
    assert option["dependencies_status"] == {"met": True, "missing": []}


def test_parse_choices_evaluates_file_dependencies_unmet(tmp_path):
    """When CBBE.esp is NOT in enabled_plugins, the dynamic option resolves to NotUsable."""
    archive_root = _write_dynamic_type_fomod(tmp_path)

    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {
            "enabled_plugins": [],  # CBBE not installed
            "provided_files": [],
            "game_version": None,
        },
    })

    page = result["pages"][0]
    option = page["groups"][0]["options"][0]
    assert option["type"] == "NotUsable"
    status = option["dependencies_status"]
    assert status["met"] is False
    assert any("CBBE.esp" in m for m in status["missing"])
    assert any("Active" in m for m in status["missing"])


def test_parse_choices_no_state_omits_dependency_fields(tmp_path):
    """Backward compat: omitting mo2_state means no dependencies_status fields on
    options or pages and no module_dependencies_status. conditional_pages_note
    is always present.
    """
    archive_root = _write_dynamic_type_fomod(tmp_path)

    result = fomod.fomod_parse_choices({"archive_path": str(archive_root)})

    assert "module_dependencies_status" not in result
    assert "conditional_pages_note" in result  # always present
    assert result["conditional_pages_note"] is not None  # dynamic type detected
    page = result["pages"][0]
    assert "dependencies_status" not in page
    option = page["groups"][0]["options"][0]
    assert "dependencies_status" not in option


# --- Module-level <moduleDependencies> ---

_MODULE_DEP_FOMOD = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>NeedsFarHarbor</moduleName>
  <moduleDependencies operator="And">
    <fileDependency file="DLCCoast.esm" state="Active"/>
  </moduleDependencies>
  <installSteps order="Explicit">
    <installStep name="OnlyStep">
      <optionalFileGroups order="Explicit">
        <group name="OnlyGroup" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="OnlyOption">
              <description>desc</description>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


def _write_module_dep_fomod(tmp_path: Path) -> Path:
    fomod_dir = tmp_path / "FarHarborMod" / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_MODULE_DEP_FOMOD, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>FH</Name></fomod>', encoding="utf-8")
    return fomod_dir.parent


def test_parse_choices_module_dependencies_met(tmp_path):
    archive_root = _write_module_dep_fomod(tmp_path)
    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {"enabled_plugins": ["DLCCoast.esm"], "provided_files": [], "game_version": None},
    })
    assert result["module_dependencies_status"] == {"met": True, "missing": []}


def test_parse_choices_module_dependencies_unmet(tmp_path):
    archive_root = _write_module_dep_fomod(tmp_path)
    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {"enabled_plugins": [], "provided_files": [], "game_version": None},
    })
    status = result["module_dependencies_status"]
    assert status["met"] is False
    assert any("DLCCoast.esm" in m for m in status["missing"])


# --- <gameDependency> version check ---

_GAME_VERSION_FOMOD = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>NeedsNextGen</moduleName>
  <moduleDependencies operator="And">
    <gameDependency version="1.10.980"/>
  </moduleDependencies>
  <installSteps order="Explicit">
    <installStep name="X">
      <optionalFileGroups order="Explicit">
        <group name="G" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="P"><description>d</description>
              <typeDescriptor><type name="Optional"/></typeDescriptor></plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


def _write_game_version_fomod(tmp_path: Path) -> Path:
    fomod_dir = tmp_path / "NextGenMod" / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_GAME_VERSION_FOMOD, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>NG</Name></fomod>', encoding="utf-8")
    return fomod_dir.parent


def test_parse_choices_game_version_met(tmp_path):
    archive_root = _write_game_version_fomod(tmp_path)
    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {"enabled_plugins": [], "provided_files": [], "game_version": "1.10.980.0"},
    })
    assert result["module_dependencies_status"]["met"] is True


def test_parse_choices_game_version_unmet(tmp_path):
    archive_root = _write_game_version_fomod(tmp_path)
    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {"enabled_plugins": [], "provided_files": [], "game_version": "1.10.163.0"},
    })
    status = result["module_dependencies_status"]
    assert status["met"] is False
    assert any("1.10.980" in m for m in status["missing"])


# --- Conditional pages flag ---

_CONDITIONAL_PAGE_FOMOD = """<?xml version="1.0" encoding="UTF-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>BranchingMod</moduleName>
  <installSteps order="Explicit">
    <installStep name="AlwaysShown">
      <optionalFileGroups order="Explicit">
        <group name="g1" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="A"><description>d</description>
              <typeDescriptor><type name="Optional"/></typeDescriptor></plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
    <installStep name="OnlyIfFlagSet">
      <visible operator="And">
        <flagDependency flag="usedAdvanced" value="true"/>
      </visible>
      <optionalFileGroups order="Explicit">
        <group name="g2" type="SelectAny">
          <plugins order="Explicit">
            <plugin name="B"><description>d</description>
              <typeDescriptor><type name="Optional"/></typeDescriptor></plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
"""


def _write_conditional_page_fomod(tmp_path: Path) -> Path:
    fomod_dir = tmp_path / "BranchingMod" / "fomod"
    fomod_dir.mkdir(parents=True)
    (fomod_dir / "ModuleConfig.xml").write_text(_CONDITIONAL_PAGE_FOMOD, encoding="utf-8")
    (fomod_dir / "info.xml").write_text(
        '<?xml version="1.0"?><fomod><Name>B</Name></fomod>', encoding="utf-8")
    return fomod_dir.parent


def test_parse_choices_conditional_pages_note_flag(tmp_path):
    """A FOMOD with conditional <visible> pages sets conditional_pages_note even
    without mo2_state. The static tree still includes the hidden page (defensive
    listing) but the note tells the agent the wizard may skip it.
    """
    archive_root = _write_conditional_page_fomod(tmp_path)
    result = fomod.fomod_parse_choices({"archive_path": str(archive_root)})
    assert result["conditional_pages_note"] is not None
    # Both pages present in static tree (no wizard flow applied yet)
    assert len(result["pages"]) == 2
    assert {p["name"] for p in result["pages"]} == {"AlwaysShown", "OnlyIfFlagSet"}


def test_parse_choices_no_conditional_flow_note_none(tmp_path):
    """Existing minimal FOMOD has no conditional flow -> conditional_pages_note is None."""
    archive_root = _write_fomod(tmp_path)  # the minimal FOMOD from earlier tests
    result = fomod.fomod_parse_choices({"archive_path": str(archive_root)})
    assert result["conditional_pages_note"] is None


def test_parse_choices_conditional_page_dependencies_status_unmet(tmp_path):
    """With mo2_state, the conditional page reports met=False because the flag was never set."""
    archive_root = _write_conditional_page_fomod(tmp_path)
    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {"enabled_plugins": [], "provided_files": [], "game_version": None},
    })
    pages_by_name = {p["name"]: p for p in result["pages"]}
    assert pages_by_name["AlwaysShown"]["dependencies_status"] == {"met": True, "missing": []}
    conditional_status = pages_by_name["OnlyIfFlagSet"]["dependencies_status"]
    assert conditional_status["met"] is False
    assert any("usedAdvanced" in m for m in conditional_status["missing"])


# --- resolve_files dependency enforcement ---

def test_resolve_files_module_dep_unmet_raises_invalid_choices(tmp_path):
    """When <moduleDependencies> isn't satisfied, pyfomod's Installer constructor
    raises FailedCondition and we surface it as invalid_choices.
    """
    archive_root = _write_module_dep_fomod(tmp_path)
    with pytest.raises(RuntimeError, match="invalid_choices"):
        fomod.fomod_resolve_files({
            "archive_path": str(archive_root),
            "choices": [
                {"page_name": "OnlyStep",
                 "selected_options": [{"group_name": "OnlyGroup", "option_name": "OnlyOption"}]}
            ],
            "mo2_state": {"enabled_plugins": [], "provided_files": [], "game_version": None},
        })


def test_resolve_files_module_dep_met_proceeds(tmp_path):
    """With DLCCoast.esm enabled, resolve_files completes normally."""
    archive_root = _write_module_dep_fomod(tmp_path)
    # No files declared on the option, so we expect file_count=0 but no error.
    result = fomod.fomod_resolve_files({
        "archive_path": str(archive_root),
        "choices": [
            {"page_name": "OnlyStep",
             "selected_options": [{"group_name": "OnlyGroup", "option_name": "OnlyOption"}]}
        ],
        "mo2_state": {"enabled_plugins": ["DLCCoast.esm"], "provided_files": [], "game_version": None},
    })
    assert result["file_count"] == 0


def test_resolve_files_without_state_skips_dependency_check(tmp_path):
    """Backward compat: omitting mo2_state means pyfomod has no file_type
    callback and silently skips file dependency checks (mirrors pyfomod's docs).
    The install proceeds even when the module dependency would have failed.
    """
    archive_root = _write_module_dep_fomod(tmp_path)
    # No mo2_state -> no game_version, no file_type cb -> pyfomod skips file dep check
    result = fomod.fomod_resolve_files({
        "archive_path": str(archive_root),
        "choices": [
            {"page_name": "OnlyStep",
             "selected_options": [{"group_name": "OnlyGroup", "option_name": "OnlyOption"}]}
        ],
    })
    assert result["file_count"] == 0


# --- Case-insensitive plugin matching (NTFS / Bethesda convention) ---

def test_parse_choices_plugin_match_is_case_insensitive(tmp_path):
    """plugins.txt may write 'cbbe.esp' but the FOMOD declares 'CBBE.esp'."""
    archive_root = _write_dynamic_type_fomod(tmp_path)
    result = fomod.fomod_parse_choices({
        "archive_path": str(archive_root),
        "mo2_state": {"enabled_plugins": ["cbbe.esp"], "provided_files": [], "game_version": None},
    })
    option = result["pages"][0]["groups"][0]["options"][0]
    assert option["type"] == "Recommended"
    assert option["dependencies_status"]["met"] is True
