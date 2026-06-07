"""i18n setup for the Tk control panel.

Provides a tiny gettext-style translation lookup that reads the bundled
en.po and zh_CN.po catalogs at import time. We avoid building .mo files
at install time so the catalogs stay text-only and easy to diff.
"""

from __future__ import annotations

from ast import literal_eval
from pathlib import Path
from typing import Final

CATALOG_DIR: Final[Path] = Path(__file__).resolve().parent

_LANG_TO_FILE: Final[dict[str, str]] = {
    "en": "en.po",
    "zh-cn": "zh_CN.po",
    "zh_cn": "zh_CN.po",
    "zh_CN": "zh_CN.po",
}


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


class Translator:
    """A tiny gettext-shaped translator backed by .po catalogs."""

    def __init__(self, language: str = "en") -> None:
        self._language = "en"
        self._catalog: dict[str, str] = {}
        self.set_language(language)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        normalized = language.strip()
        filename = _LANG_TO_FILE.get(normalized, "en.po")
        catalog_path = CATALOG_DIR / filename
        if not catalog_path.exists():
            self._catalog = {}
            self._language = "en"
            return
        self._catalog = _read_catalog(catalog_path)
        self._language = normalized

    def gettext(self, msgid: str) -> str:
        """Return the translation for ``msgid`` or the original on miss."""

        translated = self._catalog.get(msgid)
        if translated:
            return translated
        return msgid


_DEFAULT = Translator("en")


def gettext(msgid: str) -> str:
    """Module-level convenience wrapper that uses the default translator."""

    return _DEFAULT.gettext(msgid)


def set_default_language(language: str) -> None:
    """Switch the language used by the module-level ``gettext`` helper."""

    _DEFAULT.set_language(language)


__all__ = [
    "CATALOG_DIR",
    "Translator",
    "gettext",
    "set_default_language",
]
