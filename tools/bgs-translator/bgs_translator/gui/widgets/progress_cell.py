"""Text-based progress cell using Unicode block characters.

The cell renders an n-of-m progress along with a small ascii bar
matching the spec aesthetic, e.g. ``40/40 [..\u2593\u2592\u2591]``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Final

_FILLED: Final[str] = "\u2593"  # ▓
_HALF: Final[str] = "\u2592"  # ▒
_EMPTY: Final[str] = "\u2591"  # ░


def render_progress_bar(done: int, total: int, *, width: int = 8) -> str:
    """Return an ascii progress bar of fixed ``width`` block characters."""

    if total <= 0:
        return _EMPTY * width
    ratio = min(1.0, max(0.0, done / total))
    filled = int(ratio * width)
    remainder = ratio * width - filled
    half = 1 if remainder >= 0.5 and filled < width else 0
    empty = width - filled - half
    return _FILLED * filled + _HALF * half + _EMPTY * empty


class ProgressCell(ttk.Frame):
    """Composite label showing ``done/total [bar]``."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        done: int = 0,
        total: int = 0,
        width: int = 8,
    ) -> None:
        super().__init__(master)
        self._width = width
        self._done = done
        self._total = total
        self._var = tk.StringVar()
        self._label = ttk.Label(self, textvariable=self._var, style="Status.TLabel")
        self._label.pack(side="left")
        self._refresh()

    def set_progress(self, done: int, total: int) -> None:
        self._done = max(0, done)
        self._total = max(0, total)
        self._refresh()

    def _refresh(self) -> None:
        bar = render_progress_bar(self._done, self._total, width=self._width)
        self._var.set(f"{self._done}/{self._total} [{bar}]")


__all__ = ["ProgressCell", "render_progress_bar"]
