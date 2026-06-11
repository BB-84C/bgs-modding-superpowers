"""Tests for ESP-ESM Translator XML writing."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def test_write_eet_xml_structure(tmp_path: Path) -> None:
    from bgs_translator.output.eet_xml.writer import write_eet_xml
    from bgs_translator.parsers.tes4_family import TranslationUnit

    output = tmp_path / "dict.xml"
    units = [
        TranslationUnit("Sample.esm", 0, 0, "book_skill_alchemy", "BOOK", "FNAM", "Alchemy Master"),
        TranslationUnit("Sample.esm", 0, 0, "book_skill_alchemy", "BOOK", "DESC", "Secret text"),
    ]

    write_eet_xml(output, "Sample.esm", "en", "zh-cn", "Morrowind", units)

    root = ET.parse(output).getroot()
    plugin = root.find("Plugin")
    strings = root.findall("./Plugin/String")

    assert root.tag == "SSTXMLRessources"
    assert root.attrib == {"version": "1.0", "sourceLang": "en", "targetLang": "zh-cn", "game": "Morrowind"}
    assert plugin is not None
    assert plugin.attrib["name"] == "Sample.esm"
    assert [entry.findtext("REC") for entry in strings] == ["BOOK:FNAM", "BOOK:DESC"]
    assert [entry.findtext("EDID") for entry in strings] == ["book_skill_alchemy", "book_skill_alchemy"]
    assert [entry.findtext("Status") for entry in strings] == ["untranslated", "untranslated"]
