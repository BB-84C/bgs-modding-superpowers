"""Custom Canvas-based scrollbar that paints itself in the active theme.

``ttk.Scrollbar`` on Windows ignores most ``Style().configure`` palette
keys — the native scrollbar widget bleeds through and looks grey.
``AmberScrollbar`` is a thin Canvas-based replacement that mimics the
two-method protocol used by Tk's scrollables:

- ``scrollbar.set(first, last)`` is called by the scrollable to report
  the visible window.
- The scrollbar calls ``command(*args)`` on drag / click to ask the
  scrollable to scroll. The protocol matches ``Tk.yview`` and
  ``Tk.xview``: e.g. ``("moveto", "0.25")`` or ``("scroll", "1", "units")``.

That keeps it drop-in compatible with ``Treeview.configure(yscrollcommand=)``,
``Text.configure(yscrollcommand=)``, ``Listbox`` etc.

The widget is intentionally minimal — no arrow buttons, just a trough
and a thumb. The aesthetic target is a CRT/Pip-Boy phosphor bar, not
a Windows scrollbar.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Final, Literal

from bgs_translator.gui.themes import get_theme

ScrollCommand = Callable[..., object]
Orientation = Literal["vertical", "horizontal"]

_DEFAULT_THICKNESS: Final[int] = 12
_MIN_THUMB_PX: Final[int] = 24


class AmberScrollbar(tk.Canvas):
    """A Canvas-painted scrollbar in the amber/phosphor palette.

    Parameters
    ----------
    master
        The Tk parent.
    orient
        ``"vertical"`` (default) or ``"horizontal"``.
    command
        Optional callable invoked as ``command(*args)`` whenever the
        scrollbar wants the scrollable to move.
    theme_name
        Theme name used to colour the trough + thumb. Pulled from the
        theme registry; falls back to ``amber`` on miss.
    thickness
        Width (vertical) / height (horizontal) of the bar, in pixels.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        orient: Orientation = "vertical",
        command: ScrollCommand | None = None,
        theme_name: str = "amber",
        thickness: int = _DEFAULT_THICKNESS,
    ) -> None:
        theme = get_theme(theme_name)
        self._orient: Orientation = orient
        self._thickness = thickness
        self._first = 0.0
        self._last = 1.0
        self._command: ScrollCommand | None = command
        self._drag_offset: float | None = None
        self._theme_name = theme_name
        self._trough_color = theme.background
        self._thumb_color = theme.dim
        self._thumb_hover_color = theme.accent
        self._border_color = theme.border

        if orient == "vertical":
            super().__init__(
                master,
                background=theme.background,
                highlightthickness=0,
                borderwidth=0,
                relief="flat",
                takefocus=False,
                width=thickness,
            )
        else:
            super().__init__(
                master,
                background=theme.background,
                highlightthickness=0,
                borderwidth=0,
                relief="flat",
                takefocus=False,
                height=thickness,
            )

        # Trough rectangle (fills the canvas).
        self._trough_id = self.create_rectangle(
            0, 0, 1, 1, fill=self._trough_color, outline=self._border_color, width=1
        )
        # Thumb rectangle.
        self._thumb_id = self.create_rectangle(
            0, 0, 1, 1, fill=self._thumb_color, outline="", width=0
        )

        # Bindings.
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Enter>", lambda _e: self._set_thumb_color(self._thumb_hover_color))
        self.bind("<Leave>", lambda _e: self._set_thumb_color(self._thumb_color))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    # Public API ------------------------------------------------------
    def set(self, first: float | str, last: float | str) -> None:
        """Scrollable callback: report the current visible window."""

        try:
            self._first = max(0.0, min(1.0, float(first)))
            self._last = max(self._first, min(1.0, float(last)))
        except (TypeError, ValueError):
            return
        self._redraw()

    def configure_command(self, command: ScrollCommand | None) -> None:
        """Update or clear the scroll command after construction."""

        self._command = command

    def apply_theme(self, theme_name: str) -> None:
        """Re-pull colors from the named theme. Idempotent."""

        theme = get_theme(theme_name)
        self._theme_name = theme_name
        self._trough_color = theme.background
        self._thumb_color = theme.dim
        self._thumb_hover_color = theme.accent
        self._border_color = theme.border
        self.configure(background=theme.background)
        self.itemconfigure(self._trough_id, fill=self._trough_color, outline=self._border_color)
        self.itemconfigure(self._thumb_id, fill=self._thumb_color)
        self._redraw()

    # Internals -------------------------------------------------------
    def _set_thumb_color(self, color: str) -> None:
        self.itemconfigure(self._thumb_id, fill=color)

    def _thumb_extents(self) -> tuple[int, int]:
        """Return ``(start, end)`` pixel positions for the thumb."""

        size = self._long_dim()
        if size <= 1:
            return (0, 0)
        start = int(self._first * size)
        end = int(self._last * size)
        if end - start < _MIN_THUMB_PX:
            mid = (start + end) // 2
            half = max(_MIN_THUMB_PX // 2, 4)
            start = max(0, mid - half)
            end = min(size, start + _MIN_THUMB_PX)
            if end - start < _MIN_THUMB_PX:
                start = max(0, end - _MIN_THUMB_PX)
        return (start, end)

    def _long_dim(self) -> int:
        if self._orient == "vertical":
            return int(self.winfo_height())
        return int(self.winfo_width())

    def _redraw(self) -> None:
        width = int(self.winfo_width())
        height = int(self.winfo_height())
        if width <= 0 or height <= 0:
            return
        self.coords(self._trough_id, 0, 0, width, height)

        start, end = self._thumb_extents()
        inset = 2
        if self._orient == "vertical":
            self.coords(
                self._thumb_id,
                inset,
                max(0, start),
                width - inset,
                min(height, end),
            )
        else:
            self.coords(
                self._thumb_id,
                max(0, start),
                inset,
                min(width, end),
                height - inset,
            )

    def _event_position_fraction(self, event: tk.Event[tk.Misc]) -> float:
        size = self._long_dim()
        if size <= 0:
            return 0.0
        pos = event.y if self._orient == "vertical" else event.x
        return max(0.0, min(1.0, pos / size))

    def _on_press(self, event: tk.Event[tk.Misc]) -> None:
        start, end = self._thumb_extents()
        pos = event.y if self._orient == "vertical" else event.x
        if start <= pos <= end:
            self._drag_offset = (pos - start) / max(1, self._long_dim())
            return
        # Click outside the thumb: jump-to.
        self._drag_offset = (end - start) / max(1, self._long_dim()) / 2.0
        fraction = self._event_position_fraction(event) - self._drag_offset
        self._invoke_moveto(max(0.0, min(1.0, fraction)))

    def _on_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_offset is None:
            return
        fraction = self._event_position_fraction(event) - self._drag_offset
        self._invoke_moveto(max(0.0, min(1.0, fraction)))

    def _on_release(self, _event: tk.Event[tk.Misc]) -> None:
        self._drag_offset = None

    def _invoke_moveto(self, fraction: float) -> None:
        if self._command is None:
            return
        try:
            self._command("moveto", f"{fraction:.6f}")
        except tk.TclError:
            pass


__all__ = ["AmberScrollbar"]
