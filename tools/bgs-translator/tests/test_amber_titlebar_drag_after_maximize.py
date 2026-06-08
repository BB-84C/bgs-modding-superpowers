"""Maximized titlebar drag must restore without cursor-anchor jumps."""

from __future__ import annotations

import os
import tkinter as tk

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk titlebar tests skipped under CI")
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_drag_start_from_maximized_restores_with_proportional_cursor_anchor() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.themes import AMBER_THEME
    from bgs_translator.gui.widgets.amber_titlebar import AmberTitlebar

    root = tk.Tk()
    try:
        root.geometry("1200x800+0+0")
        titlebar = AmberTitlebar(root, root, AMBER_THEME)
        titlebar.pack(fill="x")
        root.update_idletasks()

        titlebar._saved_geometry = "600x400+100+100"
        titlebar._maximized = True

        event = tk.Event()
        event.x_root = 300
        event.y_root = 50
        titlebar._on_drag_start(event)
        root.update_idletasks()

        assert titlebar.maximized is False
        assert root.winfo_width() == 600
        assert root.winfo_height() == 400
        # Cursor was 25% across and 6.25% down in the maximized window;
        # it should retain those fractions in the restored geometry.
        assert root.winfo_x() == 150
        assert root.winfo_y() == 25
        assert titlebar._drag_anchor == (150, 25)
    finally:
        root.destroy()
