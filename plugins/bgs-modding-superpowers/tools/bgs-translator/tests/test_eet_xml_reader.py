"""Tests for ESP-ESM Translator XML reading."""

from __future__ import annotations

from pathlib import Path


def test_read_eet_xml_entries(tmp_path: Path) -> None:
    from bgs_translator.output.eet_xml.reader import read_eet_xml

    sample = tmp_path / "sample.xml"
    sample.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<SSTXMLRessources version="1.0" sourceLang="en" targetLang="zh-cn" game="Morrowind">
  <Plugin name="Sample.esm">
    <String>
      <REC>BOOK:FNAM</REC>
      <EDID>book_skill_alchemy</EDID>
      <Source>Alchemy Master</Source>
      <Dest>炼金大师</Dest>
      <Status>translated</Status>
    </String>
  </Plugin>
</SSTXMLRessources>
""",
        encoding="utf-8",
    )

    metadata, entries = read_eet_xml(sample)

    assert metadata == {
        "version": "1.0",
        "sourceLang": "en",
        "targetLang": "zh-cn",
        "game": "Morrowind",
        "plugin": "Sample.esm",
    }
    assert len(entries) == 1
    assert entries[0].record_sig == "BOOK"
    assert entries[0].field_sig == "FNAM"
    assert entries[0].edid == "book_skill_alchemy"
    assert entries[0].source == "Alchemy Master"
    assert entries[0].dest == "炼金大师"
    assert entries[0].status == "translated"
