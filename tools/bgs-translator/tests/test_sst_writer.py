"""Byte-level tests for the SSU9 / SSU8 SST writer."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from bgs_translator.sst.envelope import SSU8, SSU9
from bgs_translator.sst.hash import compute_rhash
from bgs_translator.sst.status import SStrParam
from bgs_translator.sst.writer import (
    ENTRY_FIXED_SIZE,
    POINTER_LITE_SIZE,
    SSTUnit,
    encode_pointer_lite,
    write_sst,
)


def _make_unit(**overrides: object) -> SSTUnit:
    base: dict[str, object] = {
        "list_index": 0,
        "strid": 0,
        "formid": 0x00000800,
        "signature": "PERK",
        "field": "EPF2",
        "index": 0,
        "index_max": 1,
        "rhash": compute_rhash("MyEdid", 0x00000800),
        "colab_id": 0,
        "s_params": int(SStrParam.TRANSLATED),
        "source": "Take Book",
        "dest": "拿书",
    }
    base.update(overrides)
    return SSTUnit(**base)  # type: ignore[arg-type]


def test_encode_pointer_lite_is_24_bytes() -> None:
    unit = _make_unit()
    blob = encode_pointer_lite(unit)
    assert len(blob) == POINTER_LITE_SIZE == 24
    # rName/fName must land at offsets 8 and 12.
    assert blob[8:12] == b"PERK"
    assert blob[12:16] == b"EPF2"
    # Strid (signed Int32 LE) at 0..4.
    assert blob[0:4] == b"\x00\x00\x00\x00"
    # FormID (UInt32 LE) at 4..8.
    assert blob[4:8] == b"\x00\x08\x00\x00"


def test_encode_pointer_lite_pads_short_signatures() -> None:
    unit = _make_unit(signature="ABC", field="X")
    blob = encode_pointer_lite(unit)
    assert blob[8:12] == b"ABC\x00"
    assert blob[12:16] == b"X\x00\x00\x00"


def test_encode_pointer_lite_rejects_oversized_signatures() -> None:
    with pytest.raises(ValueError):
        encode_pointer_lite(_make_unit(signature="ABCDE"))
    with pytest.raises(ValueError):
        encode_pointer_lite(_make_unit(field="ABCDE"))


def test_encode_pointer_lite_rejects_non_ascii_signatures() -> None:
    with pytest.raises(ValueError):
        encode_pointer_lite(_make_unit(signature="P\u00c9RK"))


def test_write_sst_empty(tmp_path: Path) -> None:
    out = tmp_path / "empty.sst"
    write_sst(out, [], masters=[])
    data = out.read_bytes()
    # magic + flag + masterCount(0) + colabCount(0)
    expected = struct.pack("<I", SSU9) + b"\x00" + struct.pack("<i", 0) + struct.pack("<i", 0)
    assert data == expected
    assert len(data) == 4 + 1 + 4 + 4


def test_write_sst_master_table_layout(tmp_path: Path) -> None:
    out = tmp_path / "masters.sst"
    write_sst(out, [], masters=["a.esm", "b.esp"])
    data = out.read_bytes()
    # After magic(4) + flag(1) + masterCount(4) = 9 bytes.
    cursor = 9
    assert struct.unpack("<I", data[:4])[0] == SSU9
    assert data[4] == 0
    assert struct.unpack("<i", data[5:9])[0] == 2  # masterCount
    # First master.
    size = struct.unpack("<i", data[cursor : cursor + 4])[0]
    assert size == len("a.esm") * 2
    cursor += 4
    assert data[cursor : cursor + size].decode("utf-16-le") == "a.esm"
    cursor += size
    # Second master.
    size = struct.unpack("<i", data[cursor : cursor + 4])[0]
    assert size == len("b.esp") * 2
    cursor += 4
    assert data[cursor : cursor + size].decode("utf-16-le") == "b.esp"
    cursor += size
    # colab count = 0
    assert struct.unpack("<i", data[cursor : cursor + 4])[0] == 0


def test_write_sst_single_entry(tmp_path: Path) -> None:
    out = tmp_path / "one.sst"
    unit = _make_unit()
    write_sst(out, [unit], masters=["a.esm"])
    data = out.read_bytes()
    # Compute where entry begins: magic(4)+flag(1)+masters(4 + 4 + 10)+colab(4)
    header_size = 4 + 1 + 4 + 4 + len("a.esm") * 2 + 4
    entry_blob = data[header_size:]
    # Entry: 1 listIndex + 24 ptr + 1 colab + 1 sparams + 4 src_size + src + 4 dst_size + dst
    src_bytes = unit.source.encode("utf-16-le")
    dst_bytes = unit.dest.encode("utf-16-le")
    expected_len = (
        ENTRY_FIXED_SIZE + len(src_bytes) + 4 + len(dst_bytes)
    )  # ENTRY_FIXED_SIZE includes the src size prefix.
    assert len(entry_blob) == expected_len
    assert entry_blob[0] == 0  # listIndex
    # rEspPointerLite (24 bytes): bytes 1..25
    assert entry_blob[1 + 8 : 1 + 12] == b"PERK"
    assert entry_blob[1 + 12 : 1 + 16] == b"EPF2"
    # colabId then sparams.
    assert entry_blob[25] == 0
    assert entry_blob[26] == int(SStrParam.TRANSLATED)
    # src size + src
    src_size = struct.unpack("<i", entry_blob[27:31])[0]
    assert src_size == len(src_bytes)
    assert entry_blob[31 : 31 + src_size] == src_bytes
    # dst size + dst
    after_src = 31 + src_size
    dst_size = struct.unpack("<i", entry_blob[after_src : after_src + 4])[0]
    assert dst_size == len(dst_bytes)
    assert entry_blob[after_src + 4 :] == dst_bytes


def test_write_sst_multiple_entries(tmp_path: Path) -> None:
    out = tmp_path / "many.sst"
    units = [
        _make_unit(source=f"src{i}", dest=f"dst{i}", index=i) for i in range(5)
    ]
    write_sst(out, units, masters=["m.esm"])
    data = out.read_bytes()
    # File must be non-trivial.
    assert len(data) > 100
    # Magic at start.
    assert struct.unpack("<I", data[:4])[0] == SSU9


def test_write_sst_strips_validated_flag(tmp_path: Path) -> None:
    out = tmp_path / "validated.sst"
    unit = _make_unit(s_params=int(SStrParam.TRANSLATED | SStrParam.VALIDATED))
    write_sst(out, [unit], masters=[])
    data = out.read_bytes()
    # sParams sits at the 27th byte of the entry (after listIndex + 24-byte ptr + colab).
    # Header: 4 magic + 1 flag + 4 masterCount(0) + 4 colabCount(0) = 13.
    entry_start = 13
    sparams_byte = data[entry_start + 1 + 24 + 1]
    assert sparams_byte == int(SStrParam.TRANSLATED)
    assert sparams_byte & int(SStrParam.VALIDATED) == 0


def test_write_sst_colab_table_layout(tmp_path: Path) -> None:
    out = tmp_path / "colab.sst"
    write_sst(
        out,
        [],
        masters=[],
        colab_labels=[(1, "alpha"), (5, "beta")],
    )
    data = out.read_bytes()
    cursor = 4 + 1 + 4  # magic + flag + masterCount(0)
    assert struct.unpack("<i", data[cursor : cursor + 4])[0] == 2  # colab count
    cursor += 4
    # First colab.
    assert struct.unpack("<i", data[cursor : cursor + 4])[0] == 1
    cursor += 4
    size = struct.unpack("<i", data[cursor : cursor + 4])[0]
    cursor += 4
    assert data[cursor : cursor + size].decode("utf-16-le") == "alpha"
    cursor += size
    # Second colab.
    assert struct.unpack("<i", data[cursor : cursor + 4])[0] == 5


def test_write_sst_ssu8_downgrade_omits_master_list(tmp_path: Path) -> None:
    out = tmp_path / "ssu8.sst"
    write_sst(out, [], masters=["never-emitted.esm"], sst_version="SSU8")
    data = out.read_bytes()
    # SSU8 layout: magic(4) + flag(1) + colabCount(4) = 9 bytes total, no masterList.
    assert len(data) == 9
    assert struct.unpack("<I", data[:4])[0] == SSU8
    assert data[4] == 0
    assert struct.unpack("<i", data[5:9])[0] == 0  # colab count


def test_write_sst_rejects_unknown_version(tmp_path: Path) -> None:
    out = tmp_path / "bad.sst"
    with pytest.raises(ValueError):
        write_sst(out, [], masters=[], sst_version="SSU7")  # type: ignore[arg-type]


def test_write_sst_rejects_byte_overflow(tmp_path: Path) -> None:
    out = tmp_path / "bad-byte.sst"
    with pytest.raises(ValueError):
        write_sst(out, [_make_unit(list_index=300)], masters=[])
    with pytest.raises(ValueError):
        write_sst(out, [_make_unit(colab_id=999)], masters=[])
