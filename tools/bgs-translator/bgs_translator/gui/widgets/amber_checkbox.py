"""Canvas-painted amber checkbox.

ttk's Checkbutton indicator on Windows is a tiny native rectangle that
ignores most palette options — even after the polish-pass-2 layout
overrides a small white square keeps bleeding through. This widget
draws the indicator from scratch through ``tk.Canvas`` and pairs it
with a ttk label so the caption stays bound to the active theme.

API mirrors ``ttk.Checkbutton``:

- ``cb.value`` returns the current state as a ``bool``.
- Setting ``cb.value = True/False`` updates the indicator + variable.
- ``<<CheckboxToggled>>`` is generated after every user click, so the
  caller can listen via ``cb.bind("<<CheckboxToggled>>", handler)``.
- ``command=`` is also supported for parity with ttk.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Final

from bgs_translator.gui.themes import get_theme

_BOX_SIZE: Final[int] = 16
_BOX_PAD: Final[int] = 3


class AmberCheckbox(ttk.Frame):
    """Composite frame: Canvas indicator + ttk.Label caption."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str = "",
        initial: bool = False,
        command: Callable[[], None] | None = None,
        theme_name: str = "amber",
    ) -> None:
        super().__init__(master, style="TFrame", padding=(0, 2))
        theme = get_theme(theme_name)
        self._theme_name = theme_name
        self._command = command
        self._value = tk.BooleanVar(value=bool(initial))
        self._bg = theme.background
        self._surface = theme.surface
        self._accent = theme.accent
        self._border = theme.border
        self._dim = theme.dim
        self._fg = theme.foreground

        # Indicator canvas.
        self._canvas = tk.Canvas(
            self,
            width=_BOX_SIZE,
            height=_BOX_SIZE,
            background=theme.background,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            cursor="hand2",
            takefocus=True,
        )
        self._canvas.pack(side="left", padx=(0, 6))

        # Caption.
        self._label = ttk.Label(self, text=text, style="TLabel", cursor="hand2")
        self._label.pack(side="left", fill="x", expand=True)

        # Bindings: both the canvas and the caption toggle the value.
        for widget in (self, self._canvas, self._label):
            widget.bind("<ButtonPress-1>", self._on_click)
            widget.bind("<KeyPress-space>", self._on_click)

        self._canvas.bind("<FocusIn>", lambda _e: self._redraw(hover=True))
        self._canvas.bind("<FocusOut>", lambda _e: self._redraw(hover=False))
        for widget in (self, self._canvas, self._label):
            widget.bind("<Enter>", lambda _e: self._redraw(hover=True))
            widget.bind("<Leave>", lambda _e: self._redraw(hover=False))

        self._redraw()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def value(self) -> bool:
        return bool(self._value.get())

    @value.setter
    def value(self, val: bool) -> None:
        self._value.set(bool(val))
        self._redraw()

    @property
    def variable(self) -> tk.BooleanVar:
        return self._value

    def configure_text(self, text: str) -> None:
        self._label.configure(text=text)

    def apply_theme(self, theme_name: str) -> None:
        """Re-pull colors from the named theme. Idempotent."""

        theme = get_theme(theme_name)
        self._theme_name = theme_name
        self._bg = theme.background
        self._surface = theme.surface
        self._accent = theme.accent
        self._border = theme.border
        self._dim = theme.dim
        self._fg = theme.foreground
        self._canvas.configure(background=theme.background)
        self._redraw()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def _redraw(self, *, hover: bool = False) -> None:
        self._canvas.delete("all")
        outline = self._accent if hover else self._dim
        # Outer box.
        self._canvas.create_rectangle(
            1,
            1,
            _BOX_SIZE - 1,
            _BOX_SIZE - 1,
            outline=outline,
            width=1,
            fill=self._surface,
        )
        if self._value.get():
            # Filled inner block — phosphor checkbox glyph.
            self._canvas.create_rectangle(
                _BOX_PAD + 1,
                _BOX_PAD + 1,
                _BOX_SIZE - _BOX_PAD - 1,
                _BOX_SIZE - _BOX_PAD - 1,
                outline="",
                fill=self._accent,
            )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _on_click(self, _event: tk.Event[tk.Misc]) -> None:
        self._value.set(not self._value.get())
        self._redraw()
        try:
            self.event_generate("<<CheckboxToggled>>", when="tail")
        except tk.TclError:
            pass
        if self._command is not None:
            try:
                self._command()
            except Exception:
                pass


__all__ = ["AmberCheckbox"]
