"""Reader for xTranslator SST vocab files (SSU2..SSU9).

The reader is version-keyed: it matches the cascade in
``TESVT_SSTFunc.pas:loadSstEdit``, missing fields default per PRD §5.

Version capabilities (internal version → on-disk label):

================  ============================================================
internal version  on-disk label   capability gained
================  ============================================================
1                 SSU2            base entry stream (no struct, no headers)
2                 SSU3            strID + formID + fName per entry
3                 SSU4            index per entry
4                 SSU5            indexMax + rHash per entry; v4 flag byte
5                 SSU6            rName per entry
6                 SSU7            colabId per entry
7                 SSU8            colab label section
8                 SSU9            masterList section
================  ============================================================
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from io import BufferedReader
from pathlib import Path
from typing import BinaryIO

from .envelope import detect_version, label_for_version
from .status import from_byte
from .writer import SSTUnit

__all__ = [
    "SSTFile",
    "read_sst",
]


@dataclass(slots=True)
class SSTFile:
    """Decoded SST file: header sections + ordered entry list."""

    version: int
    label: str
    masters: list[str] = field(default_factory=list)
    colab_labels: list[tuple[int, str]] = field(default_factory=list)
    entries: list[SSTUnit] = field(default_factory=list)


def _read_exactly(handle: BinaryIO, n: int) -> bytes:
    buf = handle.read(n)
    if len(buf) != n:
        raise EOFError(f"unexpected EOF: wanted {n} bytes, got {len(buf)}")
    return buf


def _read_i32(handle: BinaryIO) -> int:
    return int(struct.unpack("<i", _read_exactly(handle, 4))[0])


def _read_u16(handle: BinaryIO) -> int:
    return int(struct.unpack("<H", _read_exactly(handle, 2))[0])


def _read_u32(handle: BinaryIO) -> int:
    return int(struct.unpack("<I", _read_exactly(handle, 4))[0])


def _read_utf16_block(handle: BinaryIO) -> str:
    byte_size = _read_i32(handle)
    if byte_size < 0:
        raise ValueError(f"negative UTF-16 byte size: {byte_size}")
    if byte_size == 0:
        return ""
    if byte_size % 2 != 0:
        raise ValueError(f"odd UTF-16 byte size: {byte_size}")
    return _read_exactly(handle, byte_size).decode("utf-16-le")


def _read_master_table(handle: BinaryIO) -> list[str]:
    count = _read_i32(handle)
    if count < 0:
        raise ValueError(f"negative masterCount: {count}")
    return [_read_utf16_block(handle) for _ in range(count)]


def _read_colab_table(handle: BinaryIO) -> list[tuple[int, str]]:
    count = _read_i32(handle)
    if count < 0:
        raise ValueError(f"negative colabCount: {count}")
    return [(_read_i32(handle), _read_utf16_block(handle)) for _ in range(count)]


def _decode_sig(raw: bytes) -> str:
    # NUL-strip 4-byte signatures; older versions store empty fName as zeros.
    return raw.rstrip(b"\x00").decode("ascii", errors="replace")


def _read_entry(handle: BinaryIO, version: int) -> SSTUnit:
    list_index = _read_exactly(handle, 1)[0]
    strid = 0
    formid = 0
    signature = ""
    field_sig = ""
    idx = 0
    idx_max = 0
    rhash = 0
    colab_id = 0
    if version > 1:
        strid = int(struct.unpack("<i", _read_exactly(handle, 4))[0])
        formid = _read_u32(handle)
        if version > 4:
            signature = _decode_sig(_read_exactly(handle, 4))
        field_sig = _decode_sig(_read_exactly(handle, 4))
        if version > 2:
            idx = _read_u16(handle)
        if version > 3:
            idx_max = _read_u16(handle)
            rhash = _read_u32(handle)
        if version > 5:
            colab_id = _read_exactly(handle, 1)[0]
    s_params = _read_exactly(handle, 1)[0]
    source = _read_utf16_block(handle)
    dest = _read_utf16_block(handle)
    return SSTUnit(
        list_index=list_index,
        strid=strid,
        formid=formid,
        signature=signature,
        field=field_sig,
        index=idx,
        index_max=idx_max,
        rhash=rhash,
        colab_id=colab_id,
        s_params=int(from_byte(s_params)),
        source=source,
        dest=dest,
    )


def read_sst(path: Path) -> SSTFile:
    """Read an SST file at *path* and return its decoded contents.

    Accepts SSU2..SSU9. Missing fields take the per-version defaults defined
    by the PRD §5 (empty signatures, zero IDs / hashes, no colabId, etc.).
    """
    with open(path, "rb") as handle:
        reader: BufferedReader = handle
        magic_buf = reader.read(4)
        version = detect_version(magic_buf)
        if version == 0:
            raise ValueError(
                f"unrecognized SST magic: {magic_buf.hex()!r} at {path}"
            )
        sst = SSTFile(version=version, label=label_for_version(version))
        # v4 placeholder flag byte (Pascal: ``if version > 3``).
        if version > 3:
            _read_exactly(reader, 1)
        if version > 7:
            sst.masters.extend(_read_master_table(reader))
        if version > 6:
            sst.colab_labels.extend(_read_colab_table(reader))
        # Entries until EOF.
        while True:
            peek = reader.read(1)
            if not peek:
                break
            reader.seek(-1, 1)  # rewind one byte; entry parser re-reads it
            sst.entries.append(_read_entry(reader, version))
        return sst


# NOTE: ``POINTER_LITE_STRUCT`` and ``SStrParam`` live in ``writer`` and
# ``status`` respectively. They are re-exported via the package ``__init__``
# so callers can import them from ``bgs_translator.sst`` directly without the
# reader having to import-and-shadow them here.
