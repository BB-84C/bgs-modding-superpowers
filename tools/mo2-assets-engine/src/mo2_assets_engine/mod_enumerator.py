"""Enumerate every file a mod contributes (loose + archived).

Returns flat `FileEntry` lists keyed by mod. Used by the conflict resolver
to compute per-file winners.

Hidden-file convention: any subdirectory whose name ends with `.mohidden`
(MO2's hide-this-folder marker) is skipped, including its descendants.

Mod-root metadata exclusion: `meta.ini` at the immediate mod-root level is
MO2 mod metadata, NOT a game asset. MO2's USVFS does not overlay it into
the game directory. We skip it here so every mod's `meta.ini` does not
appear as a phantom conflict against every other mod's `meta.ini`. A
nested `meta.ini` (e.g. inside `Data/`) IS a real asset and is kept.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .archive_order import ArchiveLoadOrder
from .archives.ba2 import BA2Archive, BA2Kind
from .archives.bsa import BSAArchive, BSAVersion
from .types import ArchiveEntry, ArchiveKind, FileEntry, FileEntryKind, Mod


def enumerate_mod_files(*, mod: Mod, archive_order: ArchiveLoadOrder) -> list[FileEntry]:
    entries: list[FileEntry] = []
    if not mod.root.exists():
        return entries
    entries.extend(_enumerate_loose(mod))
    entries.extend(_enumerate_archives(mod, archive_order))
    return entries


def _enumerate_loose(mod: Mod) -> list[FileEntry]:
    out: list[FileEntry] = []
    for path in _walk_visible_files(mod.root, mod_root=mod.root):
        rel = path.relative_to(mod.root).as_posix().lower()
        out.append(
            FileEntry(
                relative_path=rel,
                kind=FileEntryKind.LOOSE,
                owner_mod=mod.name,
                archive=None,
            )
        )
    return out


def _walk_visible_files(current: Path, *, mod_root: Path) -> Iterator[Path]:
    """Walk loose-file content under `current`, applying mod-root filters
    only at the immediate `mod_root` level (not at recursive sub-levels).
    """
    for child in sorted(current.iterdir()):
        if child.is_dir():
            if child.name.lower().endswith(".mohidden"):
                continue
            yield from _walk_visible_files(child, mod_root=mod_root)
        elif child.is_file():
            if child.parent == mod_root:
                suffix = child.suffix.lower()
                # Skip archives at the mod-root level; they are handled separately.
                if suffix in (".bsa", ".ba2"):
                    continue
                # Skip mod-root meta.ini: it's MO2 metadata, not a game asset.
                # USVFS does not overlay it. A nested meta.ini (e.g. under
                # Data/) is kept because some mods ship one as real content.
                if child.name.lower() == "meta.ini":
                    continue
            yield child


def _enumerate_archives(mod: Mod, archive_order: ArchiveLoadOrder) -> list[FileEntry]:
    out: list[FileEntry] = []
    if not mod.root.exists():
        return out
    for child in sorted(mod.root.iterdir()):
        if not child.is_file():
            continue
        suffix = child.suffix.lower()
        if suffix not in (".bsa", ".ba2"):
            continue
        rank = archive_order.rank_of(child.name)
        if rank is None:
            # Unattached archive; not loaded by the engine.
            continue
        out.extend(_enumerate_archive_members(child, rank, mod.name))
    return out


def _enumerate_archive_members(
    archive_path: Path, load_order: int, owner_mod: str
) -> list[FileEntry]:
    suffix = archive_path.suffix.lower()
    if suffix == ".ba2":
        ba2 = BA2Archive.open(archive_path)
        kind = ArchiveKind.BA2_GENERAL if ba2.kind is BA2Kind.GNRL else ArchiveKind.BA2_DX10
        return [
            FileEntry(
                relative_path=name,
                kind=FileEntryKind.ARCHIVED,
                owner_mod=owner_mod,
                archive=ArchiveEntry(name=archive_path.name, kind=kind, load_order=load_order),
            )
            for name in ba2.list_member_names()
        ]
    # .bsa
    bsa = BSAArchive.open(archive_path)
    kind = ArchiveKind.BSA_V105 if bsa.version is BSAVersion.V105 else ArchiveKind.BSA_V104
    return [
        FileEntry(
            relative_path=name,
            kind=FileEntryKind.ARCHIVED,
            owner_mod=owner_mod,
            archive=ArchiveEntry(name=archive_path.name, kind=kind, load_order=load_order),
        )
        for name in bsa.list_member_names()
    ]
