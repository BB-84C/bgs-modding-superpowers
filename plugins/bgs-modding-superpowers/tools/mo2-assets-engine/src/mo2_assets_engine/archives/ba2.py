"""BA2 archive reader for filename enumeration.

Supports GNRL (general files) and DX10 (texture) directory shapes for BA2
versions 1 (Fallout 4), 2 (Starfield), and 8 (FO76 / Starfield update).
Does NOT decompress members; this reader is purpose-built for conflict
resolution which only needs the file-path list.

Wire format reference:
  https://en.uesp.net/wiki/Fallout_4_Mod:Archive_File_Format
  https://starfieldwiki.net/wiki/Modding:Archive_File_Format

Lifted and generalized from
`tools/bgs-translator/bgs_translator/parsers/strings_io.py:179-244`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO


class BA2Kind(StrEnum):
    GNRL = "GNRL"
    DX10 = "DX10"


_HEADER_SIZE = 24
_STARFIELD_EXTRA_HEADER_SIZE = 8
_GNRL_ENTRY_SIZE = 36
_DX10_TEX_HEADER_SIZE = 24
_DX10_CHUNK_HEADER_SIZE = 24
_SUPPORTED_VERSIONS = {1, 2, 8}


@dataclass(frozen=True)
class BA2Member:
    name: str


@dataclass(frozen=True)
class BA2Archive:
    path: Path
    kind: BA2Kind
    version: int
    members: list[BA2Member]

    def list_member_names(self) -> list[str]:
        return [m.name for m in self.members]

    @classmethod
    def open(cls, path: Path) -> BA2Archive:
        with path.open("rb") as stream:
            header = stream.read(_HEADER_SIZE)
            if len(header) < _HEADER_SIZE:
                raise ValueError(f"BA2 header too short: {path}")
            magic, version, archive_type, file_count, name_table_offset = struct.unpack(
                "<4sI4sIQ", header
            )
            if magic != b"BTDX":
                raise ValueError(f"Not a BA2 archive: {path}")
            if version not in _SUPPORTED_VERSIONS:
                raise ValueError(f"Unsupported BA2 version {version}: {path}")
            if version == 2:
                # Starfield BA2 v2 adds 8 bytes of extra header before the file table.
                stream.read(_STARFIELD_EXTRA_HEADER_SIZE)

            if archive_type == b"GNRL":
                kind = BA2Kind.GNRL
                stream.seek(_GNRL_ENTRY_SIZE * file_count, 1)
            elif archive_type == b"DX10":
                kind = BA2Kind.DX10
                _skip_dx10_file_records(stream, file_count)
            else:
                raise ValueError(
                    f"Unsupported BA2 archive type {archive_type!r}: {path}"
                )

            stream.seek(name_table_offset)
            members = [BA2Member(name=_read_name(stream)) for _ in range(file_count)]

        return cls(path=path, kind=kind, version=version, members=members)


def _skip_dx10_file_records(stream: BinaryIO, file_count: int) -> None:
    for _ in range(file_count):
        tex_header = stream.read(_DX10_TEX_HEADER_SIZE)
        if len(tex_header) < _DX10_TEX_HEADER_SIZE:
            raise ValueError("BA2 DX10 texture header truncated")
        # Layout: name_hash(I) ext(I) dir_hash(I) unk8(B) num_chunks(B)
        # chunk_header_size(H) height(H) width(H) num_mips(B) format(B)
        # is_cubemap(B) tile_mode(B). num_chunks is at byte offset 13.
        num_chunks = tex_header[13]
        stream.seek(_DX10_CHUNK_HEADER_SIZE * num_chunks, 1)


def _read_name(stream: BinaryIO) -> str:
    raw_length = stream.read(2)
    if len(raw_length) < 2:
        return ""
    (length,) = struct.unpack("<H", raw_length)
    name = stream.read(length).decode("utf-8", errors="replace")
    return name.replace("\\", "/").lower()
