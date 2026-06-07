"""Tests for localized STRINGS-family readers."""

from __future__ import annotations

import struct
from pathlib import Path


def _write_strings(path: Path, entries: dict[int, bytes], *, length_prefixed: bool) -> None:
    directory = bytearray()
    data = bytearray()
    for string_id, raw in entries.items():
        offset = len(data)
        directory.extend(struct.pack("<II", string_id, offset))
        if length_prefixed:
            data.extend(struct.pack("<I", len(raw) + 1))
        data.extend(raw + b"\x00")
    path.write_bytes(struct.pack("<II", len(entries), len(data)) + bytes(directory) + bytes(data))


def test_read_strings_file(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import read_strings_file

    path = tmp_path / "Example_english.STRINGS"
    _write_strings(path, {10: b"Alpha", 20: b"Beta"}, length_prefixed=False)

    strings = read_strings_file(path, ["utf-8"])

    assert strings.list_kind == "STRINGS"
    assert strings.encoding == "utf-8"
    assert strings.entries == {10: "Alpha", 20: "Beta"}


def test_read_dlstrings_file(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import read_strings_file

    path = tmp_path / "Example_english.DLSTRINGS"
    _write_strings(path, {30: b"Gamma"}, length_prefixed=True)

    strings = read_strings_file(path, ["utf-8"])

    assert strings.list_kind == "DLSTRINGS"
    assert strings.entries == {30: "Gamma"}


def test_strings_encoding_chain_is_honored(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import read_strings_file

    path = tmp_path / "Example_english.ILSTRINGS"
    _write_strings(path, {40: b"\xe9"}, length_prefixed=True)

    strings = read_strings_file(path, ["utf-8", "cp1252"])

    assert strings.encoding == "cp1252"
    assert strings.entries == {40: "é"}


def test_find_strings_files(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import find_strings_files

    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(b"")
    strings_dir = tmp_path / "Strings"
    strings_dir.mkdir()
    expected = strings_dir / "Example_english.STRINGS"
    expected.write_bytes(b"")

    found = find_strings_files(plugin)

    assert found == {"STRINGS": expected}
