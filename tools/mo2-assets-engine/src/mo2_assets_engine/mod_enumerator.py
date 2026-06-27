"""Enumerate projected loose files and archive members.

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

from .archives.ba2 import BA2Archive
from .archives.bsa import BSAArchive
from .types import Mod


def enumerate_projected_loose_paths(mod: Mod) -> list[str]:
    """Return a mod's loose files as normalized virtual Data paths."""
    if not mod.root.exists():
        return []
    return [path.relative_to(mod.root).as_posix().lower() for path in _walk_visible_files(mod.root, mod_root=mod.root)]


def enumerate_archive_member_paths(archive_path: Path) -> list[str]:
    suffix = archive_path.suffix.lower()
    if suffix == ".ba2":
        return BA2Archive.open(archive_path).list_member_names()
    if suffix == ".bsa":
        return BSAArchive.open(archive_path).list_member_names()
    return []


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
