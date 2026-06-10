"""Translation-unit extraction bridge for TES4-family parser records."""

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol

from bgs_translator.parsers.encoding import DEFAULT_ENCODING_CHAINS, decode_with_chain
from bgs_translator.parsers.strings_io import StringsFile, find_strings_sources, read_strings_source
from bgs_translator.parsers.tes3 import TES3Subrecord, TES3Walker
from bgs_translator.parsers.tes4_family import Record, Subrecord, TES4FamilyWalker, TranslationUnit


@dataclass(frozen=True)
class TranslatableField:
    """Schema entry for one translatable subrecord."""

    subrecord_sig: str
    list_index: int
    multi_value: bool
    byte_budget: int
    notes: str = ""


class GameSchema(Protocol):
    """Protocol for per-game translatable-field schemas."""

    name: str

    def get_translatable_subrecords(self, record_sig: str) -> list[TranslatableField]:
        """Return translatable subrecords for a record signature."""


class UniversalFallbackSchema:
    """D.1 test schema covering cross-game baseline translatable fields."""

    name: str = "Universal"
    _BASELINE: ClassVar[list[TranslatableField]] = [
        TranslatableField("FULL", 0, False, 65520),
        TranslatableField("DESC", 1, False, 65520),
        TranslatableField("NAM1", 2, False, 65520, notes="voice-linked"),
        TranslatableField("RNAM", 0, False, 512),
        TranslatableField("SHRT", 0, False, 65520),
        TranslatableField("ITXT", 0, True, 65520),
        TranslatableField("CNAM", 0, False, 65520),
        TranslatableField("NAME", 0, False, 65520),
        TranslatableField("ICON", 0, False, 65520),
        TranslatableField("MICO", 0, False, 65520),
    ]

    def get_translatable_subrecords(self, record_sig: str) -> list[TranslatableField]:
        """Return baseline fields for all record signatures."""

        return list(self._BASELINE)


UNIVERSAL_FALLBACK_SCHEMA = UniversalFallbackSchema()
LIST_KINDS: dict[int, str] = {0: "STRINGS", 1: "DLSTRINGS", 2: "ILSTRINGS"}


def extract_translation_units(
    plugin_path: Path,
    game: str,
    *,
    schema: GameSchema | None = None,
) -> Iterator[TranslationUnit]:
    """Walk ``plugin_path``, apply ``schema``, and yield translation units."""

    active_schema = schema or UNIVERSAL_FALLBACK_SCHEMA
    encoding_chain = DEFAULT_ENCODING_CHAINS.get(game, ["utf-8", "cp1252"])
    strings_files = _load_strings_files(plugin_path, encoding_chain, game=game)
    walker = TES4FamilyWalker(
        plugin_path,
        encoding_chain=encoding_chain,
        strings_files=strings_files,
    )

    for record in walker.walk():
        fields = active_schema.get_translatable_subrecords(record.sig)
        if not fields:
            continue
        edid = _record_edid(record, encoding_chain)
        counts = Counter(field.subrecord_sig for field in fields if field.multi_value)
        matching_counts = Counter(
            subrecord.sig for subrecord in record.subrecords if subrecord.sig in counts
        )
        seen_multi: Counter[str] = Counter()
        for subrecord in record.subrecords:
            for field in fields:
                if subrecord.sig != field.subrecord_sig:
                    continue
                source, strid = _extract_source(
                    subrecord,
                    field,
                    encoding_chain,
                    bool(walker.header and walker.header.is_localized),
                    strings_files,
                )
                if source is None or source == "":
                    continue
                index_n = seen_multi[subrecord.sig] if field.multi_value else 0
                index_max = max(matching_counts[subrecord.sig] - 1, 0) if field.multi_value else 0
                if field.multi_value:
                    seen_multi[subrecord.sig] += 1
                yield TranslationUnit(
                    plugin=plugin_path.name,
                    formid=record.formid,
                    formid_sanitized=record.formid & 0x00FFFFFF,
                    edid=edid,
                    signature=record.sig,
                    field=field.subrecord_sig,
                    index_n=index_n,
                    index_max=index_max,
                    source=source,
                    list_index=field.list_index,
                    strid=strid,
                )


def extract_tes3_translation_units(
    plugin_path: Path,
    schema: GameSchema,
) -> Iterator[TranslationUnit]:
    """Walk a Morrowind plugin via ``TES3Walker`` and yield inline translation units."""

    encoding_chain = DEFAULT_ENCODING_CHAINS.get(schema.name, DEFAULT_ENCODING_CHAINS["Morrowind"])
    walker = TES3Walker(plugin_path, encoding_chain=encoding_chain)
    for record in walker.walk():
        if record.sig == "TES3" or record.is_deleted:
            continue
        fields = schema.get_translatable_subrecords(record.sig)
        if not fields:
            continue
        for subrecord in record.subrecords:
            for field in fields:
                if subrecord.sig != field.subrecord_sig:
                    continue
                source = _extract_tes3_source(subrecord, encoding_chain)
                if source is None or source == "":
                    continue
                yield TranslationUnit(
                    plugin=plugin_path.name,
                    formid=0,
                    formid_sanitized=0,
                    edid=record.identity,
                    signature=record.sig,
                    field=field.subrecord_sig,
                    source=source,
                    list_index=0,
                    strid=0,
                )


def _load_strings_files(
    plugin_path: Path,
    encoding_chain: list[str],
    *,
    game: str | None = None,
) -> dict[str, StringsFile]:
    loaded: dict[str, StringsFile] = {}
    for list_kind, source in find_strings_sources(plugin_path, game=game).items():
        loaded[list_kind] = read_strings_source(source, encoding_chain)
    return loaded


def _record_edid(record: Record, encoding_chain: list[str]) -> str | None:
    for subrecord in record.subrecords:
        if subrecord.sig == "EDID":
            try:
                return _decode_inline(subrecord.data, encoding_chain)
            except UnicodeDecodeError:
                return None
    return None


def _extract_source(
    subrecord: Subrecord,
    field: TranslatableField,
    encoding_chain: list[str],
    localized: bool,
    strings_files: dict[str, StringsFile],
) -> tuple[str | None, int]:
    if localized and field.list_index in LIST_KINDS:
        if len(subrecord.data) < 4:
            return None, 0
        strid = struct.unpack_from("<I", subrecord.data, 0)[0]
        strings_file = strings_files.get(LIST_KINDS[field.list_index])
        if strings_file is None:
            return None, strid
        return strings_file.entries.get(strid), strid
    try:
        return _decode_inline(subrecord.data, encoding_chain), 0
    except UnicodeDecodeError:
        return None, 0


def _extract_tes3_source(subrecord: TES3Subrecord, encoding_chain: list[str]) -> str | None:
    try:
        return _decode_inline(subrecord.data.rstrip(b"\x00"), encoding_chain)
    except UnicodeDecodeError:
        return None


def _decode_inline(data: bytes, encoding_chain: list[str]) -> str:
    raw = data.split(b"\x00", 1)[0]
    text, _encoding = decode_with_chain(raw, encoding_chain)
    return text


__all__ = [
    "UNIVERSAL_FALLBACK_SCHEMA",
    "GameSchema",
    "TranslatableField",
    "UniversalFallbackSchema",
    "extract_tes3_translation_units",
    "extract_translation_units",
]
