"""Morrowind TES3 record and inline-string walker ownership.

TES3 plugins are a flat sequence of records. They do not have TES4-family GRUPs,
record compression, FormIDs, localized STRINGS files, or ``XXXX`` subrecord-size
overflows. The important binary difference for this walker is that TES3
subrecord sizes are unsigned 32-bit little-endian values.
"""

from __future__ import annotations

import io
import logging
import mmap
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from bgs_translator.parsers.encoding import decode_with_chain

log = logging.getLogger(__name__)

RECORD_HEADER_SIZE = 16
SUBRECORD_HEADER_SIZE = 8
DELETED_SUBRECORD_SIG = "DELE"
MMAP_THRESHOLD_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class TES3Subrecord:
    """Raw TES3 subrecord payload."""

    sig: str
    data: bytes


@dataclass(frozen=True)
class TES3Record:
    """TES3 record with parsed subrecords and NAME-derived identity."""

    sig: str
    flags: int
    identity: str | None
    subrecords: list[TES3Subrecord]
    is_deleted: bool


class CorruptTES3RecordError(ValueError):
    """Raised when a TES3 record cannot be decoded safely."""


class TES3Walker:
    """Read a Morrowind TES3 plugin and yield records, including the TES3 header."""

    def __init__(self, plugin_path: Path, encoding_chain: list[str] | None = None) -> None:
        self.plugin_path = plugin_path
        self.encoding_chain = encoding_chain or ["cp1252", "utf-8"]

    def walk(self) -> Iterator[TES3Record]:
        """Open plugin, yield records including the TES3 file header as the first yield."""

        data = self._read_plugin_bytes()
        f = io.BytesIO(data)
        file_end = len(data)
        while f.tell() < file_end:
            try:
                yield self._read_record(f)
            except CorruptTES3RecordError as exc:
                log.warning("Stopping TES3 walk for %s after corrupt record: %s", self.plugin_path, exc)
                return

    def _read_plugin_bytes(self) -> bytes:
        size = self.plugin_path.stat().st_size
        with self.plugin_path.open("rb") as stream:
            if size > MMAP_THRESHOLD_BYTES:
                with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                    return bytes(mapped)
            return stream.read()

    def _read_record(self, f: BinaryIO) -> TES3Record:
        header_offset = f.tell()
        header = f.read(RECORD_HEADER_SIZE)
        if len(header) < RECORD_HEADER_SIZE:
            raise CorruptTES3RecordError(f"short record header at offset {header_offset}")
        sig_raw, data_size, _unused, flags = struct.unpack("<4sIII", header)
        sig = _decode_signature(sig_raw)
        raw_data = f.read(data_size)
        if len(raw_data) < data_size:
            raise CorruptTES3RecordError(f"record {sig} data truncated at offset {header_offset}")
        subrecords = self._parse_subrecords(raw_data)
        return TES3Record(
            sig=sig,
            flags=flags,
            identity=self._record_identity(subrecords),
            subrecords=subrecords,
            is_deleted=any(subrecord.sig == DELETED_SUBRECORD_SIG for subrecord in subrecords),
        )

    def _parse_subrecords(self, data: bytes) -> list[TES3Subrecord]:
        subrecords: list[TES3Subrecord] = []
        offset = 0
        data_len = len(data)
        while offset + SUBRECORD_HEADER_SIZE <= data_len:
            sig_raw, size = struct.unpack_from("<4sI", data, offset)
            offset += SUBRECORD_HEADER_SIZE
            sig = _decode_signature(sig_raw)
            if offset + size > data_len:
                log.warning("TES3 subrecord %s size exceeds containing record; truncating", sig)
                size = data_len - offset
            payload = data[offset : offset + size]
            offset += size
            subrecords.append(TES3Subrecord(sig=sig, data=payload))
        if offset < data_len:
            log.warning("Ignoring %s trailing TES3 bytes after final subrecord", data_len - offset)
        return subrecords

    def _record_identity(self, subrecords: list[TES3Subrecord]) -> str | None:
        for subrecord in subrecords:
            if subrecord.sig != "NAME":
                continue
            try:
                return _decode_inline_text(subrecord.data, self.encoding_chain)
            except UnicodeDecodeError:
                return None
        return None


def _decode_signature(sig: bytes) -> str:
    return sig.decode("ascii", errors="replace")


def _decode_inline_text(data: bytes, encoding_chain: list[str]) -> str:
    raw = data.rstrip(b"\x00")
    text, _encoding = decode_with_chain(raw, encoding_chain)
    return text


__all__ = ["TES3Record", "TES3Subrecord", "TES3Walker"]
