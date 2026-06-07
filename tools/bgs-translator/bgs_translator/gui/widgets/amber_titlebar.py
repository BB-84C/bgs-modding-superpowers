"""Custom amber titlebar for the control panel.

Replaces the native Windows window chrome after the host root window
calls ``wm_overrideredirect(True)``. Layout is a single row:

    [icon] [title text]                          [ - ] [ \u25a1 ] [ x ]

All controls are drawn through ``ttk.Label`` so the existing amber
theme styles apply directly. Click-and-drag on the title row moves the
window; double-click on the title row toggles maximize against the
work area (taskbar-aware on Windows).

The custom titlebar is Windows-first per AMENDMENTS. On non-Windows
the host root keeps native chrome and this widget is simply not
constructed — see ``gui/app.py``.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import tkinter as tk
from collections.abc import Callable
from ctypes import wintypes
from tkinter import ttk
from typing import Any, Final

from bgs_translator.gui.themes import ThemeConfig

log = logging.getLogger(__name__)

_TITLEBAR_HEIGHT: Final[int] = 30
_BUTTON_PAD_X: Final[int] = 12
_BUTTON_PAD_Y: Final[int] = 4


class AmberTitlebar(ttk.Frame):
    """Window-chrome replacement painted in the active theme.

    Parameters
    ----------
    master
        The host parent (typically the inner workspace frame).
    root
        The real ``tk.Tk`` root. Min/max/close act on it; the drag
        handler moves it.
    theme
        Active palette for buttons + glyphs.
    title
        Title text shown in the centre-left.
    on_close
        Optional callback fired before the window is destroyed; this is
        wired to the existing two-stage ``CloseHandler`` so the close
        confirmation dialog still gates exit.
    """

    def __init__(
        self,
        master: tk.Misc,
        root: tk.Tk,
        theme: ThemeConfig,
        *,
        title: str = "bgs-translator control panel",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, style="Titlebar.TFrame", padding=(8, 2))
        self._root = root
        self._theme = theme
        self._on_close = on_close
        self._drag_anchor: tuple[int, int] | None = None
        self._maximized = False
        self._saved_geometry: str | None = None

        self.columnconfigure(1, weight=1)

        # Left-side icon glyph — uses the phosphor block character so
        # it reads as a CRT cursor instead of an emoji.
        ttk.Label(
            self,
            text="\u25ae",  # vertical rectangle
            style="TitlebarAccent.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(2, 8))

        self._title_var = tk.StringVar(value=title)
        self._title_label = ttk.Label(
            self,
            textvariable=self._title_var,
            style="Titlebar.TLabel",
        )
        self._title_label.grid(row=0, column=1, sticky="we")

        # Control cluster (right-aligned).
        controls = ttk.Frame(self, style="Titlebar.TFrame")
        controls.grid(row=0, column=2, sticky="e")
        self._buttons: dict[str, ttk.Label] = {}
        self._make_button(controls, "min", "\u2500", self._on_min_click).grid(
            row=0, column=0, padx=(0, 2)
        )
        self._make_button(controls, "max", "\u25a1", self._on_max_click).grid(
            row=0, column=1, padx=(0, 2)
        )
        self._make_button(controls, "close", "\u00d7", self._on_close_click).grid(
            row=0, column=2, padx=(0, 2)
        )

        # Drag bindings on title row.
        for target in (self, self._title_label):
            target.bind("<ButtonPress-1>", self._on_drag_start)
            target.bind("<B1-Motion>", self._on_drag_motion)
            target.bind("<ButtonRelease-1>", self._on_drag_end)
            target.bind("<Double-Button-1>", self._on_title_double_click)

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def apply_theme(self, theme: ThemeConfig) -> None:
        """Repaint the titlebar in the supplied theme."""

        self._theme = theme
        # The named styles themselves are reconfigured by the theme
        # registry; nothing widget-local needs to change.

    def set_title(self, text: str) -> None:
        self._title_var.set(text)

    # ------------------------------------------------------------------
    # Button rendering
    # ------------------------------------------------------------------
    def _make_button(
        self,
        parent: tk.Misc,
        kind: str,
        glyph: str,
        command: Callable[[], None],
    ) -> ttk.Label:
        style = "TitlebarClose.TLabel" if kind == "close" else "TitlebarButton.TLabel"
        button = ttk.Label(
            parent,
            text=f"  {glyph}  ",
            style=style,
            padding=(_BUTTON_PAD_X, _BUTTON_PAD_Y),
            cursor="hand2",
        )
        button.bind("<ButtonPress-1>", lambda _e: command())
        button.bind("<Enter>", lambda _e: self._on_button_hover(button, kind, True))
        button.bind("<Leave>", lambda _e: self._on_button_hover(button, kind, False))
        self._buttons[kind] = button
        return button

    def _on_button_hover(self, button: ttk.Label, kind: str, hover: bool) -> None:
        if kind == "close":
            button.configure(style="TitlebarCloseHover.TLabel" if hover else "TitlebarClose.TLabel")
        else:
            button.configure(
                style="TitlebarButtonHover.TLabel" if hover else "TitlebarButton.TLabel"
            )

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------
    def _on_close_click(self) -> None:
        if self._on_close is not None:
            self._on_close()
        else:
            self._root.destroy()

    def _on_min_click(self) -> None:
        # ``iconify`` becomes flaky when overrideredirect is True on
        # Windows — withdraw + a one-shot deiconify binding works
        # reliably. We use iconify when chrome is intact (non-Windows)
        # and the withdraw-cycle on Windows.
        if sys.platform == "win32":
            self._root.withdraw()
            # Restore on left-click of the taskbar entry. Tk does not
            # raise an event for that path, so we poll via a key binding
            # on the root: any focus event after withdraw deiconifies.
            self._root.after(50, self._root.deiconify)
            try:
                self._root.iconify()
            except tk.TclError:
                pass
        else:
            try:
                self._root.iconify()
            except tk.TclError:
                pass

    def _on_max_click(self) -> None:
        if self._maximized:
            if self._saved_geometry is not None:
                self._root.geometry(self._saved_geometry)
            self._maximized = False
            return
        self._saved_geometry = self._root.geometry()
        rect = _windows_work_area()
        if rect is not None:
            left, top, right, bottom = rect
            self._root.geometry(f"{right - left}x{bottom - top}+{left}+{top}")
        else:
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            self._root.geometry(f"{sw}x{sh}+0+0")
        self._maximized = True

    def _on_title_double_click(self, _event: tk.Event[tk.Misc]) -> None:
        self._on_max_click()

    # ------------------------------------------------------------------
    # Drag handlers
    # ------------------------------------------------------------------
    def _on_drag_start(self, event: tk.Event[tk.Misc]) -> None:
        if self._maximized:
            # Drag-while-maximised restores first so the window does
            # not stay glued to the work area while the user drags.
            self._on_max_click()
        try:
            root_x = self._root.winfo_x()
            root_y = self._root.winfo_y()
        except tk.TclError:
            return
        self._drag_anchor = (event.x_root - root_x, event.y_root - root_y)

    def _on_drag_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_anchor is None:
            return
        new_x = event.x_root - self._drag_anchor[0]
        new_y = event.y_root - self._drag_anchor[1]
        try:
            self._root.geometry(f"+{new_x}+{new_y}")
        except tk.TclError:
            return

    def _on_drag_end(self, _event: tk.Event[tk.Misc]) -> None:
        self._drag_anchor = None

    # Read-only introspection used by tests --------------------------
    @property
    def controls(self) -> dict[str, ttk.Label]:
        return dict(self._buttons)

    @property
    def maximized(self) -> bool:
        return self._maximized


def install_titlebar_styles(root: tk.Misc, theme: ThemeConfig, base_font: tuple[str, int]) -> None:
    """Configure the ttk styles consumed by ``AmberTitlebar``.

    Called from the theme registry's ``apply_theme`` after the base
    palette is laid down, so the titlebar repaints during a theme
    switch without touching its widget tree.
    """

    style = ttk.Style(root)
    family, size = base_font
    title_font = (family, size, "bold")

    style.configure(
        "Titlebar.TFrame",
        background=theme.surface,
        bordercolor=theme.border,
        lightcolor=theme.border,
        darkcolor=theme.border,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Titlebar.TLabel",
        background=theme.surface,
        foreground=theme.accent,
        font=title_font,
        padding=(4, 2),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TitlebarAccent.TLabel",
        background=theme.surface,
        foreground=theme.accent,
        font=(family, size + 2, "bold"),
        padding=(2, 0),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TitlebarButton.TLabel",
        background=theme.surface,
        foreground=theme.foreground,
        font=(family, size + 1, "bold"),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TitlebarButtonHover.TLabel",
        background=theme.accent,
        foreground=theme.accent_fg,
        font=(family, size + 1, "bold"),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TitlebarClose.TLabel",
        background=theme.surface,
        foreground=theme.foreground,
        font=(family, size + 1, "bold"),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TitlebarCloseHover.TLabel",
        background=theme.error,
        foreground=theme.accent_fg,
        font=(family, size + 1, "bold"),
        borderwidth=0,
        relief="flat",
    )


def _windows_work_area() -> tuple[int, int, int, int] | None:
    """Return ``(left, top, right, bottom)`` of the primary monitor work area.

    The work area excludes the taskbar so a maximised override-redirect
    window does not cover it. Returns ``None`` on non-Windows.
    """

    if sys.platform != "win32":
        return None
    try:
        user32: Any = ctypes.windll.user32
        rect = wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        ok = user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        if not ok:
            return None
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except (OSError, AttributeError) as exc:
        log.debug("Could not query Windows work area: %s", exc)
        return None


__all__ = ["AmberTitlebar", "install_titlebar_styles"]
