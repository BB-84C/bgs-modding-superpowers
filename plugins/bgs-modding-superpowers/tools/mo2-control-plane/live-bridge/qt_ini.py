r"""Qt QSettings INI array dialect parser.

ModOrganizer.ini [customExecutables] uses Qt's array serialization:
    [customExecutables]
    size=2
    1\title=xEdit
    1\binary=C:/Tools/xEdit/xEdit.exe
    1\arguments=-fo4
    2\title=LOOT

configparser treats backslash keys poorly for this dialect and PyQt6.QSettings
is too heavy for broker-side unit tests. This parser walks the section line by
line and extracts the array fields directly.
"""

from __future__ import annotations

from pathlib import Path


_BOOL_KEYS = {"ownicon", "hide", "toolbar", "minimizeToSystemTray"}


def parse_custom_executables(ini_path: Path) -> list[dict]:
    """Parse Qt QSettings array entries under [customExecutables]."""

    if not ini_path.exists():
        return []

    lines = ini_path.read_text(encoding="utf-8", errors="replace").splitlines()
    in_section = False
    section_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_section:
                break
            if stripped == "[customExecutables]":
                in_section = True
            continue
        if in_section and stripped and "=" in stripped:
            section_lines.append(stripped)

    if not section_lines:
        return []

    flat: dict[str, str] = {}
    for line in section_lines:
        key, _, value = line.partition("=")
        flat[key.strip()] = value

    try:
        size = int(flat.get("size", "0"))
    except ValueError:
        size = 0

    if size == 0:
        return []

    entries: list[dict] = []
    for index in range(1, size + 1):
        index_prefix = f"{index}\\"
        entry: dict = {}
        for key, value in flat.items():
            if not key.startswith(index_prefix):
                continue
            sub_key = key[len(index_prefix) :]
            if sub_key in _BOOL_KEYS:
                entry[sub_key] = value.strip().lower() == "true"
            else:
                entry[sub_key] = value
        if entry.get("title"):
            entries.append(entry)

    return entries
