"""Green classic-phosphor Tk theme stub.

TODO(Chunk-L.2): refine surface tint and selection contrast against the
Treeview heading bar; verify against the spec screenshots once they
land in /docs/plans/translator-tool/.
"""

from __future__ import annotations

from bgs_translator.gui.themes._base import ThemeConfig

THEME = ThemeConfig(
    name="green",
    background="#001a00",
    foreground="#33ff33",
    accent="#00cc44",
    accent_fg="#001a00",
    surface="#002a00",
    border="#005a00",
    dim="#229922",
    warn="#aaff66",
    error="#ff5544",
    ok="#aaffaa",
)

__all__ = ["THEME"]
