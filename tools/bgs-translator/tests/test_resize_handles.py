"""Regression tests for custom override-redirect resize handles."""

from __future__ import annotations

import os
import tkinter as tk

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk resize-handle tests skipped under CI")
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_resize_hit_test_detects_edges_and_center() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.themes import AMBER_THEME
    from bgs_translator.gui.widgets.resize_handles import ResizeHandles, ResizeZone

    root = tk.Tk()
    try:
        root.geometry("1000x700+20+20")
        outer = tk.Frame(root, width=1000, height=700)
        outer.pack(fill="both", expand=True)
        handles = ResizeHandles(root=root, outer_frame=outer, theme=AMBER_THEME)
        root.update_idletasks()

        assert handles.hit_test(5, 100, 1000, 700) is ResizeZone.WEST
        assert handles.hit_test(5, 5, 1000, 700) is ResizeZone.NORTHWEST
        assert handles.hit_test(500, 500, 1000, 700) is ResizeZone.NONE
    finally:
        root.destroy()


def test_resize_drag_east_changes_width_without_moving_left_edge() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.themes import AMBER_THEME
    from bgs_translator.gui.widgets.resize_handles import ResizeHandles

    root = tk.Tk()
    try:
        root.minsize(1024, 600)
        root.geometry("1100x700+40+50")
        outer = tk.Frame(root, width=1100, height=700)
        outer.pack(fill="both", expand=True)
        handles = ResizeHandles(root=root, outer_frame=outer, theme=AMBER_THEME)
        root.update_idletasks()
        start_x = root.winfo_x()
        start_width = root.winfo_width()

        press = tk.Event()
        press.x = 1098
        press.y = 350
        press.x_root = 1140
        press.y_root = 400
        handles._on_button_press(press)

        motion = tk.Event()
        motion.x_root = 1190
        motion.y_root = 400
        handles._on_drag_motion(motion)
        root.update_idletasks()

        assert root.winfo_x() == start_x
        assert abs(root.winfo_width() - (start_width + 50)) <= 6
    finally:
        root.destroy()


def test_resize_drag_west_clamps_to_min_width_and_preserves_right_edge() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.themes import AMBER_THEME
    from bgs_translator.gui.widgets.resize_handles import ResizeHandles

    root = tk.Tk()
    try:
        root.minsize(1024, 600)
        root.geometry("1100x700+40+50")
        outer = tk.Frame(root, width=1100, height=700)
        outer.pack(fill="both", expand=True)
        handles = ResizeHandles(root=root, outer_frame=outer, theme=AMBER_THEME)
        root.update_idletasks()
        start_x = root.winfo_x()
        start_width = root.winfo_width()
        min_width = root.minsize()[0]

        press = tk.Event()
        press.x = 2
        press.y = 350
        press.x_root = 42
        press.y_root = 400
        handles._on_button_press(press)

        motion = tk.Event()
        motion.x_root = 242
        motion.y_root = 400
        handles._on_drag_motion(motion)
        root.update_idletasks()

        assert root.winfo_width() >= min_width
        assert root.winfo_width() <= start_width
        assert root.winfo_x() >= start_x + start_width - min_width
    finally:
        root.destroy()
