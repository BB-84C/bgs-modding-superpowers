"""Tests for translation-unit extraction from TES4-family records."""

from __future__ import annotations

from pathlib import Path

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
