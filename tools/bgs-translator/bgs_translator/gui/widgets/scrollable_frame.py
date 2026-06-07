"""A simple vertically scrollable frame.

Wrap any content inside ``ScrollableFrame.interior`` and the canvas
will provide a vertical scrollbar when the content overflows.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """ttk.Frame holding a Canvas + vertical scrollbar + inner frame."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self._canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self._scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)

        self.interior = ttk.Frame(self._canvas)
        self._interior_id = self._canvas.create_window(
            (0, 0), window=self.interior, anchor="nw"
        )

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.interior.bind("<Configure>", self._on_interior_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _on_interior_resize(self, _event: tk.Event[tk.Misc]) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event: tk.Event[tk.Misc]) -> None:
        self._canvas.itemconfigure(self._interior_id, width=event.width)

    def _bind_wheel(self, _event: tk.Event[tk.Misc]) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event: tk.Event[tk.Misc]) -> None:
        self._canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: tk.Event[tk.Misc]) -> None:
        # event.delta is +/-120 per notch on Windows.
        delta = int(-event.delta / 120) if event.delta else 0
        if delta:
            self._canvas.yview_scroll(delta, "units")


__all__ = ["ScrollableFrame"]
