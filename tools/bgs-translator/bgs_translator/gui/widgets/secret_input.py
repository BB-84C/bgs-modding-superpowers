"""Secret-text Entry widget with a show/hide toggle.

Used for API-key fields. Defaults to masked. The toggle button text
flips between ``Show`` and ``Hide`` as the masking is changed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SecretInput(ttk.Frame):
    """An Entry with a sibling Show/Hide button."""

    _MASK_CHAR = "\u2022"  # bullet

    def __init__(
        self,
        master: tk.Misc,
        *,
        placeholder: str = "",
        width: int = 32,
    ) -> None:
        super().__init__(master)
        self._var = tk.StringVar(value=placeholder)
        self._shown = False

        self._entry = ttk.Entry(
            self,
            textvariable=self._var,
            show=self._MASK_CHAR,
            width=width,
        )
        self._entry.pack(side="left", fill="x", expand=True)

        self._toggle = ttk.Button(
            self,
            text="Show",
            width=6,
            command=self._toggle_visibility,
        )
        self._toggle.pack(side="left", padx=(4, 0))

    def _toggle_visibility(self) -> None:
        self._shown = not self._shown
        self._entry.configure(show="" if self._shown else self._MASK_CHAR)
        self._toggle.configure(text="Hide" if self._shown else "Show")

    def get(self) -> str:
        return self._var.get()

    def set(self, value: str) -> None:
        self._var.set(value)


__all__ = ["SecretInput"]
