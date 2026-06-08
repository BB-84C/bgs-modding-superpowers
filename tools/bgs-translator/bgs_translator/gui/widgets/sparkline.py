"""Unicode-block sparkline widget for the batch monitor."""

from __future__ import annotations

import math
import tkinter as tk
from collections import deque
from collections.abc import Iterable
from typing import Final

from bgs_translator.gui.themes import get_theme

_BLOCKS: Final[str] = "▁▂▃▄▅▆▇█"


class Sparkline(tk.Canvas):
    """Small Canvas that renders a deque of floats as Unicode block text."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        values: deque[float] | None = None,
        maxlen: int = 30,
        theme_name: str = "amber",
        width: int = 220,
        height: int = 30,
    ) -> None:
        theme = get_theme(theme_name)
        super().__init__(
            master,
            width=width,
            height=height,
            background=theme.background,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
        )
        self.values: deque[float] = values if values is not None else deque(maxlen=maxlen)
        self._theme_name = theme_name
        self._text_id = self.create_text(
            0,
            height // 2,
            anchor="w",
            text=self.render_text(),
            fill=theme.foreground,
            font=("Consolas", 12, "bold"),
        )
        self.bind("<Configure>", lambda _event: self._redraw())

    def update_value(self, value: float) -> None:
        """Append one value and repaint."""

        self.values.append(float(value))
        self._redraw()

    def set_values(self, values: Iterable[float]) -> None:
        """Replace all values while preserving the existing maxlen."""

        self.values.clear()
        for value in values:
            self.values.append(float(value))
        self._redraw()

    def render_text(self) -> str:
        """Return the current Unicode-block sparkline string."""

        if not self.values:
            return ""
        low = min(self.values)
        high = max(self.values)
        if math.isclose(high, low):
            return _BLOCKS[0] * len(self.values)
        span = high - low
        chars: list[str] = []
        for value in self.values:
            fraction = (value - low) / span
            index = 0 if fraction <= 0 else min(len(_BLOCKS) - 1, math.ceil(fraction * len(_BLOCKS)))
            chars.append(_BLOCKS[index])
        return "".join(chars)

    def apply_theme(self, theme_name: str) -> None:
        """Apply a theme palette."""

        theme = get_theme(theme_name)
        self._theme_name = theme_name
        self.configure(background=theme.background)
        self.itemconfigure(self._text_id, fill=theme.foreground)

    def _redraw(self) -> None:
        self.itemconfigure(self._text_id, text=self.render_text())
        self.coords(self._text_id, 0, max(1, int(self.winfo_height()) // 2))


__all__ = ["Sparkline"]
