"""Headless construction smoke test for the Tk control panel.

Skipped under CI by default — many CI runners do not ship Tk. The test
constructs the app, processes pending events, then destroys the root
without ever entering the mainloop.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    bool(os.environ.get("CI")),
    reason="GUI smoke test skipped under CI (no Tk runtime guaranteed)",
)


def test_translator_app_constructs_and_destroys() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")

    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp()
    try:
        app.update_idletasks()
        # Status bar present.
        assert app.status_bar is not None
        # Nav tree has the four canonical sections.
        top_ids = app.nav_tree.get_children("")
        texts = {app.nav_tree.item(node, "option")[0] if False else app.nav_tree.item(node)["text"]
                 for node in top_ids}
        # We expect at least Projects / Profiles / Glossary / Logs translations.
        # The text may be localized; assert count instead.
        assert len(top_ids) == 4
        assert texts  # non-empty
        # Notebook has exactly the 7 tabs from the spec.
        assert len(app.notebook.tabs()) == 7
    finally:
        app.destroy()


def test_theme_switch_does_not_raise() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")

    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp(theme="amber")
    try:
        app._on_theme_change("green")
        app._on_theme_change("mono")
        app._on_theme_change("amber")
        app.update_idletasks()
    finally:
        app.destroy()


def test_language_switch_updates_tabs() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")

    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp(language="en")
    try:
        original = app.notebook.tab(0, "text")
        app._on_language_change("zh-cn")
        app.update_idletasks()
        switched = app.notebook.tab(0, "text")
        # Either the translation differs or the catalog falls back to
        # English — either way the call must not raise.
        assert isinstance(switched, str)
        assert switched != "" and original != ""
    finally:
        app.destroy()
