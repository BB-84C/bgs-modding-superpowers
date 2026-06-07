"""Polish-pass-2 regression tests.

These guard the three issues called out in the user's review of
``beta-final.png``:

1. Every ttk widget class actually styled by the theme has explicit
   ``bordercolor``, ``lightcolor``, and ``darkcolor`` overrides — so
   ttk's default light/dark 3D borders never bleed through.
2. The Windows titlebar tint hook is wired into ``TranslatorApp`` and
   returns the documented attribute-acceptance dict.
3. The nav tree's primary column is wide enough to render ``Logs``
   (and ``Glossary`` / ``Profiles``) without descender truncation.
"""

from __future__ import annotations

import os
from typing import Final

import pytest

# Widget classes the theme MUST style with explicit border colours.
_BORDER_CRITICAL_CLASSES: Final[tuple[str, ...]] = (
    "TFrame",
    "Surface.TFrame",
    "TButton",
    "Accent.TButton",
    "TEntry",
    "TCombobox",
    "TCheckbutton",
    "TNotebook",
    "TNotebook.Tab",
    "Treeview",
    "Treeview.Heading",
    "TPanedwindow",
    "TSeparator",
)

_BORDER_KEYS: Final[tuple[str, ...]] = ("bordercolor", "lightcolor", "darkcolor")


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Polish-pass tests skipped under CI (no Tk runtime guaranteed)")
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_amber_theme_sets_border_colors_on_every_critical_class() -> None:
    _need_tk_runtime()
    import tkinter as tk
    from tkinter import ttk

    from bgs_translator.gui.themes import AMBER_THEME, apply_theme

    root = tk.Tk()
    try:
        apply_theme(root, AMBER_THEME, "Consolas", 11)
        style = ttk.Style(root)
        missing: dict[str, list[str]] = {}
        for cls in _BORDER_CRITICAL_CLASSES:
            absent: list[str] = []
            for key in _BORDER_KEYS:
                value = style.lookup(cls, key)
                # ``style.lookup`` returns '' when no value is configured
                # at any state. The amber theme should set all three.
                if not value:
                    absent.append(key)
            if absent:
                missing[cls] = absent
        assert not missing, f"Border colour keys missing on amber theme: {missing}"
    finally:
        root.destroy()


def test_all_three_themes_set_explicit_border_colors() -> None:
    _need_tk_runtime()
    import tkinter as tk
    from tkinter import ttk

    from bgs_translator.gui.themes import AMBER_THEME, GREEN_THEME, MONO_THEME, apply_theme

    for theme in (AMBER_THEME, GREEN_THEME, MONO_THEME):
        root = tk.Tk()
        try:
            apply_theme(root, theme, "Consolas", 11)
            style = ttk.Style(root)
            # Spot-check a few critical classes per theme.
            for cls in ("TEntry", "TCombobox", "Treeview", "TNotebook"):
                for key in _BORDER_KEYS:
                    assert style.lookup(cls, key), (
                        f"Theme {theme.name!r} missing {key!r} on {cls!r}"
                    )
        finally:
            root.destroy()


def test_titlebar_tint_helper_returns_attribute_map() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.themes import AMBER_THEME
    from bgs_translator.gui.win_chrome import apply_titlebar_tint

    root = tk.Tk()
    try:
        result = apply_titlebar_tint(root, AMBER_THEME)
        # Even on non-Windows the helper returns the full key set so
        # callers can introspect without platform branching.
        assert set(result.keys()) == {"dark_mode", "caption", "text", "border"}
        for value in result.values():
            assert isinstance(value, bool)
    finally:
        root.destroy()


def test_translator_app_exposes_titlebar_tint_attribute() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp()
    try:
        tint = app.titlebar_tint
        assert isinstance(tint, dict)
        assert set(tint.keys()) == {"dark_mode", "caption", "text", "border"}
    finally:
        app.destroy()


def test_nav_tree_column_zero_is_wide_enough_for_logs() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp()
    try:
        app.update_idletasks()
        column = app.nav_tree.column("#0")
        assert isinstance(column, dict)
        width = int(column.get("width", 0))
        minwidth = int(column.get("minwidth", 0))
        assert width >= 200, f"Nav tree '#0' width must be >=200 to fit Logs, got {width}"
        assert minwidth >= 180, (
            f"Nav tree '#0' minwidth must be >=180 to keep Logs visible after resize, "
            f"got {minwidth}"
        )
    finally:
        app.destroy()


def test_amber_scrollbar_is_canvas_subclass() -> None:
    """Custom Canvas-based scrollbar should not inherit ttk.Scrollbar."""

    import tkinter as tk

    from bgs_translator.gui.widgets import AmberScrollbar

    # No Tk root needed for class introspection.
    assert issubclass(AmberScrollbar, tk.Canvas)


def test_amber_scrollbar_set_then_redraw_round_trip() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets import AmberScrollbar

    root = tk.Tk()
    try:
        # Make it visible so winfo_height is non-zero.
        sb = AmberScrollbar(root, orient="vertical")
        sb.pack(side="right", fill="y", expand=True)
        sb.update_idletasks()
        sb.set(0.0, 0.5)
        sb.update_idletasks()
        sb.set("0.3", "0.9")  # tk callers pass strings
        sb.update_idletasks()
        # No exceptions == pass; thumb extents are sane.
        start, end = sb._thumb_extents()
        assert end >= start
    finally:
        root.destroy()
