"""Entries tab placeholder for Chunk L MVP.

Full table view + filter row lands in Chunk L.2. For now this frame
shows a phosphor-styled placeholder so the notebook can still mount it.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bgs_translator.gui.i18n import gettext as _


class EntriesTab(ttk.Frame):
    """Placeholder Entries tab."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(24, 24))
        ttk.Label(self, text=_("Entries"), style="Phosphor.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(
            self,
            text=_("Coming soon") + " (Chunk L.2)",
            style="Dim.TLabel",
        ).pack(anchor="w")


__all__ = ["EntriesTab"]
