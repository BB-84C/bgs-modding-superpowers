"""GUI smoke tests for entries tab polish."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk entries GUI tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_entries_detail_pane_uses_vertical_source_dest_split() -> None:
    _need_tk_runtime()

    from bgs_translator.gui.tabs.entries_tab import EntriesTab

    root = tk.Tk()
    try:
        tab = EntriesTab(root, project_root_provider=lambda: None)
        tab.pack(fill="both", expand=True)
        root.update_idletasks()

        assert isinstance(tab._detail_paned, ttk.PanedWindow)
        assert str(tab._detail_paned.cget("orient")) == "vertical"
        assert len(tab._detail_paned.panes()) == 2
        assert str(tab._source_text.cget("wrap")) == "word"
        assert str(tab._dest_text.cget("wrap")) == "word"
    finally:
        root.destroy()
