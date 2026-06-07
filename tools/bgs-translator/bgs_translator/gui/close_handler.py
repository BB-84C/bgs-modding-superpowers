"""Two-stage close confirmation for the Tk control panel.

The first close attempt opens a confirmation dialog. The user must
click ``Stop everything`` (or the dialog's primary button) for the
second stage to fire and actually destroy the root window. ``Cancel``
returns to the running state.

The full spec calls for a richer dialog that distinguishes
``Close window only`` (detach the asyncio loop) from ``Stop everything``
(cancel in-flight batches and quit). For Chunk-L MVP we only implement
``Stop everything`` plus ``Cancel``; the detached-loop path is left as
a TODO so it can be wired once the runner sidecar lands.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from bgs_translator.gui.i18n import gettext as _


class CloseHandler:
    """Manage the two-stage close lifecycle for a Tk root."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        on_force_close: Callable[[], None] | None = None,
    ) -> None:
        self._root = root
        self._on_force_close = on_force_close
        self._confirming = False
        root.protocol("WM_DELETE_WINDOW", self.request_close)

    def request_close(self) -> None:
        """Entry point. Show stage-1 unless we are already confirming."""

        if self._confirming:
            return
        self._confirming = True
        try:
            self._show_confirmation_dialog()
        finally:
            self._confirming = False

    def _show_confirmation_dialog(self) -> None:
        dialog = tk.Toplevel(self._root)
        dialog.title(_("Confirm close"))
        dialog.transient(self._root)
        dialog.resizable(False, False)
        dialog.grab_set()

        # TODO(Chunk-L.2): add ``Close window only`` button once a
        # detached runner is available; for now we only confirm full quit.
        body = ttk.Frame(dialog, padding=(16, 12))
        body.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            body,
            text=_("Are you sure you want to close? Unsaved work may be lost."),
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Button(body, text=_("Cancel"), command=dialog.destroy).grid(
            row=1, column=0, sticky="e", padx=(0, 6)
        )
        ttk.Button(
            body,
            text=_("Save"),
            style="Accent.TButton",
            command=lambda: self._do_close(dialog),
        ).grid(row=1, column=1, sticky="w")

        # Center over the root.
        dialog.update_idletasks()
        root_x = self._root.winfo_rootx()
        root_y = self._root.winfo_rooty()
        root_w = self._root.winfo_width()
        root_h = self._root.winfo_height()
        dw = dialog.winfo_width()
        dh = dialog.winfo_height()
        dialog.geometry(f"+{root_x + (root_w - dw) // 2}+{root_y + (root_h - dh) // 2}")

    def _do_close(self, dialog: tk.Toplevel) -> None:
        dialog.destroy()
        if self._on_force_close is not None:
            try:
                self._on_force_close()
            except Exception:
                pass
        self._root.destroy()


__all__ = ["CloseHandler"]
