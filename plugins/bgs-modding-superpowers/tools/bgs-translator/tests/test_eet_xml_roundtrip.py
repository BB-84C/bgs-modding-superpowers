"""Round-trip tests for ESP-ESM Translator XML I/O."""

from __future__ import annotations

from pathlib import Path


def test_eet_xml_write_read_roundtrip(tmp_path: Path) -> None:
    from bgs_translator.output.eet_xml.reader import read_eet_xml
    from bgs_translator.output.eet_xml.writer import write_eet_xml
    from bgs_translator.parsers.tes4_family import TranslationUnit

    output = tmp_path / "roundtrip.xml"
    units = [
        TranslationUnit("Sample.esm", 0, 0, "book_skill_alchemy", "BOOK", "FNAM", "Alchemy Master"),
        TranslationUnit("Sample.esm", 0, 0, None, "CELL", "NAME", "Balmora"),
    ]

    write_eet_xml(output, "Sample.esm", "en", "zh-cn", "Morrowind", units)
    metadata, entries = read_eet_xml(output)

    assert metadata["plugin"] == "Sample.esm"
    assert [(entry.record_sig, entry.field_sig, entry.edid, entry.source, entry.dest, entry.status) for entry in entries] == [
        ("BOOK", "FNAM", "book_skill_alchemy", "Alchemy Master", None, "untranslated"),
        ("CELL", "NAME", None, "Balmora", None, "untranslated"),
    ]
