"""Keyboard shortcuts from PRD §1.5."""

from __future__ import annotations

import os

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk shortcut tests skipped under CI")
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_ctrl_3_selects_third_notebook_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    _need_tk_runtime()
    from bgs_translator.gui.app import TranslatorApp

    selected: list[int] = []
    app = TranslatorApp()
    try:
        monkeypatch.setattr(app._notebook, "select", lambda index: selected.append(int(index)))
        app._select_tab_by_index(2)
        assert selected == [2]
    finally:
        app.destroy()


def test_ctrl_b_toggles_nav_pane_visibility() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp()
    try:
        app.update_idletasks()
        assert app._nav_visible is True
        assert len(app._paned.panes()) == 2

        app._toggle_nav_pane()
        app.update_idletasks()
        assert app._nav_visible is False
        assert len(app._paned.panes()) == 1

        app._toggle_nav_pane()
        app.update_idletasks()
        assert app._nav_visible is True
        assert len(app._paned.panes()) == 2
    finally:
        app.destroy()
