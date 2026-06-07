"""Coverage check ensuring Simplified Chinese catalogs translate English msgids."""

# TODO(Chunk-B): Keep the i18n coverage stub passing for empty catalogs.

from __future__ import annotations

import sys
from ast import literal_eval
from pathlib import Path

CATALOG_DIR = Path(__file__).resolve().parent


def _po_string_value(line: str) -> str:
    return str(literal_eval(line.split(" ", 1)[1].strip()))


def _read_catalog(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    current_msgid: str | None = None
    current_msgstr: str | None = None
    active: str | None = None

    def flush() -> None:
        nonlocal current_msgid, current_msgstr
        if current_msgid is not None and current_msgid != "":
            entries[current_msgid] = current_msgstr or ""
        current_msgid = None
        current_msgstr = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            current_msgid = _po_string_value(line)
            current_msgstr = ""
            active = "msgid"
            continue
        if line.startswith("msgstr "):
            current_msgstr = _po_string_value(line)
            active = "msgstr"
            continue
        if line.startswith('"') and active == "msgid" and current_msgid is not None:
            current_msgid += str(literal_eval(line))
            continue
        if line.startswith('"') and active == "msgstr" and current_msgstr is not None:
            current_msgstr += str(literal_eval(line))

    flush()
    return entries


def find_missing_translations(
    en_path: Path | None = None,
    zh_cn_path: Path | None = None,
) -> list[str]:
    """Return English msgids that are missing non-empty zh_CN msgstr values."""
    en_catalog = _read_catalog(en_path or CATALOG_DIR / "en.po")
    zh_catalog = _read_catalog(zh_cn_path or CATALOG_DIR / "zh_CN.po")
    return [msgid for msgid in en_catalog if not zh_catalog.get(msgid)]


def main() -> int:
    """Run the coverage check as a script."""
    missing = find_missing_translations()
    if not missing:
        return 0

    print("Missing zh_CN translations:")
    for msgid in missing:
        print(f"- {msgid}")
    return 1


__all__ = ["find_missing_translations", "main"]

if __name__ == "__main__":
    sys.exit(main())
