"""Localized STRINGS, DLSTRINGS, and ILSTRINGS IO ownership."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal, cast

from bgs_translator.parsers.encoding import decode_with_chain

StringsListKind = Literal["STRINGS", "DLSTRINGS", "ILSTRINGS"]
STRING_LIST_KINDS: tuple[StringsListKind, ...] = ("STRINGS", "DLSTRINGS", "ILSTRINGS")


@dataclass
class StringsFile:
    """Decoded localized string table."""

    path: Path
    list_kind: StringsListKind
    encoding: str
    entries: dict[int, str]


@dataclass(frozen=True)
class StringsSource:
    """A loose or archive-backed STRINGS-family file source."""

    path: Path
    list_kind: StringsListKind
    archive_path: Path | None = None
    member_path: str | None = None


_ARCHIVE_PATTERNS_BY_GAME: dict[str, tuple[str, ...]] = {
    "Fallout4": (
        "{stem} - main.ba2",
        "{stem} - interface.ba2",
        "{stem}.ba2",
    ),
    "Fallout76": (
        "{stem} - main.ba2",
        "{stem} - Localization.ba2",
        "{stem} - interface.ba2",
        "{stem}.ba2",
        "seventysix - localization.ba2",
    ),
    "Starfield": (
        "{stem} - main.ba2",
        "{stem} - main02.ba2",
        "{stem} - Localization.ba2",
        "{stem} - interface.ba2",
        "{stem}.ba2",
    ),
}


def find_strings_files(
    plugin_path: Path, target_lang_code: str = "english"
) -> dict[StringsListKind, Path]:
    """Locate sibling localized STRINGS-family files for ``plugin_path``."""

    strings_dir = plugin_path.parent / "Strings"
    stem = plugin_path.stem
    found: dict[StringsListKind, Path] = {}
    for list_kind in STRING_LIST_KINDS:
        candidate = strings_dir / f"{stem}_{target_lang_code}.{list_kind}"
        if candidate.exists():
            found[list_kind] = candidate
    return found


def find_strings_sources(
    plugin_path: Path,
    target_lang_code: str = "english",
    *,
    game: str | None = None,
) -> dict[StringsListKind, StringsSource]:
    """Locate loose or BA2-backed localized STRINGS-family sources."""

    language_candidates = _language_slug_candidates(target_lang_code)
    found: dict[StringsListKind, StringsSource] = {}
    for language_slug in language_candidates:
        for kind, path in find_strings_files(plugin_path, language_slug).items():
            found.setdefault(kind, StringsSource(path=path, list_kind=kind))
    missing = [kind for kind in STRING_LIST_KINDS if kind not in found]
    if missing:
        found.update(
            _find_archive_strings_sources(plugin_path, language_candidates, missing, game=game)
        )
    return found


def _kind_from_suffix(path: Path) -> StringsListKind:
    suffix = path.suffix.upper().lstrip(".")
    if suffix in {"STRINGS", "DLSTRINGS", "ILSTRINGS"}:
        return cast(StringsListKind, suffix)
    raise ValueError(f"Unsupported STRINGS-family suffix: {path.suffix}")


def _decode_entries(raw_entries: dict[int, bytes], encoding_chain: list[str]) -> tuple[dict[int, str], str]:
    decoded: dict[int, str] = {}
    encoding_used: str | None = None
    for string_id, raw in raw_entries.items():
        text, encoding = decode_with_chain(raw, encoding_chain)
        if encoding_used is None:
            encoding_used = encoding
        elif encoding != encoding_used:
            encoding_used = "mixed"
        decoded[string_id] = text
    return decoded, encoding_used or (encoding_chain[0] if encoding_chain else "")


def read_strings_file(path: Path, encoding_chain: list[str]) -> StringsFile:
    """Parse a Bethesda STRINGS, DLSTRINGS, or ILSTRINGS file."""

    return read_strings_bytes(path, path.read_bytes(), encoding_chain)


def read_strings_source(source: StringsSource, encoding_chain: list[str]) -> StringsFile:
    """Parse a loose or archive-backed localized string table."""

    if source.archive_path and source.member_path:
        data = BA2Archive(source.archive_path).read_member(source.member_path)
        display = Path(f"{source.archive_path}!{source.member_path}")
        return read_strings_bytes(display, data, encoding_chain)
    return read_strings_file(source.path, encoding_chain)


def read_strings_bytes(path: Path, data: bytes, encoding_chain: list[str]) -> StringsFile:
    """Parse STRINGS-family bytes using ``path`` for diagnostics and list-kind detection."""

    if len(data) < 8:
        raise ValueError(f"STRINGS file too short: {path}")
    count, data_size = struct.unpack_from("<II", data, 0)
    directory_start = 8
    directory_end = directory_start + count * 8
    data_start = directory_end
    data_end = data_start + data_size
    if directory_end > len(data) or data_end > len(data):
        raise ValueError(f"STRINGS directory exceeds file size: {path}")

    list_kind = _kind_from_suffix(path)
    block = data[data_start:data_end]
    raw_entries: dict[int, bytes] = {}
    for index in range(count):
        string_id, offset = struct.unpack_from("<II", data, directory_start + index * 8)
        if offset >= len(block):
            raw_entries[string_id] = b""
            continue
        if list_kind == "STRINGS":
            terminator = block.find(b"\x00", offset)
            end = len(block) if terminator == -1 else terminator
            raw_entries[string_id] = block[offset:end]
            continue
        if offset + 4 > len(block):
            raw_entries[string_id] = b""
            continue
        length = struct.unpack_from("<I", block, offset)[0]
        start = offset + 4
        end = min(start + length, len(block))
        raw = block[start:end]
        raw_entries[string_id] = raw[:-1] if raw.endswith(b"\x00") else raw

    entries, encoding = _decode_entries(raw_entries, encoding_chain)
    return StringsFile(path=path, list_kind=list_kind, encoding=encoding, entries=entries)


@dataclass(frozen=True)
class _BA2Entry:
    name: str
    offset: int
    packed_size: int
    size: int


class BA2Archive:
    """Minimal BA2 GNRL reader for localized string resources."""

    _HEADER_SIZE = 24
    _STARFIELD_EXTRA_HEADER_SIZE = 8
    _ENTRY_SIZE = 36

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, _BA2Entry] | None = None

    def read_member(self, member_path: str) -> bytes:
        entries = self._read_directory()
        normalized = _normalize_archive_member(member_path)
        entry = entries.get(normalized)
        if entry is None:
            raise FileNotFoundError(f"{member_path} not found in {self.path}")
        with self.path.open("rb") as stream:
            stream.seek(entry.offset)
            raw = stream.read(entry.packed_size or entry.size)
        if entry.packed_size:
            return zlib.decompress(raw)
        return raw

    def has_member(self, member_path: str) -> bool:
        return _normalize_archive_member(member_path) in self._read_directory()

    def _read_directory(self) -> dict[str, _BA2Entry]:
        if self._entries is not None:
            return self._entries
        with self.path.open("rb") as stream:
            header = stream.read(self._HEADER_SIZE)
            if len(header) < self._HEADER_SIZE:
                raise ValueError(f"BA2 header too short: {self.path}")
            magic, version, archive_type, file_count, name_table_offset = struct.unpack(
                "<4sI4sIQ", header
            )
            if magic != b"BTDX":
                raise ValueError(f"Not a BA2 archive: {self.path}")
            if archive_type != b"GNRL":
                self._entries = {}
                return self._entries
            if version == 2:
                stream.read(self._STARFIELD_EXTRA_HEADER_SIZE)
            elif version not in {1, 8}:
                raise ValueError(f"Unsupported BA2 version {version}: {self.path}")

            raw_entries = [stream.read(self._ENTRY_SIZE) for _ in range(file_count)]
            stream.seek(name_table_offset)
            names = [_read_ba2_name(stream) for _ in range(file_count)]

        entries: dict[str, _BA2Entry] = {}
        for name, raw in zip(names, raw_entries, strict=True):
            if len(raw) < self._ENTRY_SIZE:
                continue
            _name_hash, _ext, _dir_hash, _unknown, offset, packed_size, size, _sentinel = (
                struct.unpack("<IIIIQIII", raw)
            )
            entries[_normalize_archive_member(name)] = _BA2Entry(
                name=name,
                offset=offset,
                packed_size=packed_size,
                size=size,
            )
        self._entries = entries
        return entries


def _read_ba2_name(stream: BinaryIO) -> str:
    raw_length = stream.read(2)
    if len(raw_length) < 2:
        return ""
    length = struct.unpack("<H", raw_length)[0]
    return stream.read(length).decode("utf-8", errors="replace")


def _find_archive_strings_sources(
    plugin_path: Path,
    target_lang_codes: list[str],
    missing: list[StringsListKind],
    *,
    game: str | None,
) -> dict[StringsListKind, StringsSource]:
    found: dict[StringsListKind, StringsSource] = {}
    stem = plugin_path.stem
    needed = set(missing)
    members = [
        (kind, f"strings/{stem}_{target_lang_code}.{kind.lower()}")
        for target_lang_code in target_lang_codes
        for kind in STRING_LIST_KINDS
        if kind in needed
    ]
    for archive_path in _candidate_archives(plugin_path, game=game):
        try:
            archive = BA2Archive(archive_path)
            for kind, member_path in members:
                if kind in found:
                    continue
                if archive.has_member(member_path):
                    found[kind] = StringsSource(
                        path=Path(f"{archive_path}!{member_path}"),
                        list_kind=kind,
                        archive_path=archive_path,
                        member_path=member_path,
                    )
            if needed.issubset(found.keys()):
                break
        except (OSError, ValueError, zlib.error):
            continue
    return found


def _candidate_archives(plugin_path: Path, *, game: str | None) -> list[Path]:
    available = {path.name.casefold(): path for path in plugin_path.parent.glob("*.ba2")}
    patterns = _ARCHIVE_PATTERNS_BY_GAME.get(game or "", ("{stem} - main.ba2", "{stem}.ba2"))
    candidates: list[Path] = []
    for pattern in patterns:
        candidate = available.get(pattern.format(stem=plugin_path.stem).casefold())
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _normalize_archive_member(path: str) -> str:
    return path.replace("\\", "/").casefold()


def _language_slug_candidates(target_lang_code: str) -> list[str]:
    normalized = target_lang_code.casefold().replace("-", "").replace("_", "")
    aliases = {
        "en": ["english", "en"],
        "english": ["english", "en"],
        "zhcn": ["chinese", "zhhans", "zh-hans", "zh_cn"],
        "chinese": ["chinese", "zhhans", "zh-hans", "zh_cn"],
        "zhhans": ["zhhans", "chinese", "zh-hans", "zh_cn"],
    }
    candidates = aliases.get(normalized, [target_lang_code.casefold()])
    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


__all__ = [
    "BA2Archive",
    "StringsFile",
    "StringsListKind",
    "StringsSource",
    "find_strings_files",
    "find_strings_sources",
    "read_strings_bytes",
    "read_strings_file",
    "read_strings_source",
]
