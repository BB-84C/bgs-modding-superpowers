"""Tests for translation-unit extraction from TES4-family records."""

from __future__ import annotations

import struct
from pathlib import Path

from test_strings_io import _strings_bytes, write_ba2_gnrl
from test_tes4_family_walker import plugin_bytes, record, subrecord


def test_extract_translation_units(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units

    data = (
        subrecord(b"EDID", b"WeaponEdid\x00")
        + subrecord(b"FULL", b"Sword\x00")
        + subrecord(b"DESC", b"A sharp thing\x00")
    )
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(child=record(b"WEAP", data, formid=0xFE001234)))

    units = list(extract_translation_units(plugin, "SkyrimSE"))

    assert [unit.source for unit in units] == ["Sword", "A sharp thing"]
    assert units[0].edid == "WeaponEdid"
    assert units[0].formid_sanitized == 0x001234


def test_multi_value_itxt_indices(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units

    data = subrecord(b"ITXT", b"Choice A\x00") + subrecord(b"ITXT", b"Choice B\x00")
    plugin = tmp_path / "Message.esm"
    plugin.write_bytes(plugin_bytes(child=record(b"MESG", data)))

    units = list(extract_translation_units(plugin, "SkyrimSE"))

    assert [(unit.field, unit.index_n, unit.index_max, unit.source) for unit in units] == [
        ("ITXT", 0, 1, "Choice A"),
        ("ITXT", 1, 1, "Choice B"),
    ]


def test_extract_localized_starfield_units_from_sibling_ba2(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units

    data = subrecord(b"FULL", struct.pack("<I", 1001))
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80, child=record(b"WEAP", data, fv=552)))
    write_ba2_gnrl(
        tmp_path / "Example - main.ba2",
        {
            "strings/Example_english.strings": _strings_bytes({1001: b"Archive Sword"}),
        },
    )

    units = list(extract_translation_units(plugin, "Starfield"))

    assert [unit.source for unit in units] == ["Archive Sword"]
    assert units[0].strid == 1001


def test_extract_localized_starfield_quest_cnam_from_dlstrings(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units
    from bgs_translator.parsers.schemas import get_schema_for_game

    data = (
        subrecord(b"EDID", b"QuestEdid\x00")
        + subrecord(b"FULL", struct.pack("<I", 1001))
        + subrecord(b"CNAM", struct.pack("<I", 2001))
        + subrecord(b"CNAM", struct.pack("<I", 2002))
    )
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80, child=record(b"QUST", data, fv=552)))
    write_ba2_gnrl(
        tmp_path / "Example - main.ba2",
        {
            "strings/Example_english.strings": _strings_bytes({1001: b"Quest Name"}),
            "strings/Example_english.dlstrings": _strings_bytes(
                {2001: b"Quest log A", 2002: b"Quest log B"},
                length_prefixed=True,
            ),
        },
    )

    units = list(
        extract_translation_units(plugin, "Starfield", schema=get_schema_for_game("Starfield"))
    )

    cnam_units = [unit for unit in units if unit.signature == "QUST" and unit.field == "CNAM"]
    assert [
        (unit.list_index, unit.strid, unit.index_n, unit.index_max, unit.source)
        for unit in cnam_units
    ] == [
        (1, 2001, 0, 1, "Quest log A"),
        (1, 2002, 1, 1, "Quest log B"),
    ]


def test_extract_localized_starfield_uses_xtranslator_full_fallback(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units
    from bgs_translator.parsers.schemas import get_schema_for_game

    data = subrecord(b"EDID", b"ReferenceEdid\x00") + subrecord(
        b"FULL", struct.pack("<I", 1001)
    )
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80, child=record(b"REFR", data, fv=552)))
    write_ba2_gnrl(
        tmp_path / "Example - main.ba2",
        {
            "strings/Example_english.strings": _strings_bytes({1001: b"Reference Name"}),
        },
    )

    units = list(
        extract_translation_units(plugin, "Starfield", schema=get_schema_for_game("Starfield"))
    )

    assert [(unit.signature, unit.field, unit.list_index, unit.source) for unit in units] == [
        ("REFR", "FULL", 0, "Reference Name")
    ]


def test_extract_localized_starfield_recorddef_exact_field_overrides_fallback(
    tmp_path: Path,
) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units
    from bgs_translator.parsers.schemas import get_schema_for_game

    data = subrecord(b"EDID", b"LoadScreenEdid\x00") + subrecord(
        b"DESC", struct.pack("<I", 1001)
    )
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80, child=record(b"LSCR", data, fv=552)))
    write_ba2_gnrl(
        tmp_path / "Example - main.ba2",
        {
            "strings/Example_english.strings": _strings_bytes({1001: b"Loading tip"}),
            "strings/Example_english.dlstrings": _strings_bytes(
                {1001: b"Wrong fallback"},
                length_prefixed=True,
            ),
        },
    )

    units = list(
        extract_translation_units(plugin, "Starfield", schema=get_schema_for_game("Starfield"))
    )

    assert [(unit.signature, unit.field, unit.list_index, unit.source) for unit in units] == [
        ("LSCR", "DESC", 0, "Loading tip"),
        ("ORPH", "DLST", 1, "Wrong fallback"),
    ]


def test_extract_localized_starfield_keeps_xtranslator_orphan_strings(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units

    data = subrecord(b"FULL", struct.pack("<I", 1001))
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80, child=record(b"WEAP", data, fv=552)))
    write_ba2_gnrl(
        tmp_path / "Example - main.ba2",
        {
            "strings/Example_english.strings": _strings_bytes(
                {1001: b"Archive Sword", 2002: b"Loose menu label"}
            ),
        },
    )

    units = list(extract_translation_units(plugin, "Starfield"))

    assert [(unit.signature, unit.field, unit.strid, unit.source) for unit in units] == [
        ("WEAP", "FULL", 1001, "Archive Sword"),
        ("ORPH", "STRS", 2002, "Loose menu label"),
    ]


def test_starfield_repeated_localized_weapon_names_get_sst_indices(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units
    from bgs_translator.parsers.schemas import get_schema_for_game

    data = (
        subrecord(b"EDID", b"WeaponEdid\x00")
        + subrecord(b"FULL", struct.pack("<I", 1001))
        + subrecord(b"FULL", struct.pack("<I", 1002))
    )
    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80, child=record(b"WEAP", data, fv=552)))
    write_ba2_gnrl(
        tmp_path / "Example - main.ba2",
        {
            "strings/Example_english.strings": _strings_bytes(
                {1001: b"Standard", 1002: b"Advanced"}
            ),
        },
    )

    units = list(
        extract_translation_units(plugin, "Starfield", schema=get_schema_for_game("Starfield"))
    )

    assert [(unit.source, unit.index_n, unit.index_max, unit.strid) for unit in units] == [
        ("Standard", 0, 1, 1001),
        ("Advanced", 1, 1, 1002),
    ]
