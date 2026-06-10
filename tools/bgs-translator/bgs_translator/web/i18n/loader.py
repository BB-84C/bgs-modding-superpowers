"""Small gettext helper for browser GUI labels."""

from __future__ import annotations

from functools import lru_cache

_CATALOGS = {
    "zh-cn": {
        "Projects": "项目集",
        "Entries": "条目",
        "Batches": "进度",
        "Prompt": "提示词",
        "Profiles": "AI 设置",
        "Glossary": "专有名词",
        "Logs": "记录",
    },
    "en": {},
}


def gettext(message: str, language: str = "zh-cn") -> str:
    """Return a translated browser GUI label when one exists."""

    return _catalog(language).get(message, message)


@lru_cache(maxsize=4)
def _catalog(language: str) -> dict[str, str]:
    normalized = language.replace("_", "-").casefold()
    return dict(_CATALOGS.get(normalized, _CATALOGS["zh-cn"]))


__all__ = ["gettext"]
