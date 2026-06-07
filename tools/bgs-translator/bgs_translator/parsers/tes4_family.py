"""Shared Oblivion-through-Starfield TES4-family walker ownership."""

from __future__ import annotations

import io
import logging
import mmap
import struct
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from bgs_translator.parsers.strings_io import StringsFile

log = logging.getLogger(__name__)

RECORD_HEADER_SIZE = 24
GRUP_HEADER_SIZE = 24
SUBRECORD_HEADER_SIZE = 6
COMPRESSED_RECORD_FLAG = 0x00040000
DELETED_RECORD_FLAG = 0x20
LOCALIZED_PLUGIN_FLAG = 0x80
ESL_PLUGIN_FLAG = 0x200
MMAP_THRESHOLD_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class Subrecord:
    """Raw subrecord payload after XXXX size resolution."""

    sig: str
    data: bytes


@dataclass(frozen=True)
class Record:
    """TES4-family record with parsed subrecords."""

    sig: str
    formid: int
    flags: int
    form_version: int
    subrecords: list[Subrecord]
    is_compressed: bool

    @property
    def is_deleted(self) -> bool:
        """Return true when the record carries the Deleted flag."""

        return bool(self.flags & DELETED_RECORD_FLAG)


@dataclass
class TES4Header:
    """Parsed content from the TES4 file header record."""

    form_version: int
    flags: int
    is_localized: bool
    is_esl: bool
    masters: list[str]


@dataclass(frozen=True)
class TranslationUnit:
    """One translatable string instance extracted from a plugin."""

    plugin: str
    formid: int
    formid_sanitized: int
    edid: str | None
    signature: str
    field: str
    source: str
    index_n: int = 0
    index_max: int = 0
    list_index: int = 0
    strid: int = 0


class CorruptRecordError(ValueError):
    """Raised when a single record cannot be decoded but walking can continue."""


class TES4FamilyWalker:
    """Read a TES4-family plugin and yield non-header records."""

    def __init__(
        self,
        plugin_path: Path,
        *,
        encoding_chain: list[str] | None = None,
        strings_files: dict[str, StringsFile] | None = None,
    ) -> None:
        self.plugin_path = plugin_path
        self.encoding_chain = encoding_chain or ["utf-8", "cp1252"]
        self.strings_files = strings_files or {}
        self.header: TES4Header | None = None

    def walk(self) -> Iterator[Record]:
        """Open the plugin, parse the TES4 header, and yield contained records."""

        data = self._read_plugin_bytes()
        f = io.BytesIO(data)
        self.header = self._parse_tes4_header(f)
        file_end = len(data)
        while f.tell() < file_end:
            sig = f.read(4)
            if len(sig) < 4:
                break
            f.seek(-4, io.SEEK_CUR)
            if sig == b"GRUP":
                yield from self._walk_grup(f, file_end)
            else:
                try:
                    yield self._read_record(f)
                except CorruptRecordError as exc:
                    log.warning("Skipping corrupt top-level record in %s: %s", self.plugin_path, exc)

    def _read_plugin_bytes(self) -> bytes:
        size = self.plugin_path.stat().st_size
        with self.plugin_path.open("rb") as stream:
            if size > MMAP_THRESHOLD_BYTES:
                with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                    return bytes(mapped)
            return stream.read()

    def _parse_tes4_header(self, f: BinaryIO) -> TES4Header:
        record = self._read_record(f)
        if record.sig != "TES4":
            raise ValueError(f"Expected TES4 header in {self.plugin_path}, found {record.sig}")

        form_version = max(record.form_version, 0)
        masters: list[str] = []
        for subrecord in record.subrecords:
            if subrecord.sig == "HEDR" and len(subrecord.data) >= 10:
                form_version = max(struct.unpack_from("<H", subrecord.data, 8)[0], 0)
            elif subrecord.sig == "MAST":
                masters.append(_decode_ascii_zstring(subrecord.data))
        return TES4Header(
            form_version=form_version,
            flags=record.flags,
            is_localized=bool(record.flags & LOCALIZED_PLUGIN_FLAG),
            is_esl=bool(record.flags & ESL_PLUGIN_FLAG),
            masters=masters,
        )

    def _walk_grup(self, f: BinaryIO, end: int) -> Iterator[Record]:
        start = f.tell()
        header = f.read(GRUP_HEADER_SIZE)
        if len(header) < GRUP_HEADER_SIZE:
            return
        sig, group_size = struct.unpack_from("<4sI", header, 0)
        if sig != b"GRUP":
            f.seek(start)
            try:
                yield self._read_record(f)
            except CorruptRecordError as exc:
                log.warning("Skipping corrupt record in %s: %s", self.plugin_path, exc)
            return
        if group_size < GRUP_HEADER_SIZE:
            log.warning("Skipping malformed GRUP at offset %s in %s", start, self.plugin_path)
            f.seek(min(end, start + GRUP_HEADER_SIZE))
            return

        group_end = min(end, start + group_size)
        while f.tell() < group_end:
            child_sig = f.read(4)
            if len(child_sig) < 4:
                break
            f.seek(-4, io.SEEK_CUR)
            if child_sig == b"GRUP":
                yield from self._walk_grup(f, group_end)
            else:
                try:
                    yield self._read_record(f)
                except CorruptRecordError as exc:
                    log.warning("Skipping corrupt record in %s: %s", self.plugin_path, exc)
        if f.tell() < group_end:
            f.seek(group_end)

    def _read_record(self, f: BinaryIO) -> Record:
        header_offset = f.tell()
        header = f.read(RECORD_HEADER_SIZE)
        if len(header) < RECORD_HEADER_SIZE:
            raise CorruptRecordError(f"short record header at offset {header_offset}")
        sig_raw, data_size, flags, formid, _vc1, form_version, _vc2 = struct.unpack(
            "<4sIII I H H", header
        )
        sig = _decode_signature(sig_raw)
        raw_data = f.read(data_size)
        if len(raw_data) < data_size:
            raise CorruptRecordError(f"record {sig} data truncated at offset {header_offset}")
        try:
            data = self._maybe_decompress(raw_data, flags)
        except zlib.error as exc:
            raise CorruptRecordError(f"record {sig} decompression failed: {exc}") from exc
        return Record(
            sig=sig,
            formid=formid,
            flags=flags,
            form_version=max(form_version, 0),
            subrecords=self._parse_subrecords(data),
            is_compressed=bool(flags & COMPRESSED_RECORD_FLAG),
        )

    def _parse_subrecords(self, data: bytes) -> list[Subrecord]:
        subrecords: list[Subrecord] = []
        offset = 0
        override_size: int | None = None
        data_len = len(data)
        while offset + SUBRECORD_HEADER_SIZE <= data_len:
            sig_raw, size = struct.unpack_from("<4sH", data, offset)
            offset += SUBRECORD_HEADER_SIZE
            sig = _decode_signature(sig_raw)
            actual_size = override_size if override_size is not None else size
            override_size = None
            if offset + actual_size > data_len:
                log.warning("Subrecord %s size exceeds containing record; truncating", sig)
                actual_size = data_len - offset
            payload = data[offset : offset + actual_size]
            offset += actual_size
            if sig == "XXXX":
                if len(payload) == 4:
                    override_size = struct.unpack("<I", payload)[0]
                else:
                    log.warning("Malformed XXXX subrecord with %s bytes", len(payload))
                continue
            subrecords.append(Subrecord(sig=sig, data=payload))
        if offset < data_len:
            log.warning("Ignoring %s trailing bytes after final subrecord", data_len - offset)
        return subrecords

    def _maybe_decompress(self, raw: bytes, flags: int) -> bytes:
        if not flags & COMPRESSED_RECORD_FLAG:
            return raw
        if len(raw) < 4:
            raise zlib.error("compressed record is missing decompressed-size prefix")
        expected_size = struct.unpack_from("<I", raw, 0)[0]
        decompressed = zlib.decompress(raw[4:])
        if len(decompressed) != expected_size:
            log.warning(
                "Compressed record size mismatch in %s: expected %s, got %s",
                self.plugin_path,
                expected_size,
                len(decompressed),
            )
        return decompressed


def _decode_signature(sig: bytes) -> str:
    return sig.decode("ascii", errors="replace")


def _decode_ascii_zstring(data: bytes) -> str:
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace")


__all__ = [
    "Record",
    "Subrecord",
    "TES4FamilyWalker",
    "TES4Header",
    "TranslationUnit",
]
