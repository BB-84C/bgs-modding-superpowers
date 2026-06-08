"""Tests for the batch-monitor sparkline widget."""

from __future__ import annotations

from collections import deque

import pytest


def _need_tk_runtime() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_sparkline_update_rolls_buffer_and_renders_blocks() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets.sparkline import Sparkline

    root = tk.Tk()
    try:
        values: deque[float] = deque([0.1, 0.5, 1.0, 0.3], maxlen=4)
        sparkline = Sparkline(root, values=values)
        sparkline.update_value(0.7)

        assert list(sparkline.values) == [0.5, 1.0, 0.3, 0.7]
        assert sparkline.render_text() == "▄█▁▆"
        assert len(sparkline.find_all()) == 1
    finally:
        root.destroy()
