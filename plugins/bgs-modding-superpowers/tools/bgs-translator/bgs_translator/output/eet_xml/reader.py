"""ESP-ESM Translator XML reader for Morrowind round-trip validation."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class EETXMLEntry:
    """One XML dictionary row."""

    record_sig: str
    field_sig: str
    edid: str | None
    source: str
    dest: str | None
    status: str


def read_eet_xml(path: Path) -> tuple[dict[str, Any], list[EETXMLEntry]]:
    """Parse an ESP-ESM Translator XML dictionary into metadata and entries."""

    root = ET.parse(path).getroot()
    metadata: dict[str, Any] = dict(root.attrib)
    plugins = root.findall("Plugin")
    if plugins:
        metadata["plugin"] = plugins[0].attrib.get("name", "")
    entries: list[EETXMLEntry] = []
    for plugin in plugins:
        for node in plugin.findall("String"):
            record_sig, field_sig = _split_rec(node.findtext("REC", default=""))
            entries.append(
                EETXMLEntry(
                    record_sig=record_sig,
                    field_sig=field_sig,
                    edid=_blank_to_none(node.findtext("EDID")),
                    source=node.findtext("Source", default=""),
                    dest=_blank_to_none(node.findtext("Dest")),
                    status=node.findtext("Status", default="untranslated"),
                )
            )
    return metadata, entries


def _split_rec(value: str) -> tuple[str, str]:
    if ":" not in value:
        return value, ""
    record_sig, field_sig = value.split(":", 1)
    return record_sig, field_sig


def _blank_to_none(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


__all__ = ["EETXMLEntry", "read_eet_xml"]
