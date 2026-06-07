"""Monochrome high-contrast Tk theme stub.

TODO(Chunk-L.2): verify against high-contrast accessibility targets;
spec calls for a minimal, no-color rendering of the same widget set.
"""

from __future__ import annotations

from bgs_translator.gui.themes._base import ThemeConfig

THEME = ThemeConfig(
    name="mono",
    background="#000000",
    foreground="#e0e0e0",
    accent="#a0a0a0",
    accent_fg="#000000",
    surface="#101010",
    border="#404040",
    dim="#707070",
    warn="#d0d0d0",
    error="#ffffff",
    ok="#c0c0c0",
)

__all__ = ["THEME"]
