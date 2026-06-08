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


# ---------------------------------------------------------------------
# Polish pass 3 — strip native chrome, custom titlebar + checkbox
# ---------------------------------------------------------------------


def test_translator_app_strips_native_chrome_on_windows() -> None:
    """``wm_overrideredirect(True)`` must be active on win32/linux."""

    _need_tk_runtime()
    import sys

    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp()
    try:
        if sys.platform in ("win32", "linux"):
            assert app.chrome_stripped is True, (
                "TranslatorApp must call overrideredirect(True) on win32 + linux"
            )
            assert bool(app.overrideredirect()) is True
            assert app.titlebar is not None, (
                "AmberTitlebar must be mounted when native chrome is stripped"
            )
        else:
            # macOS: chrome left intact deliberately.
            assert app.chrome_stripped is False
            assert app.titlebar is None
    finally:
        app.destroy()


def test_amber_titlebar_has_min_max_close_buttons() -> None:
    _need_tk_runtime()
    import sys

    from bgs_translator.gui.app import TranslatorApp

    if sys.platform not in ("win32", "linux"):
        import pytest

        pytest.skip("Custom titlebar is Windows/Linux-first")

    app = TranslatorApp()
    try:
        titlebar = app.titlebar
        assert titlebar is not None
        controls = titlebar.controls
        assert set(controls.keys()) == {"min", "max", "close"}
        # Each control widget should render a non-empty caption.
        for kind, widget in controls.items():
            text = str(widget.cget("text")).strip()
            assert text, f"{kind!r} titlebar button has no glyph"
    finally:
        app.destroy()


def test_amber_titlebar_drag_handler_moves_root() -> None:
    """Synthesizing the drag bindings should update the root geometry."""

    _need_tk_runtime()
    import sys
    import tkinter as tk

    from bgs_translator.gui.app import TranslatorApp

    if sys.platform not in ("win32", "linux"):
        import pytest

        pytest.skip("Custom titlebar is Windows/Linux-first")

    app = TranslatorApp()
    try:
        app.update_idletasks()
        titlebar = app.titlebar
        assert titlebar is not None
        start_x = app.winfo_x()
        start_y = app.winfo_y()

        # Fabricate press + motion events. We cannot use event_generate
        # for x_root / y_root reliably across platforms, so we drive
        # the handlers directly.
        press = tk.Event()
        press.x_root = start_x + 50
        press.y_root = start_y + 5
        titlebar._on_drag_start(press)

        motion = tk.Event()
        motion.x_root = start_x + 200
        motion.y_root = start_y + 150
        titlebar._on_drag_motion(motion)
        app.update_idletasks()

        # Geometry should reflect the delta: new origin == event_root - anchor.
        new_x = app.winfo_x()
        new_y = app.winfo_y()
        assert new_x != start_x or new_y != start_y, (
            "Drag handler did not move the root window"
        )

        titlebar._on_drag_end(tk.Event())
    finally:
        app.destroy()


def test_amber_checkbox_toggles_value() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets import AmberCheckbox

    root = tk.Tk()
    try:
        cb = AmberCheckbox(root, text="Always preview", initial=False)
        cb.pack()
        cb.update_idletasks()
        assert cb.value is False
        cb.value = True
        assert cb.value is True
        # Setter is idempotent.
        cb.value = True
        assert cb.value is True
    finally:
        root.destroy()


def test_amber_checkbox_emits_virtual_event_on_click() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets import AmberCheckbox

    root = tk.Tk()
    try:
        cb = AmberCheckbox(root, text="Always preview", initial=False)
        cb.pack()
        cb.update_idletasks()
        toggled: list[bool] = []
        cb.bind("<<CheckboxToggled>>", lambda _e: toggled.append(cb.value))
        cb._on_click(tk.Event())
        # ``update_idletasks`` only drains idle work; virtual events
        # queued with ``when="tail"`` need the full event-loop pump.
        cb.update()
        assert toggled == [True]
        cb._on_click(tk.Event())
        cb.update()
        assert toggled == [True, False]
    finally:
        root.destroy()


def test_project_tab_uses_amber_checkbox() -> None:
    """The Project tab's preview toggle must be the new AmberCheckbox."""

    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.tabs import ProjectTab
    from bgs_translator.gui.themes import AMBER_THEME, apply_theme
    from bgs_translator.gui.widgets import AmberCheckbox

    root = tk.Tk()
    try:
        apply_theme(root, AMBER_THEME, "Consolas", 11)
        tab = ProjectTab(root)
        tab.pack()
        tab.update_idletasks()
        # The tab should hold a reference to the new widget.
        assert isinstance(tab._preview_checkbox, AmberCheckbox)
        # And the old ttk.Checkbutton attribute (_preview_var) must be gone.
        assert not hasattr(tab, "_preview_var")
    finally:
        root.destroy()


def test_app_outer_frame_paints_accent_border() -> None:
    """The outer frame around the workspace must render the accent colour."""

    _need_tk_runtime()
    from bgs_translator.gui.app import TranslatorApp
    from bgs_translator.gui.themes import AMBER_THEME

    app = TranslatorApp()
    try:
        app.update_idletasks()
        outer_bg = str(app._outer.cget("background")).lower()
        assert outer_bg == AMBER_THEME.accent.lower(), (
            f"Outer accent border expected {AMBER_THEME.accent!r}, got {outer_bg!r}"
        )
        # The workspace inside should be the regular background.
        workspace_bg = str(app._workspace.cget("background")).lower()
        assert workspace_bg == AMBER_THEME.background.lower()
    finally:
        app.destroy()


# ---------------------------------------------------------------------
# Polish pass 4 — scrollbar track+thumb, empty-state glyph, bigger
# titlebar buttons
# ---------------------------------------------------------------------


def test_amber_scrollbar_has_distinct_track_and_thumb_items() -> None:
    """Track + thumb canvas items must both exist after polish pass 4."""

    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets import AmberScrollbar

    root = tk.Tk()
    try:
        sb = AmberScrollbar(root, orient="vertical")
        sb.pack(side="right", fill="y", expand=True)
        sb.update_idletasks()
        # Track + thumb + two end caps == 4 canvas items.
        items = sb.find_all()
        assert len(items) >= 3, f"Expected track + thumb + caps, got {len(items)} items"
        # Track and thumb must use different fills (track is rail, thumb is grip).
        track_fill = str(sb.itemcget(sb._track_id, "fill")).lower()
        thumb_fill = str(sb.itemcget(sb._thumb_id, "fill")).lower()
        assert track_fill != thumb_fill, (
            f"Track and thumb must have distinct fill colours, both = {track_fill!r}"
        )
        # Thumb has a visible outline so it reads as a discrete grip.
        thumb_outline = str(sb.itemcget(sb._thumb_id, "outline")).lower()
        assert thumb_outline, "Thumb must have a non-empty outline colour"
    finally:
        root.destroy()


def test_amber_scrollbar_hover_brightens_thumb() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets import AmberScrollbar

    root = tk.Tk()
    try:
        sb = AmberScrollbar(root, orient="vertical")
        sb.pack(side="right", fill="y", expand=True)
        sb.update_idletasks()
        rest_fill = str(sb.itemcget(sb._thumb_id, "fill")).lower()
        sb._on_hover(True)
        hover_fill = str(sb.itemcget(sb._thumb_id, "fill")).lower()
        assert rest_fill != hover_fill, "Hover should switch the thumb fill colour"
        sb._on_hover(False)
        back_fill = str(sb.itemcget(sb._thumb_id, "fill")).lower()
        assert back_fill == rest_fill, "Leaving hover should restore the rest fill"
    finally:
        root.destroy()


def test_empty_state_panel_renders_caption_and_sub_line() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.widgets import EmptyStatePanel

    root = tk.Tk()
    try:
        panel = EmptyStatePanel(
            root, caption="[ TEST CAPTION ]", sub_line="TEST SUB"
        )
        panel.pack(fill="both", expand=True)
        panel.update_idletasks()
        # The caption + sub appear in the StringVar's value.
        text = panel._var.get()
        assert "[ TEST CAPTION ]" in text
        assert "TEST SUB" in text
        # Reachable through property.
        assert panel.caption == "[ TEST CAPTION ]"
        # Setter updates the rendered text.
        panel.set_caption("[ OTHER ]", "OTHER SUB")
        text2 = panel._var.get()
        assert "[ OTHER ]" in text2
        assert "OTHER SUB" in text2
    finally:
        root.destroy()


def test_project_tab_mounts_empty_state_when_no_project() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.tabs import ProjectTab
    from bgs_translator.gui.themes import AMBER_THEME, apply_theme
    from bgs_translator.gui.widgets import EmptyStatePanel

    root = tk.Tk()
    try:
        apply_theme(root, AMBER_THEME, "Consolas", 11)
        tab = ProjectTab(root)
        tab.pack(fill="both", expand=True)
        tab.update_idletasks()
        assert isinstance(tab._empty_state, EmptyStatePanel)
        assert "NO PROJECT LOADED" in tab._empty_state.caption
    finally:
        root.destroy()


def test_logs_tab_mounts_empty_state_when_no_log_file() -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.tabs import LogsTab
    from bgs_translator.gui.themes import AMBER_THEME, apply_theme
    from bgs_translator.gui.widgets import EmptyStatePanel

    root = tk.Tk()
    try:
        apply_theme(root, AMBER_THEME, "Consolas", 11)
        tab = LogsTab(root)
        tab.pack(fill="both", expand=True)
        tab.update_idletasks()
        assert isinstance(tab._empty_state, EmptyStatePanel)
        assert "NO LOGS RECORDED" in tab._empty_state.caption
    finally:
        root.destroy()


def test_amber_titlebar_buttons_have_non_zero_padding() -> None:
    _need_tk_runtime()
    import sys

    from bgs_translator.gui.app import TranslatorApp

    if sys.platform not in ("win32", "linux"):
        import pytest

        pytest.skip("Custom titlebar is Windows/Linux-first")

    app = TranslatorApp()
    try:
        app.update_idletasks()
        titlebar = app.titlebar
        assert titlebar is not None
        for kind, button in titlebar.controls.items():
            padding_value = button.cget("padding")
            # ttk returns a tuple-or-list; coerce to ints and check both axes.
            if isinstance(padding_value, (tuple, list)):
                px = int(str(padding_value[0]))
                py = int(str(padding_value[1])) if len(padding_value) > 1 else px
            else:
                px = py = int(str(padding_value))
            assert px >= 8, f"{kind!r} button padx={px} too small for a click target"
            assert py >= 4, f"{kind!r} button pady={py} too small for a click target"
    finally:
        app.destroy()
