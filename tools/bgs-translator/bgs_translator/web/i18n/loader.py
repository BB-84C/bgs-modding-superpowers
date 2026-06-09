"""Small PO-backed gettext loader for the web panel."""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

_LANGUAGE_FILES = {
    "en": "en.po",
    "zh-cn": "zh_CN.po",
    "zh_CN": "zh_CN.po",
}


def gettext(message: str, language: str = "zh-cn") -> str:
    """Return the translated string from the inherited GUI PO catalogs."""

    return _catalog(language).get(message, message)


@lru_cache(maxsize=4)
def _catalog(language: str) -> dict[str, str]:
    name = _LANGUAGE_FILES.get(language, "zh_CN.po")
    path = Path(__file__).parents[2] / "gui" / "i18n" / name
    if not path.exists():
        return {}
    return _parse_po(path)


def _parse_po(path: Path) -> dict[str, str]:
    catalog: dict[str, str] = {}
    msgid: str | None = None
    msgstr: str | None = None
    active: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if msgid is not None and msgstr is not None:
                catalog[msgid] = msgstr or msgid
            msgid = None
            msgstr = None
            active = None
            continue
        if line.startswith("msgid "):
            if msgid is not None and msgstr is not None:
                catalog[msgid] = msgstr or msgid
            msgid = _po_string(line[6:])
            msgstr = None
            active = "msgid"
            continue
        if line.startswith("msgstr "):
            msgstr = _po_string(line[7:])
            active = "msgstr"
            continue
        if line.startswith('"') and active == "msgid" and msgid is not None:
            msgid += _po_string(line)
            continue
        if line.startswith('"') and active == "msgstr" and msgstr is not None:
            msgstr += _po_string(line)
    if msgid is not None and msgstr is not None:
        catalog[msgid] = msgstr or msgid
    return catalog


def _po_string(value: str) -> str:
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value.strip('"')
    return parsed if isinstance(parsed, str) else ""


__all__ = ["gettext"]
