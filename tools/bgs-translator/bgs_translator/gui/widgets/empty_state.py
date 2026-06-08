"""Centered ASCII empty-state glyph for empty content panels.

Replaces the bare empty rectangle that previously read as a "form
control" instead of a "CRT terminal panel". The widget paints a small
Vault-Tec-flavoured ASCII box with a caption inside, centered in
whatever frame it is packed into.

Used by:
- Project tab signature-counts area when no project is loaded.
- Logs tab viewer when today's JSONL log is missing or empty.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Final

from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.themes import get_theme

_BOX_TEMPLATE: Final[str] = (
    "+========================================+\n"
    "|                                        |\n"
    "|    {caption}    |\n"
    "|                                        |\n"
    "|         {sub_line:^22}         |\n"
    "|                                        |\n"
    "+========================================+"
)

def _render_box(caption: str, sub_line: str) -> str:
    """Build the centered ASCII box for the empty state."""

    # Caption is centered inside a 32-wide cell; sub_line in a 22-wide cell.
    caption_cell = f"{caption:^32}"
    return _BOX_TEMPLATE.format(caption=caption_cell, sub_line=sub_line)


class EmptyStatePanel(ttk.Frame):
    """A ttk.Frame containing a centered ASCII vault-tec-style glyph.

    Caller decides whether to show or hide the panel; this widget does
    not own visibility. Pack/grid it on top of an empty content area
    and remove it when the area becomes populated.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        caption: str | None = None,
        sub_line: str | None = None,
        source_caption: str | None = None,
        theme_name: str = "amber",
        font_family: str = "Consolas",
        font_size: int = 11,
    ) -> None:
        super().__init__(master, style="TFrame")
        theme = get_theme(theme_name)
        self._theme_name = theme_name
        resolved_caption = caption or _("[ NO DATA LOADED ]")
        resolved_sub_line = sub_line or _("VAULT-TEC INDUSTRIES")

        self._var = tk.StringVar(value=_render_box(resolved_caption, resolved_sub_line))
        self._caption = resolved_caption
        self._source_caption = source_caption or resolved_caption
        self._sub_line = resolved_sub_line

        self._label = tk.Label(
            self,
            textvariable=self._var,
            font=(font_family, font_size, "bold"),
            background=theme.background,
            foreground=theme.dim,
            justify="center",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            padx=8,
            pady=8,
        )
        # Center the label both horizontally and vertically inside the
        # parent frame.
        self._label.place(relx=0.5, rely=0.5, anchor="center")

    def set_caption(self, caption: str, sub_line: str | None = None) -> None:
        """Update the empty-state caption + optional sub-line."""

        self._caption = caption
        self._source_caption = caption
        if sub_line is not None:
            self._sub_line = sub_line
        self._var.set(_render_box(self._caption, self._sub_line))

    def apply_theme(self, theme_name: str) -> None:
        """Re-pull colors from the named theme."""

        theme = get_theme(theme_name)
        self._theme_name = theme_name
        self._label.configure(background=theme.background, foreground=theme.dim)

    @property
    def caption(self) -> str:
        return self._source_caption


__all__ = ["EmptyStatePanel"]
