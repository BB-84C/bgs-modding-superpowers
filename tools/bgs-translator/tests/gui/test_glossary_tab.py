"""GUI smoke tests for glossary tab polish."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk glossary GUI tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_glossary_add_button_state_tracks_scope(tmp_path: Path) -> None:
    _need_tk_runtime()

    from bgs_translator.gui.tabs.glossary_tab import GlossaryTab

    root = tk.Tk()
    try:
        tab = GlossaryTab(root, kb_root=tmp_path / "kb", user_packs_root=tmp_path / "user-packs")
        tab.pack(fill="both", expand=True)
        root.update_idletasks()

        for scope in ("vanilla", "mod"):
            tab.scope_var.set(scope)
            tab.refresh()
            assert str(tab.add_button.cget("state")) == "disabled"
            assert "Manual [Add] is disabled" in tab._empty_state.caption

        for scope in ("player", "do_not_translate"):
            tab.scope_var.set(scope)
            tab.refresh()
            assert str(tab.add_button.cget("state")) == "normal"
            assert "Click [Add]" in tab._empty_state.caption
    finally:
        root.destroy()
