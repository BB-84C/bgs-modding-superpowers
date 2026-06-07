"""Tk theme registry for the control panel.

Each theme module exports a ``ThemeConfig`` dataclass instance named
``THEME``. The registry resolves a theme by name and applies it through
``ttk.Style`` against a Tk root.
"""

from __future__ import annotations

from typing import Final

from bgs_translator.gui.themes._base import ThemeConfig, apply_theme
from bgs_translator.gui.themes.amber import THEME as AMBER_THEME
from bgs_translator.gui.themes.green import THEME as GREEN_THEME
from bgs_translator.gui.themes.mono import THEME as MONO_THEME

_THEMES: Final[dict[str, ThemeConfig]] = {
    AMBER_THEME.name: AMBER_THEME,
    GREEN_THEME.name: GREEN_THEME,
    MONO_THEME.name: MONO_THEME,
}


def list_themes() -> list[str]:
    """Return the registered theme names in display order."""

    return list(_THEMES.keys())


def get_theme(name: str) -> ThemeConfig:
    """Look up a theme by name, falling back to ``amber`` on miss."""

    return _THEMES.get(name, AMBER_THEME)


__all__ = [
    "AMBER_THEME",
    "GREEN_THEME",
    "MONO_THEME",
    "ThemeConfig",
    "apply_theme",
    "get_theme",
    "list_themes",
]
