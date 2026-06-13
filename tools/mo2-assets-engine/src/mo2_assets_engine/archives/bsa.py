"""BSA archive reader for filename enumeration.

Supports BSA v104 (Skyrim LE / FO3 / FNV) and v105 (Skyrim SE / AE / VR).
Does NOT decompress members; this reader is purpose-built for conflict
resolution which only needs the file-path list.

Wire format reference:
  https://en.uesp.net/wiki/Skyrim_Mod:Archive_File_Format

The v105 file-record `offset` is documented as
`folder_offset + total_file_name_length`, so when reading we subtract
`total_file_name_length` to recover the position of the per-folder
name+records block.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import BinaryIO


class BSAVersion(IntEnum):
    V104 = 104
    V105 = 105


_HEADER_SIZE = 36
_FOLDER_RECORD_SIZE_V104 = 16
_FOLDER_RECORD_SIZE_V105 = 24
_FILE_RECORD_SIZE = 16

_FLAG_FOLDER_NAMES = 0b0001
_FLAG_FILE_NAMES = 0b0010


@dataclass(frozen=True)
class BSAMember:
    name: str


@dataclass(frozen=True)
class BSAArchive:
    path: Path
    version: BSAVersion
    members: list[BSAMember]

    def list_member_names(self) -> list[str]:
        return [m.name for m in self.members]

    @classmethod
    def open(cls, path: Path) -> BSAArchive:
        with path.open("rb") as stream:
            header = stream.read(_HEADER_SIZE)
            if len(header) < _HEADER_SIZE:
                raise ValueError(f"BSA header too short: {path}")
            (
                magic,
                version_value,
                _folder_offset,
                archive_flags,
                folder_count,
                file_count,
                total_folder_name_length,
                total_file_name_length,
                _file_flags,
            ) = struct.unpack("<4sIIIIIIII", header)

            if magic != b"BSA\x00":
                raise ValueError(f"Not a BSA archive: {path}")
            try:
                version = BSAVersion(version_value)
            except ValueError as exc:
                raise ValueError(f"Unsupported BSA version {version_value}: {path}") from exc

            if not (
                archive_flags & _FLAG_FOLDER_NAMES and archive_flags & _FLAG_FILE_NAMES
            ):
                raise ValueError(
                    f"BSA at {path} omits folder/file names; enumeration not supported"
                )

            folder_record_size = (
                _FOLDER_RECORD_SIZE_V105
                if version is BSAVersion.V105
                else _FOLDER_RECORD_SIZE_V104
            )
            folder_records = [
                _read_folder_record(stream, version) for _ in range(folder_count)
            ]

            # Walk per-folder name + file-record blocks. The folder name in
            # this block is the source of truth for the folder path.
            folder_names: list[str] = []
            file_owner_folder_index: list[int] = []
            for folder_index, (folder_file_count, raw_offset) in enumerate(folder_records):
                target_offset = (
                    raw_offset - total_file_name_length
                    if version is BSAVersion.V105
                    else raw_offset
                )
                stream.seek(target_offset)
                folder_name = _read_bstring(stream)
                folder_names.append(folder_name)
                # Skip the file records; we use the trailing names block.
                stream.seek(_FILE_RECORD_SIZE * folder_file_count, 1)
                file_owner_folder_index.extend([folder_index] * folder_file_count)

            # Read trailing file-name block.
            file_names_start = (
                _HEADER_SIZE
                + folder_record_size * folder_count
                + total_folder_name_length
                + folder_count  # one length byte per BString
                + _FILE_RECORD_SIZE * file_count
            )
            stream.seek(file_names_start)
            full_names: list[str] = []
            for index in range(file_count):
                fname = _read_cstring(stream)
                folder_index = file_owner_folder_index[index]
                owner_folder_name = folder_names[folder_index]
                full_path = (
                    f"{owner_folder_name}/{fname}".replace("\\", "/").lower()
                )
                full_names.append(full_path)

            members = [BSAMember(name=name) for name in full_names]

        return cls(path=path, version=version, members=members)


def _read_folder_record(stream: BinaryIO, version: BSAVersion) -> tuple[int, int]:
    """Return (file_count_in_folder, offset). Skips name_hash + padding."""
    if version is BSAVersion.V105:
        raw = stream.read(_FOLDER_RECORD_SIZE_V105)
        _name_hash, file_count, _pad, offset = struct.unpack("<QIIQ", raw)
        return file_count, offset
    raw = stream.read(_FOLDER_RECORD_SIZE_V104)
    _name_hash, file_count, offset = struct.unpack("<QII", raw)
    return file_count, offset


def _read_bstring(stream: BinaryIO) -> str:
    """Read a BString: 1-byte length (includes null) + name + null."""
    (length,) = struct.unpack("<B", stream.read(1))
    raw = stream.read(length)
    return raw.rstrip(b"\x00").decode("ascii", errors="replace").replace("\\", "/").lower()


def _read_cstring(stream: BinaryIO) -> str:
    buf = bytearray()
    while True:
        byte = stream.read(1)
        if not byte or byte == b"\x00":
            return buf.decode("ascii", errors="replace").lower()
        buf += byte
