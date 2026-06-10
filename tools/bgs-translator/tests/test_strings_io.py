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


def write_ba2_gnrl(path: Path, members: dict[str, bytes]) -> None:
    header_size = 32
    entry_size = 36
    data_offset = header_size + len(members) * entry_size
    data = bytearray()
    entries = bytearray()
    names = bytearray()
    for member_path, payload in members.items():
        offset = data_offset + len(data)
        data.extend(payload)
        suffix = Path(member_path).suffix.lstrip(".").lower().encode("ascii")[:4].ljust(4, b"\x00")
        entries.extend(
            struct.pack(
                "<IIIIQIII",
                0,
                int.from_bytes(suffix, "little"),
                0,
                0x00100100,
                offset,
                0,
                len(payload),
                0xBAADF00D,
            )
        )
        encoded_name = member_path.encode("utf-8")
        names.extend(struct.pack("<H", len(encoded_name)) + encoded_name)
    name_table_offset = data_offset + len(data)
    path.write_bytes(
        struct.pack("<4sI4sIQII", b"BTDX", 2, b"GNRL", len(members), name_table_offset, 1, 0)
        + bytes(entries)
        + bytes(data)
        + bytes(names)
    )


def _strings_bytes(entries: dict[int, bytes], *, length_prefixed: bool = False) -> bytes:
    directory = bytearray()
    data = bytearray()
    for string_id, raw in entries.items():
        offset = len(data)
        directory.extend(struct.pack("<II", string_id, offset))
        if length_prefixed:
            data.extend(struct.pack("<I", len(raw) + 1))
        data.extend(raw + b"\x00")
    return struct.pack("<II", len(entries), len(data)) + bytes(directory) + bytes(data)


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


def test_strings_decode_allows_mixed_entry_encodings(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import read_strings_file

    path = tmp_path / "Mixed_english.STRINGS"
    _write_strings(path, {10: b"Alpha", 20: b"\xe9"}, length_prefixed=False)

    strings = read_strings_file(path, ["utf-8", "cp1252"])

    assert strings.encoding == "mixed"
    assert strings.entries == {10: "Alpha", 20: "é"}


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


def test_find_strings_sources_reads_sibling_starfield_ba2(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import find_strings_sources, read_strings_source

    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(b"")
    ba2 = tmp_path / "Example - main.ba2"
    write_ba2_gnrl(
        ba2,
        {
            "strings/Example_english.strings": _strings_bytes({1001: b"Archive Sword"}),
        },
    )

    found = find_strings_sources(plugin, game="Starfield")
    strings = read_strings_source(found["STRINGS"], ["utf-8"])

    assert found["STRINGS"].archive_path == ba2
    assert strings.entries == {1001: "Archive Sword"}


def test_find_strings_sources_accepts_starfield_en_alias_in_ba2(tmp_path: Path) -> None:
    from bgs_translator.parsers.strings_io import find_strings_sources

    plugin = tmp_path / "Creation.esm"
    plugin.write_bytes(b"")
    ba2 = tmp_path / "Creation - main.ba2"
    write_ba2_gnrl(
        ba2,
        {
            "strings/Creation_en.strings": _strings_bytes({1001: b"Alias Sword"}),
        },
    )

    found = find_strings_sources(plugin, "english", game="Starfield")

    assert found["STRINGS"].member_path == "strings/Creation_en.strings"
