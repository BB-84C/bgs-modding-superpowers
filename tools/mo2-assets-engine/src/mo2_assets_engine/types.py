"""Core dataclasses and enums for mo2-assets-engine.

Names mirror the conflict buckets in MO2's internal
`ModInfoWithConflictInfo::doConflictCheck()`
(see src/modinfowithconflictinfo.cpp in modorganizer2/modorganizer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class FileEntryKind(StrEnum):
    LOOSE = "loose"
    ARCHIVED = "archived"


class ArchiveKind(StrEnum):
    BA2_GENERAL = "ba2-general"
    BA2_DX10 = "ba2-dx10"
    BSA_V104 = "bsa-v104"
    BSA_V105 = "bsa-v105"


class ConflictBucket(StrEnum):
    NO_CONFLICT = "no-conflict"
    LOOSE_OVERWRITES_LOOSE = "loose-overwrites-loose"
    LOOSE_OVERWRITTEN_BY_LOOSE = "loose-overwritten-by-loose"
    LOOSE_OVERWRITES_ARCHIVE = "loose-overwrites-archive"
    ARCHIVE_OVERWRITTEN_BY_LOOSE = "archive-overwritten-by-loose"
    ARCHIVE_OVERWRITES_ARCHIVE = "archive-overwrites-archive"
    ARCHIVE_OVERWRITTEN_BY_ARCHIVE = "archive-overwritten-by-archive"


@dataclass(frozen=True)
class ArchiveEntry:
    name: str
    kind: ArchiveKind
    load_order: int


@dataclass(frozen=True)
class FileEntry:
    relative_path: str
    kind: FileEntryKind
    owner_mod: str
    archive: ArchiveEntry | None


@dataclass(frozen=True)
class Mod:
    name: str
    priority: int
    enabled: bool
    root: Path


@dataclass(frozen=True)
class ResolvedWinner:
    relative_path: str
    winner: FileEntry
    losers: list[FileEntry] = field(default_factory=list)
    bucket: ConflictBucket = ConflictBucket.NO_CONFLICT


@dataclass(frozen=True)
class ConflictReport:
    """Per-mod conflict summary mirroring the 3-section MO2 Conflicts tab."""

    mod: Mod
    kept: list[ResolvedWinner]
    overwritten: list[ResolvedWinner]
    no_conflict: list[FileEntry]
