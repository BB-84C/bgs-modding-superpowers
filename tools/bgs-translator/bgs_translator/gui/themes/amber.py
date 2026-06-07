"""Amber phosphor Tk theme — Pip-Boy / vintage CRT palette."""

from __future__ import annotations

from bgs_translator.gui.themes._base import ThemeConfig

THEME = ThemeConfig(
    name="amber",
    background="#1a0f00",
    foreground="#ffb000",
    accent="#ff8800",
    accent_fg="#1a0f00",
    surface="#2a1900",
    border="#5a3a00",
    dim="#a07000",
    warn="#ffcc44",
    error="#ff5544",
    ok="#88ff66",
)

__all__ = ["THEME"]
