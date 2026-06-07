"""Theme palette dataclass and Tk style application helpers."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


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
        # ``clam`` honors background and foreground configuration on Windows.
        # The default ``vista`` and ``xpnative`` themes ignore most palette
        # options, which is why the phosphor palette would otherwise vanish.
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

    # Tk option database for classic widgets (tk.Frame, tk.Label, tk.Text...).
    root.option_add("*background", bg)
    root.option_add("*foreground", fg)
    root.option_add("*Font", base_font)
    root.option_add("*Text.background", surface)
    root.option_add("*Text.foreground", fg)
    root.option_add("*Text.insertBackground", accent)
    root.option_add("*Text.selectBackground", accent)
    root.option_add("*Text.selectForeground", accent_fg)
    root.option_add("*Entry.background", surface)
    root.option_add("*Entry.foreground", fg)
    root.option_add("*Entry.insertBackground", accent)
    root.option_add("*Menu.background", surface)
    root.option_add("*Menu.foreground", fg)
    root.option_add("*Menu.activeBackground", accent)
    root.option_add("*Menu.activeForeground", accent_fg)

    # ttk styles.
    style.configure(".", background=bg, foreground=fg, font=base_font)
    style.configure(
        "TFrame",
        background=bg,
        bordercolor=border,
    )
    style.configure(
        "Surface.TFrame",
        background=surface,
        bordercolor=border,
    )
    style.configure(
        "TLabel",
        background=bg,
        foreground=fg,
        font=base_font,
    )
    style.configure(
        "Accent.TLabel",
        background=bg,
        foreground=accent,
        font=bold_font,
    )
    style.configure(
        "Dim.TLabel",
        background=bg,
        foreground=dim,
        font=base_font,
    )
    style.configure(
        "Header.TLabel",
        background=bg,
        foreground=accent,
        font=bold_font,
    )
    style.configure(
        "Status.TLabel",
        background=surface,
        foreground=fg,
        font=base_font,
        padding=(6, 2),
    )

    style.configure(
        "TButton",
        background=surface,
        foreground=fg,
        bordercolor=border,
        focusthickness=1,
        focuscolor=accent,
        padding=(8, 4),
        font=base_font,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", accent), ("pressed", accent)],
        foreground=[("active", accent_fg), ("pressed", accent_fg)],
    )

    style.configure(
        "Accent.TButton",
        background=accent,
        foreground=accent_fg,
        bordercolor=accent,
        focuscolor=fg,
        padding=(10, 6),
        font=bold_font,
        relief="flat",
    )
    style.map(
        "Accent.TButton",
        background=[("active", fg), ("pressed", fg)],
        foreground=[("active", bg), ("pressed", bg)],
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
    )

    style.configure(
        "TCombobox",
        fieldbackground=surface,
        background=surface,
        foreground=fg,
        bordercolor=border,
        arrowcolor=accent,
        padding=(4, 2),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", surface)],
        foreground=[("readonly", fg)],
        selectbackground=[("readonly", accent)],
        selectforeground=[("readonly", accent_fg)],
    )

    style.configure(
        "TCheckbutton",
        background=bg,
        foreground=fg,
        indicatorbackground=surface,
        indicatorforeground=accent,
        focuscolor=accent,
        padding=(4, 2),
    )
    style.map(
        "TCheckbutton",
        background=[("active", bg)],
        foreground=[("active", accent)],
    )

    style.configure(
        "TNotebook",
        background=bg,
        bordercolor=border,
        tabmargins=(2, 4, 2, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=surface,
        foreground=dim,
        bordercolor=border,
        padding=(14, 6),
        font=base_font,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", bg), ("active", surface)],
        foreground=[("selected", accent), ("active", fg)],
        expand=[("selected", (1, 1, 1, 0))],
    )

    style.configure(
        "Treeview",
        background=surface,
        fieldbackground=surface,
        foreground=fg,
        bordercolor=border,
        rowheight=int(font_size * 2.2),
        font=base_font,
    )
    style.map(
        "Treeview",
        background=[("selected", accent)],
        foreground=[("selected", accent_fg)],
    )
    style.configure(
        "Treeview.Heading",
        background=bg,
        foreground=accent,
        bordercolor=border,
        relief="flat",
        font=bold_font,
        padding=(6, 4),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", surface)],
        foreground=[("active", fg)],
    )

    style.configure(
        "TScrollbar",
        background=surface,
        troughcolor=bg,
        bordercolor=border,
        arrowcolor=accent,
    )
    style.map(
        "TScrollbar",
        background=[("active", accent)],
    )

    style.configure(
        "TPanedwindow",
        background=bg,
    )
    style.configure(
        "TSeparator",
        background=border,
    )
    style.configure(
        "Phosphor.TLabel",
        background=bg,
        foreground=accent,
        font=(font_family, font_size + 1, "bold"),
    )

    # Root background.
    try:
        root.tk.call("tk_setPalette", bg)
    except tk.TclError:
        pass
    if isinstance(root, tk.Tk):
        try:
            root.configure(background=bg)
        except tk.TclError:
            pass


__all__ = ["ThemeConfig", "apply_theme"]
