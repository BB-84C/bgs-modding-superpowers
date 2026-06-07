"""Tests for the TES4-family binary walker."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def subrecord(sig: bytes, data: bytes, *, forced_size: int | None = None) -> bytes:
    size = len(data) if forced_size is None else forced_size
    return sig + struct.pack("<H", size) + data


def record(sig: bytes, data: bytes, *, flags: int = 0, formid: int = 0x01020304, fv: int = 43) -> bytes:
    return sig + struct.pack("<III I H H", len(data), flags, formid, 0, fv, 0) + data


def tes4_header(*, flags: int = 0, fv: int = 43) -> bytes:
    hedr = struct.pack("<fII", 1.0, 1, fv)
    return record(b"TES4", subrecord(b"HEDR", hedr), flags=flags, formid=0, fv=fv)


def grup(*children: bytes) -> bytes:
    payload = b"".join(children)
    return b"GRUP" + struct.pack("<I4sIII", 24 + len(payload), b"WEAP", 0, 0, 0) + payload


def plugin_bytes(*, flags: int = 0, child: bytes | None = None) -> bytes:
    if child is None:
        child = record(b"WEAP", subrecord(b"FULL", b"Test Sword\x00"))
    return tes4_header(flags=flags) + grup(child)


def test_walks_minimal_plugin(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes4_family import TES4FamilyWalker

    plugin = tmp_path / "Example.esm"
    plugin.write_bytes(plugin_bytes())

    records = list(TES4FamilyWalker(plugin).walk())

    assert len(records) == 1
    assert records[0].sig == "WEAP"
    assert records[0].formid == 0x01020304
    assert records[0].subrecords[0].sig == "FULL"
    assert records[0].subrecords[0].data == b"Test Sword\x00"


def test_xxxx_overflow(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes4_family import TES4FamilyWalker

    payload = b"A" * 70000
    data = subrecord(b"XXXX", struct.pack("<I", len(payload))) + subrecord(
        b"DESC", payload, forced_size=0
    )
    plugin = tmp_path / "Overflow.esm"
    plugin.write_bytes(plugin_bytes(child=record(b"WEAP", data)))

    parsed = next(TES4FamilyWalker(plugin).walk())

    assert parsed.subrecords[0].sig == "DESC"
    assert parsed.subrecords[0].data == payload


def test_compressed_record(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes4_family import TES4FamilyWalker

    raw = subrecord(b"FULL", b"Compressed\x00")
    compressed = struct.pack("<I", len(raw)) + zlib.compress(raw)
    plugin = tmp_path / "Compressed.esm"
    plugin.write_bytes(plugin_bytes(child=record(b"WEAP", compressed, flags=0x40000)))

    parsed = next(TES4FamilyWalker(plugin).walk())

    assert parsed.is_compressed is True
    assert parsed.subrecords[0].data == b"Compressed\x00"


def test_esl_flag_detection(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes4_family import TES4FamilyWalker
    plugin = tmp_path / "Light.esl"
    plugin.write_bytes(plugin_bytes(flags=0x200))
    walker = TES4FamilyWalker(plugin)

    list(walker.walk())


    assert walker.header is not None
    assert walker.header.is_esl is True


def test_localized_flag_detection(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes4_family import TES4FamilyWalker
    plugin = tmp_path / "Localized.esm"
    plugin.write_bytes(plugin_bytes(flags=0x80))
    walker = TES4FamilyWalker(plugin)

    list(walker.walk())

    assert walker.header is not None
    assert walker.header.is_localized is True
