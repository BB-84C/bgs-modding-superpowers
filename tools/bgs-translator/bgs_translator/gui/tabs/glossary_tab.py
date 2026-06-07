"""Glossary tab placeholder for Chunk L MVP."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bgs_translator.gui.i18n import gettext as _


class GlossaryTab(ttk.Frame):
    """Placeholder Glossary tab."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(24, 24))
        ttk.Label(self, text=_("Glossary"), style="Phosphor.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(
            self,
            text=_("Coming soon") + " (Chunk L.2)",
            style="Dim.TLabel",
        ).pack(anchor="w")


__all__ = ["GlossaryTab"]
