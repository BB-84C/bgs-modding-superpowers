"""Tests for translation-unit extraction from TES4-family records."""

from __future__ import annotations

import struct
from pathlib import Path

from test_strings_io import _strings_bytes, write_ba2_gnrl
from test_tes4_family_walker import plugin_bytes, record, subrecord


def test_extract_translation_units(tmp_path: Path) -> None:
    from bgs_translator.parsers.extractor import extract_translation_units
    data = subrecord(b"EDID", b"WeaponEdid\x00") + subrecord(b"FULL", b"Sword\x00") + subrecord(
        b"DESC", b"A sharp thing\x00"
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
