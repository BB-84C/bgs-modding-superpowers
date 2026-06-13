"""Read MO2 profile state from disk (modlist.txt + plugins.txt).

Offline-first: no MO2 process required. The profile directory is typically
`<MO2_Root>/profiles/<ProfileName>/`. The mods root is typically
`<MO2_Root>/mods/`.

MO2 `modlist.txt` line prefixes:
    +    enabled mod
    -    disabled mod
    *    separator (UI grouping only, not a real mod)
    #    comment

In `modlist.txt`, the TOP of the file is the LAST-applied mod (highest priority).
We assign priorities so that the topmost enabled mod gets the highest integer,
matching MO2's `优先级` column (top of mod list = highest number visible in UI
when sorted that way).

`plugins.txt` uses the BGS asterisk-prefix format: a leading `*` means the
plugin is enabled. Official masters (Skyrim.esm, etc.) do not need a `*`.
See `skills/writing-bgs-load-order/` for the full format reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .types import Mod


@dataclass(frozen=True)
class MO2Profile:
    profile_dir: Path
    mods_root: Path
    enabled_mods: list[Mod] = field(default_factory=list)
    enabled_plugins: list[str] = field(default_factory=list)


def read_profile(*, profile_dir: Path, mods_root: Path) -> MO2Profile:
    enabled_mods = _read_enabled_mods(profile_dir / "modlist.txt", mods_root)
    enabled_plugins = _read_enabled_plugins(profile_dir / "plugins.txt")
    return MO2Profile(
        profile_dir=profile_dir,
        mods_root=mods_root,
        enabled_mods=enabled_mods,
        enabled_plugins=enabled_plugins,
    )


def _read_enabled_mods(modlist_path: Path, mods_root: Path) -> list[Mod]:
    if not modlist_path.exists():
        return []
    names: list[str] = []
    for raw_line in modlist_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        prefix, name = line[:1], line[1:]
        if prefix == "+":
            names.append(name)
        # `-` (disabled) and `*` (separator) are skipped.

    # `names` is in modlist.txt order: top of file first.
    # Top of file = highest priority in MO2's UI.
    total = len(names)
    return [
        Mod(
            name=name,
            priority=total - 1 - index,
            enabled=True,
            root=mods_root / name,
        )
        for index, name in enumerate(names)
    ]


def _read_enabled_plugins(plugins_path: Path) -> list[str]:
    if not plugins_path.exists():
        return []
    enabled: list[str] = []
    for raw_line in plugins_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("*"):
            enabled.append(line[1:])
        # Bare lines without `*` are disabled non-official plugins; skip.
        # Official masters do not appear in this file at all.
    return enabled
