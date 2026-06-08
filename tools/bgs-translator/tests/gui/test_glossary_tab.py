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


def test_glossary_add_dialog_labels_helpers_and_scope_label(tmp_path: Path) -> None:
    _need_tk_runtime()

    from bgs_translator.gui.tabs.glossary_tab import GlossaryEntryDialog

    root = tk.Tk()
    try:
        dialog = GlossaryEntryDialog(
            root,
            scope="player",
            kb_root=tmp_path / "kb",
            user_packs_root=tmp_path / "user-packs",
        )
        root.update_idletasks()

        all_labels = [
            str(widget.cget("text"))
            for widget in dialog.winfo_children()[0].winfo_children()
            if isinstance(widget, tk.Widget) and "text" in widget.keys()
        ]

        assert "source:" in all_labels
        assert "Term as it appears in source language (e.g. 'Constellation')" in all_labels
        assert "source_lang:" in all_labels
        assert "BCP-47 source code (e.g. 'en')" in all_labels
        assert "scope:" in all_labels
        assert "player" in all_labels
        assert not any(label == "source_aliases:" for label in all_labels)
        assert "aliases:" in all_labels
    finally:
        for child in root.winfo_children():
            child.destroy()
        root.destroy()
