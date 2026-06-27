"""Read BGS archive lists from game INI files."""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path

_ARCHIVE_KEYS = {
    "sresourcearchive2list",
    "sresourceindexfilelist",
    "sresourcearchivelist",
    "sresourcearchivelist2",
}


@dataclass(frozen=True)
class IniArchiveLists:
    explicit_archives: list[str] = field(default_factory=list)


def read_archive_lists(ini_paths: list[Path]) -> IniArchiveLists:
    """Read all provided INIs and union archive names from [Archive]."""
    explicit: list[str] = []
    seen: set[str] = set()
    for ini_path in ini_paths:
        if not ini_path.exists():
            continue
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        parser.optionxform = str.lower  # type: ignore[method-assign]
        parser.read(ini_path, encoding="utf-8-sig")
        if not parser.has_section("Archive"):
            continue
        for key, value in parser.items("Archive"):
            if key.lower() not in _ARCHIVE_KEYS:
                continue
            for archive_name in _split_archive_list(value):
                normalized = archive_name.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                explicit.append(archive_name)
    return IniArchiveLists(explicit_archives=explicit)


def _split_archive_list(value: str) -> list[str]:
    return [part.strip().strip('"') for part in value.split(",") if part.strip()]
