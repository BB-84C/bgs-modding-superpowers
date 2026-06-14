"""Tests for qt_ini.parse_custom_executables."""

import sys
from pathlib import Path

LIVE_BRIDGE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(LIVE_BRIDGE_DIR))


def test_parse_two_entries(tmp_path):
    from qt_ini import parse_custom_executables

    ini = tmp_path / "ModOrganizer.ini"
    ini.write_text(
        r"""
[General]
gameName=Fallout 4

[customExecutables]
size=2
1\title=xEdit
1\binary=C:/Tools/xEdit/xEdit.exe
1\arguments=-fo4
1\workingDirectory=C:/Tools/xEdit
1\steamAppID=
1\ownicon=true
1\hide=false
2\title=LOOT
2\binary=C:/LOOT/LOOT.exe
2\arguments=
2\workingDirectory=
2\steamAppID=
2\ownicon=false
2\hide=false
""",
        encoding="utf-8",
    )

    entries = parse_custom_executables(ini)

    assert len(entries) == 2
    assert entries[0]["title"] == "xEdit"
    assert entries[0]["binary"] == "C:/Tools/xEdit/xEdit.exe"
    assert entries[0]["arguments"] == "-fo4"
    assert entries[0]["ownicon"] is True
    assert entries[0]["hide"] is False
    assert entries[1]["title"] == "LOOT"


def test_parse_missing_file(tmp_path):
    from qt_ini import parse_custom_executables

    entries = parse_custom_executables(tmp_path / "missing.ini")

    assert entries == []


def test_parse_empty_section(tmp_path):
    from qt_ini import parse_custom_executables

    ini = tmp_path / "ModOrganizer.ini"
    ini.write_text("[customExecutables]\nsize=0\n", encoding="utf-8")

    entries = parse_custom_executables(ini)

    assert entries == []


def test_parse_no_section(tmp_path):
    from qt_ini import parse_custom_executables

    ini = tmp_path / "ModOrganizer.ini"
    ini.write_text("[General]\ngameName=Skyrim\n", encoding="utf-8")

    entries = parse_custom_executables(ini)

    assert entries == []



def test_parse_skips_entries_without_title(tmp_path):
    """Entries with no title field are skipped (incomplete)."""

    from qt_ini import parse_custom_executables

    ini = tmp_path / "ModOrganizer.ini"
    ini.write_text(
        r"""
[customExecutables]
size=2
1\binary=foo.exe
2\title=Valid
2\binary=valid.exe
""",
        encoding="utf-8",
    )

    entries = parse_custom_executables(ini)

    assert len(entries) == 1
    assert entries[0]["title"] == "Valid"
