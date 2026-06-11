"""Tests for the Morrowind TES3 binary walker."""

from __future__ import annotations

import struct
from pathlib import Path


def tes3_subrecord(sig: bytes, data: bytes) -> bytes:
    return sig + struct.pack("<I", len(data)) + data


def tes3_record(sig: bytes, data: bytes, *, flags: int = 0) -> bytes:
    return sig + struct.pack("<III", len(data), 0, flags) + data


def tes3_plugin(*records: bytes) -> bytes:
    header_payload = tes3_subrecord(b"HEDR", struct.pack("<fII32s256s", 1.3, 1, 0, b"", b""))
    return tes3_record(b"TES3", header_payload) + b"".join(records)


def test_walks_tes3_header_and_record(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes3 import TES3Walker

    book_payload = b"".join(
        [
            tes3_subrecord(b"NAME", b"book_skill_alchemy\x00"),
            tes3_subrecord(b"FNAM", b"Alchemy Master\x00"),
            tes3_subrecord(b"DESC", b"This tome contains secrets.\x00"),
            tes3_subrecord(b"TEXT", b"A" * 70000),
        ]
    )
    plugin = tmp_path / "Morrowind.esm"
    plugin.write_bytes(tes3_plugin(tes3_record(b"BOOK", book_payload, flags=0x1234)))

    records = list(TES3Walker(plugin).walk())

    assert [record.sig for record in records] == ["TES3", "BOOK"]
    assert records[1].flags == 0x1234
    assert records[1].identity == "book_skill_alchemy"
    assert [(sub.sig, len(sub.data)) for sub in records[1].subrecords] == [
        ("NAME", len(b"book_skill_alchemy\x00")),
        ("FNAM", len(b"Alchemy Master\x00")),
        ("DESC", len(b"This tome contains secrets.\x00")),
        ("TEXT", 70000),
    ]


def test_dele_subrecord_marks_record_deleted(tmp_path: Path) -> None:
    from bgs_translator.parsers.tes3 import TES3Walker

    plugin = tmp_path / "Deleted.esp"
    plugin.write_bytes(
        tes3_plugin(
            tes3_record(
                b"BOOK",
                tes3_subrecord(b"NAME", b"deleted_book\x00") + tes3_subrecord(b"DELE", b"\x00\x00\x00\x00"),
            )
        )
    )

    _header, book = list(TES3Walker(plugin).walk())

    assert book.is_deleted is True
    assert book.identity == "deleted_book"
