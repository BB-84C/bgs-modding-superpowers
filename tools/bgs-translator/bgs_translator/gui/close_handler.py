"""Two-stage close confirmation for the Tk control panel."""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import tkinter as tk
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Final

from bgs_translator.config import paths
from bgs_translator.core import event_queue
from bgs_translator.gui.i18n import gettext as _

log = logging.getLogger(__name__)

_LAST_EXPORT_FALLBACK: Final[str] = datetime.min.replace(tzinfo=UTC).isoformat()


class CloseHandler:
    """Manage PRD §4.2 close-window-only vs stop-everything flow."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        on_force_close: Callable[[], None] | None = None,
        on_window_close: Callable[[], None] | None = None,
        get_in_flight_count: Callable[[], int] | None = None,
        get_unsaved_count: Callable[[], int] | None = None,
        get_active_project: Callable[[], str | None] | None = None,
        export_project: Callable[[str], None] | None = None,
    ) -> None:
        self._root = root
        self._on_force_close = on_force_close
        self._on_window_close = on_window_close
        self._get_in_flight_count = get_in_flight_count or event_queue.in_flight_count
        self._get_unsaved_count = get_unsaved_count or self._count_unsaved_manual_edits
        self._get_active_project = get_active_project or (lambda: None)
        self._export_project = export_project or self._export_project_subprocess
        self._confirming = False
        root.protocol("WM_DELETE_WINDOW", self.request_close)

    def request_close(self) -> None:
        """Entry point for custom titlebar X, native close, and Alt+F4."""

        if self._confirming:
            return
        self._confirming = True
        self._show_stage_one_dialog()

    def _show_stage_one_dialog(self) -> None:
        in_flight = self._safe_count(self._get_in_flight_count)
        unsaved = self._safe_count(self._get_unsaved_count)
        dialog = self._new_modal(title=_("Close window"))

        body = ttk.Frame(dialog, padding=(16, 12))
        body.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            body,
            text=(
                f"{_('Background batches in flight')}: {in_flight}\n"
                f"{_('Unsaved manual edits')}: {unsaved}"
            ),
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Button(
            body,
            text=_("Close window only"),
            command=lambda: self._close_window_only(dialog, unsaved),
        ).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            body,
            text=_("Stop everything (cancel batches)"),
            style="Accent.TButton",
            command=lambda: self._stop_everything(dialog, unsaved),
        ).grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(body, text=_("Cancel"), command=lambda: self._cancel(dialog)).grid(
            row=1, column=2, sticky="ew"
        )

        self._center(dialog)

    def _close_window_only(self, dialog: tk.Toplevel, unsaved: int) -> None:
        dialog.destroy()
        if unsaved > 0:
            self._show_stage_two_dialog(stop_everything=False, unsaved=unsaved)
            return
        self._finish_close(force=False)

    def _stop_everything(self, dialog: tk.Toplevel, unsaved: int) -> None:
        dialog.destroy()
        if unsaved > 0:
            self._show_stage_two_dialog(stop_everything=True, unsaved=unsaved)
            return
        self._finish_close(force=True)

    def _show_stage_two_dialog(self, *, stop_everything: bool, unsaved: int) -> None:
        dialog = self._new_modal(title=_("Save before close?"))
        body = ttk.Frame(dialog, padding=(16, 12))
        body.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            body,
            text=f"{unsaved} {_('unsaved edits exist.')}",
            justify="left",
            wraplength=420,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Button(
            body,
            text=_("Save SST and quit"),
            style="Accent.TButton",
            command=lambda: self._save_and_quit(dialog, stop_everything),
        ).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            body,
            text=_("Discard and quit"),
            command=lambda: self._discard_and_quit(dialog, stop_everything),
        ).grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(body, text=_("Cancel"), command=lambda: self._cancel(dialog)).grid(
            row=1, column=2, sticky="ew"
        )

        self._center(dialog)

    def _save_and_quit(self, dialog: tk.Toplevel, stop_everything: bool) -> None:
        project = self._get_active_project()
        if not project:
            messagebox.showerror(
                title=_("Save SST and quit"),
                message=_("No active project selected."),
                parent=dialog,
            )
            return
        try:
            self._export_project(project)
        except Exception as exc:
            messagebox.showerror(
                title=_("Save SST and quit"),
                message=f"{_('Export failed')}: {exc}",
                parent=dialog,
            )
            return
        dialog.destroy()
        self._finish_close(force=stop_everything)

    def _discard_and_quit(self, dialog: tk.Toplevel, stop_everything: bool) -> None:
        dialog.destroy()
        self._finish_close(force=stop_everything)

    def _cancel(self, dialog: tk.Toplevel) -> None:
        dialog.destroy()
        self._confirming = False

    def _finish_close(self, *, force: bool) -> None:
        if force and self._on_force_close is not None:
            try:
                self._on_force_close()
            except Exception as exc:
                log.debug("Force-close callback failed: %s", exc)
        if not force and self._on_window_close is not None:
            try:
                self._on_window_close()
            except Exception as exc:
                log.debug("Window-close callback failed: %s", exc)
        self._confirming = False
        self._root.destroy()

    def _new_modal(self, *, title: str) -> tk.Toplevel:
        dialog = tk.Toplevel(self._root)
        dialog.title(title)
        dialog.transient(self._root)
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._cancel(dialog))
        return dialog

    def _center(self, dialog: tk.Toplevel) -> None:
        dialog.update_idletasks()
        root_x = self._root.winfo_rootx()
        root_y = self._root.winfo_rooty()
        root_w = self._root.winfo_width()
        root_h = self._root.winfo_height()
        dw = dialog.winfo_width()
        dh = dialog.winfo_height()
        dialog.geometry(f"+{root_x + (root_w - dw) // 2}+{root_y + (root_h - dh) // 2}")

    def _count_unsaved_manual_edits(self) -> int:
        project = self._get_active_project()
        if not project:
            return 0
        project_root = paths.project_root(project)
        db_path = project_root / "memory" / "memory.sqlite"
        if not db_path.exists():
            return 0
        cutoff = self._last_export_timestamp(project_root)
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM units
                WHERE via_llm = 0
                  AND dest IS NOT NULL
                  AND updated_at > ?
                """,
                (cutoff,),
            ).fetchone()
            return int(row[0] if row else 0)
        except sqlite3.DatabaseError as exc:
            log.warning("Could not count unsaved manual edits for %s: %s", project, exc)
            return 0
        finally:
            conn.close()

    @staticmethod
    def _last_export_timestamp(project_root: Path) -> str:
        exports_dir = project_root / "exports"
        if not exports_dir.exists():
            return _LAST_EXPORT_FALLBACK
        latest = max((p.stat().st_mtime for p in exports_dir.glob("*") if p.is_file()), default=None)
        if latest is None:
            return _LAST_EXPORT_FALLBACK
        return datetime.fromtimestamp(latest, UTC).isoformat()

    @staticmethod
    def _safe_count(getter: Callable[[], int]) -> int:
        try:
            return max(0, int(getter()))
        except Exception as exc:
            log.debug("Close-dialog count getter failed: %s", exc)
            return 0

    @staticmethod
    def _export_project_subprocess(project: str) -> None:
        cmd = [sys.executable, "-m", "bgs_translator.cli.app", "project", "export", project]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "xtl project export failed")[-2000:])


__all__ = ["CloseHandler"]
