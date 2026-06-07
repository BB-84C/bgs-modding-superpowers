"""Theme palette dataclass and Tk style application helpers.

Polish-pass-2 note: clam-theme ttk widgets on Windows still render
visible light/dark 3D edges around Entry, Combobox, Treeview, and
Notebook unless we override their LAYOUT — recolouring is not enough.
This module therefore both ``configure``s the palette AND ``layout``s
the problematic widgets so the only colours visible on screen come
from the theme palette.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, cast


@dataclass(frozen=True)
class ThemeConfig:
    """Palette + style data for a single Tk theme."""

    name: str
    background: str
    foreground: str
    accent: str
    accent_fg: str
    surface: str
    border: str
    dim: str
    warn: str
    error: str
    ok: str


def apply_theme(root: tk.Misc, theme: ThemeConfig, font_family: str, font_size: int) -> None:
    """Apply ``theme`` to ttk styles and Tk's own option database.

    This mutates the shared ttk style; idempotent under repeated calls
    with the same palette. Safe to invoke during a theme switch.
    """

    style = ttk.Style(root)
    try:
        # ``clam`` honours background and foreground configuration on
        # Windows. The default ``vista`` and ``xpnative`` themes ignore
        # most palette options, which is why the phosphor palette would
        # otherwise vanish.
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = theme.background
    fg = theme.foreground
    accent = theme.accent
    accent_fg = theme.accent_fg
    surface = theme.surface
    border = theme.border
    dim = theme.dim

    base_font = (font_family, font_size)
    bold_font = (font_family, font_size, "bold")

    # ------------------------------------------------------------------
    # Tk option database for classic widgets (tk.Frame, tk.Label, ...).
    # ------------------------------------------------------------------
    root.option_add("*background", bg)
    root.option_add("*foreground", fg)
    root.option_add("*Font", base_font)
    root.option_add("*borderWidth", 0)
    root.option_add("*highlightThickness", 0)
    root.option_add("*relief", "flat")

    root.option_add("*Text.background", surface)
    root.option_add("*Text.foreground", fg)
    root.option_add("*Text.insertBackground", accent)
    root.option_add("*Text.selectBackground", accent)
    root.option_add("*Text.selectForeground", accent_fg)
    root.option_add("*Text.borderWidth", 0)
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.highlightThickness", 0)

    root.option_add("*Entry.background", surface)
    root.option_add("*Entry.foreground", fg)
    root.option_add("*Entry.insertBackground", accent)
    root.option_add("*Entry.borderWidth", 0)
    root.option_add("*Entry.relief", "flat")
    root.option_add("*Entry.highlightThickness", 0)

    root.option_add("*Listbox.background", surface)
    root.option_add("*Listbox.foreground", fg)
    root.option_add("*Listbox.selectBackground", accent)
    root.option_add("*Listbox.selectForeground", accent_fg)
    root.option_add("*Listbox.borderWidth", 0)
    root.option_add("*Listbox.relief", "flat")
    root.option_add("*Listbox.highlightThickness", 0)

    root.option_add("*Menu.background", surface)
    root.option_add("*Menu.foreground", fg)
    root.option_add("*Menu.activeBackground", accent)
    root.option_add("*Menu.activeForeground", accent_fg)
    root.option_add("*Menu.borderWidth", 0)
    root.option_add("*Menu.relief", "flat")

    # ------------------------------------------------------------------
    # Layout overrides — strip the native 3D borders that clam draws
    # around Entry, Combobox, Treeview, and the Notebook client area.
    # ------------------------------------------------------------------
    _strip_widget_borders(style)

    # ------------------------------------------------------------------
    # ttk style configuration.
    # ------------------------------------------------------------------
    style.configure(
        ".",
        background=bg,
        foreground=fg,
        font=base_font,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        troughcolor=bg,
        focuscolor=accent,
        relief="flat",
        borderwidth=0,
    )

    style.configure("TFrame", background=bg, bordercolor=border, borderwidth=0, relief="flat")
    style.configure(
        "Surface.TFrame",
        background=surface,
        bordercolor=border,
        borderwidth=0,
        relief="flat",
    )

    for label_style in ("TLabel", "Dim.TLabel", "Accent.TLabel", "Header.TLabel"):
        style.configure(label_style, background=bg, foreground=fg, borderwidth=0, relief="flat")
    style.configure("Accent.TLabel", foreground=accent, font=bold_font)
    style.configure("Dim.TLabel", foreground=dim)
    style.configure("Header.TLabel", foreground=accent, font=bold_font)
    style.configure(
        "Status.TLabel",
        background=surface,
        foreground=fg,
        font=base_font,
        padding=(6, 2),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "StatusDim.TLabel",
        background=surface,
        foreground=dim,
        font=base_font,
        padding=(0, 2),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "StatusAccent.TLabel",
        background=surface,
        foreground=accent,
        font=bold_font,
        padding=(0, 2),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Phosphor.TLabel",
        background=bg,
        foreground=accent,
        font=(font_family, font_size + 1, "bold"),
        borderwidth=0,
        relief="flat",
    )

    style.configure(
        "TButton",
        background=surface,
        foreground=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        focusthickness=1,
        focuscolor=accent,
        padding=(8, 4),
        font=base_font,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "TButton",
        background=[("active", accent), ("pressed", accent)],
        foreground=[("active", accent_fg), ("pressed", accent_fg)],
        bordercolor=[("active", accent), ("pressed", accent)],
    )

    style.configure(
        "Accent.TButton",
        background=accent,
        foreground=accent_fg,
        bordercolor=accent,
        lightcolor=accent,
        darkcolor=accent,
        focuscolor=fg,
        padding=(10, 6),
        font=bold_font,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", fg), ("pressed", fg)],
        foreground=[("active", bg), ("pressed", bg)],
        bordercolor=[("active", fg), ("pressed", fg)],
    )

    style.configure(
        "TEntry",
        fieldbackground=surface,
        foreground=fg,
        insertcolor=accent,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=(4, 2),
        relief="flat",
        borderwidth=0,
    )

    style.configure(
        "TCombobox",
        fieldbackground=surface,
        background=surface,
        foreground=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        arrowcolor=accent,
        padding=(4, 2),
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", surface), ("!disabled", surface)],
        background=[("readonly", surface), ("!disabled", surface)],
        foreground=[("readonly", fg), ("!disabled", fg)],
        bordercolor=[("focus", accent), ("active", border), ("!disabled", border)],
        lightcolor=[("focus", accent), ("!disabled", border)],
        darkcolor=[("focus", accent), ("!disabled", border)],
        arrowcolor=[("active", accent), ("!disabled", accent)],
        selectbackground=[("readonly", accent)],
        selectforeground=[("readonly", accent_fg)],
    )
    # Dropdown listbox painted by the popdown window. Style its option
    # database so the dropdown matches the entry instead of going white.
    root.option_add("*TCombobox*Listbox.background", surface)
    root.option_add("*TCombobox*Listbox.foreground", fg)
    root.option_add("*TCombobox*Listbox.selectBackground", accent)
    root.option_add("*TCombobox*Listbox.selectForeground", accent_fg)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.relief", "flat")
    root.option_add("*TCombobox*Listbox.highlightThickness", 0)

    style.configure(
        "TCheckbutton",
        background=bg,
        foreground=fg,
        indicatorbackground=surface,
        indicatorforeground=accent,
        indicatorcolor=surface,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        focuscolor=accent,
        padding=(4, 2),
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "TCheckbutton",
        background=[("active", bg)],
        foreground=[("active", accent)],
        indicatorcolor=[("selected", accent), ("!selected", surface)],
        bordercolor=[("active", accent), ("!disabled", border)],
        lightcolor=[("active", accent), ("!disabled", border)],
        darkcolor=[("active", accent), ("!disabled", border)],
    )

    style.configure(
        "TNotebook",
        background=bg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        tabmargins=(2, 4, 2, 0),
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "TNotebook.Tab",
        background=surface,
        foreground=dim,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        padding=(14, 6),
        font=base_font,
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", bg), ("active", surface)],
        foreground=[("selected", accent), ("active", fg)],
        bordercolor=[("selected", accent), ("!selected", border)],
        lightcolor=[("selected", accent), ("!selected", border)],
        darkcolor=[("selected", accent), ("!selected", border)],
        expand=[("selected", (1, 1, 1, 0))],
    )

    style.configure(
        "Treeview",
        background=surface,
        fieldbackground=surface,
        foreground=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        rowheight=int(font_size * 2.4),
        font=base_font,
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", accent)],
        foreground=[("selected", accent_fg)],
        bordercolor=[("!disabled", border)],
        lightcolor=[("!disabled", border)],
        darkcolor=[("!disabled", border)],
    )
    style.configure(
        "Treeview.Heading",
        background=bg,
        foreground=accent,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        relief="flat",
        font=bold_font,
        padding=(6, 4),
        borderwidth=0,
    )
    style.map(
        "Treeview.Heading",
        background=[("active", surface)],
        foreground=[("active", fg)],
        bordercolor=[("active", border), ("!disabled", border)],
    )

    # Fallback ttk scrollbar styling for any leftover callers — the
    # canvas-painted AmberScrollbar handles the visible surfaces but we
    # still want any unsubstituted ttk.Scrollbar to be on-palette.
    for sb_layout in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(
            sb_layout,
            background=dim,
            troughcolor=bg,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            arrowcolor=accent,
            relief="flat",
            borderwidth=0,
        )
        style.map(
            sb_layout,
            background=[("active", accent), ("!disabled", dim)],
            arrowcolor=[("active", accent_fg), ("!disabled", accent)],
            bordercolor=[("!disabled", border)],
        )

    style.configure(
        "TPanedwindow",
        background=bg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        relief="flat",
        borderwidth=0,
    )
    style.configure(
        "Sash",
        background=border,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        gripcount=0,
        sashthickness=4,
    )
    style.configure(
        "TSeparator",
        background=border,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
    )

    # ------------------------------------------------------------------
    # Titlebar styles (registered late so theme switches refresh them).
    # ------------------------------------------------------------------
    # Imported here to avoid a top-level circular dependency between
    # the themes package and the widgets package.
    from bgs_translator.gui.widgets.amber_titlebar import install_titlebar_styles

    install_titlebar_styles(root, theme, base_font)

    # ------------------------------------------------------------------
    # Root background.
    # ------------------------------------------------------------------
    try:
        root.tk.call("tk_setPalette", bg)
    except tk.TclError:
        pass
    if isinstance(root, tk.Tk):
        try:
            root.configure(background=bg)
        except tk.TclError:
            pass


def _strip_widget_borders(style: ttk.Style) -> None:
    """Override widget layouts to drop clam's hardcoded 3D edges.

    clam draws Entry/Combobox/Treeview through a chain of layout
    elements (``Entry.field`` -> ``Entry.padding`` -> ``Entry.textarea``).
    ``Entry.field`` is the rectangle that paints the 3D border, and the
    colour keys we set above can only modify some of its sub-rectangles.
    Replacing the layout with the inner elements directly makes the
    surrounding 3D edge disappear entirely.

    The layout strings below were derived by inspecting
    ``style.layout(name)`` under clam and stripping the outer field /
    border elements that paint the unwanted lines.
    """

    safe_layouts: dict[str, list[tuple[str, dict[str, object]]]] = {
        "TEntry": [
            (
                "Entry.padding",
                {
                    "sticky": "nswe",
                    "children": [("Entry.textarea", {"sticky": "nswe"})],
                },
            )
        ],
        "TCombobox": [
            (
                "Combobox.padding",
                {
                    "expand": "1",
                    "sticky": "nswe",
                    "children": [
                        ("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
                        ("Combobox.textarea", {"expand": "1", "sticky": "nswe"}),
                    ],
                },
            )
        ],
        "Treeview": [
            (
                "Treeview.padding",
                {
                    "sticky": "nswe",
                    "children": [("Treeview.treearea", {"sticky": "nswe"})],
                },
            )
        ],
        "TNotebook": [("Notebook.client", {"sticky": "nswe"})],
    }
    for layout_name, layout_spec in safe_layouts.items():
        try:
            # ``_LayoutSpec`` from the tk stubs is a deeply recursive
            # structure that mypy cannot prove our dict literals satisfy;
            # the runtime shape is correct so we cast on the boundary.
            style.layout(layout_name, cast(Any, layout_spec))
        except tk.TclError:
            # Some Tk builds reject layout edits; configuration above
            # still applies, so we just continue.
            continue


__all__ = ["ThemeConfig", "apply_theme"]
