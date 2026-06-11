"""ESP-ESM Translator XML writer for Morrowind dictionary output.

ESP-ESM Translator's XML dictionary schema is not formally documented. This
module emits a best-effort interim XML shape based on the TES3-shaped dictionary
keys called out in Chunk E planning and the xTranslator-style ``SSTXMLRessources``
root. TODO(Spike-1-followup): validate an emitted file in ESP-ESM Translator
4.35 and adjust the element names/attributes if its loader expects a stricter
community-dictionary shape.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

from bgs_translator.parsers.tes4_family import TranslationUnit


def write_eet_xml(
    output_path: Path,
    plugin_name: str,
    source_lang: str,
    target_lang: str,
    game: str,
    units: Iterable[TranslationUnit],
) -> None:
    """Write an ESP-ESM Translator XML dictionary file as UTF-8."""

    root = ET.Element(
        "SSTXMLRessources",
        {
            "version": "1.0",
            "sourceLang": source_lang,
            "targetLang": target_lang,
            "game": game,
        },
    )
    plugin = ET.SubElement(root, "Plugin", {"name": plugin_name})
    for unit in units:
        entry = ET.SubElement(plugin, "String")
        ET.SubElement(entry, "REC").text = f"{unit.signature}:{unit.field}"
        if unit.edid is not None:
            ET.SubElement(entry, "EDID").text = unit.edid
        ET.SubElement(entry, "Source").text = unit.source
        dest = getattr(unit, "dest", None)
        ET.SubElement(entry, "Dest").text = str(dest) if dest is not None else None
        ET.SubElement(entry, "Status").text = str(getattr(unit, "status", "untranslated"))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


__all__ = ["write_eet_xml"]
