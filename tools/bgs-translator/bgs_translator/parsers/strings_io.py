"""Localized STRINGS, DLSTRINGS, and ILSTRINGS IO ownership."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bgs_translator.parsers.encoding import decode_with_chain

StringsListKind = Literal["STRINGS", "DLSTRINGS", "ILSTRINGS"]


@dataclass
class StringsFile:
    """Decoded localized string table."""

    path: Path
    list_kind: StringsListKind
    encoding: str
    entries: dict[int, str]


def find_strings_files(plugin_path: Path, target_lang_code: str = "english") -> dict[str, Path]:
    """Locate sibling localized STRINGS-family files for ``plugin_path``."""

    strings_dir = plugin_path.parent / "Strings"
    stem = plugin_path.stem
    found: dict[str, Path] = {}
    for list_kind in ("STRINGS", "DLSTRINGS", "ILSTRINGS"):
        candidate = strings_dir / f"{stem}_{target_lang_code}.{list_kind}"
        if candidate.exists():
            found[list_kind] = candidate
    return found


def _kind_from_suffix(path: Path) -> StringsListKind:
    suffix = path.suffix.upper().lstrip(".")
    if suffix in {"STRINGS", "DLSTRINGS", "ILSTRINGS"}:
        return suffix  # type: ignore[return-value]
    raise ValueError(f"Unsupported STRINGS-family suffix: {path.suffix}")


def _decode_entries(raw_entries: dict[int, bytes], encoding_chain: list[str]) -> tuple[dict[int, str], str]:
    decoded: dict[int, str] = {}
    encoding_used: str | None = None
    for string_id, raw in raw_entries.items():
        text, encoding = decode_with_chain(raw, encoding_chain)
        if encoding_used is None:
            encoding_used = encoding
        elif encoding != encoding_used:
            text, encoding_used = decode_with_chain(raw, [encoding_used])
        decoded[string_id] = text
    return decoded, encoding_used or (encoding_chain[0] if encoding_chain else "")


def read_strings_file(path: Path, encoding_chain: list[str]) -> StringsFile:
    """Parse a Bethesda STRINGS, DLSTRINGS, or ILSTRINGS file."""

    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"STRINGS file too short: {path}")
    count, data_size = struct.unpack_from("<II", data, 0)
    directory_start = 8
    directory_end = directory_start + count * 8
    data_start = directory_end
    data_end = data_start + data_size
    if directory_end > len(data) or data_end > len(data):
        raise ValueError(f"STRINGS directory exceeds file size: {path}")

    list_kind = _kind_from_suffix(path)
    block = data[data_start:data_end]
    raw_entries: dict[int, bytes] = {}
    for index in range(count):
        string_id, offset = struct.unpack_from("<II", data, directory_start + index * 8)
        if offset >= len(block):
            raw_entries[string_id] = b""
            continue
        if list_kind == "STRINGS":
            terminator = block.find(b"\x00", offset)
            end = len(block) if terminator == -1 else terminator
            raw_entries[string_id] = block[offset:end]
            continue
        if offset + 4 > len(block):
            raw_entries[string_id] = b""
            continue
        length = struct.unpack_from("<I", block, offset)[0]
        start = offset + 4
        end = min(start + length, len(block))
        raw = block[start:end]
        raw_entries[string_id] = raw[:-1] if raw.endswith(b"\x00") else raw

    entries, encoding = _decode_entries(raw_entries, encoding_chain)
    return StringsFile(path=path, list_kind=list_kind, encoding=encoding, entries=entries)


__all__ = ["StringsFile", "StringsListKind", "find_strings_files", "read_strings_file"]
