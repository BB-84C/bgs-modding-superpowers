"""Logs tab for the Tk control panel.

Tails today's JSONL log file from ``paths.logs_root() / <date>.log``.
A ``Live`` toggle controls whether the tab auto-refreshes every two
seconds. Level + source filters narrow the visible entries.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tkinter as tk
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tkinter import ttk
from typing import Final

from bgs_translator.config import paths
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.empty_state import EmptyStatePanel

log = logging.getLogger(__name__)

_REFRESH_INTERVAL_MS: Final[int] = 2000
_MAX_LINES: Final[int] = 2000

_LEVEL_TAGS: Final[dict[str, str]] = {
    "error": "log-error",
    "warn": "log-warn",
    "warning": "log-warn",
    "info": "log-info",
    "debug": "log-debug",
}


class LogsTab(ttk.Frame):
    """Scrolling JSONL log viewer."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(12, 10))
        self._live = tk.BooleanVar(value=True)
        self._level_filter = tk.StringVar(value=_("all"))
        self._source_filter = tk.StringVar(value=_("all"))
        self.day_var = tk.StringVar(value=datetime.now(UTC).strftime("%Y-%m-%d"))
        self._after_id: str | None = None

        ttk.Label(self, text=_("Logs"), style="Phosphor.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        # Filter row ----------------------------------------------------
        controls = ttk.Frame(self)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text=f"{_('Day')}:", style="Dim.TLabel").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self.day_var,
            values=_last_seven_days(),
            width=12,
            state="readonly",
        ).pack(side="left", padx=(4, 12))
        ttk.Label(controls, text=f"{_('Level')}:", style="Dim.TLabel").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self._level_filter,
            values=[_("all"), _("error"), _("warn"), _("info"), _("debug")],
            width=8,
            state="readonly",
        ).pack(side="left", padx=(4, 12))
        ttk.Label(controls, text=f"{_('Source')}:", style="Dim.TLabel").pack(side="left")
        ttk.Combobox(
            controls,
            textvariable=self._source_filter,
            values=[_("all"), _("batch"), _("glossary"), _("sst-write"), _("profile-probe"), _("validator")],
            width=14,
            state="readonly",
        ).pack(side="left", padx=(4, 12))
        self.pause_button = ttk.Button(controls, text=_("Pause tail"), command=self.toggle_tail)
        self.pause_button.pack(side="left")
        ttk.Button(controls, text=_("Filter"), command=self._refresh).pack(side="left", padx=(12, 0))
        ttk.Button(controls, text=_("Open logs folder"), command=self.open_logs_folder).pack(side="left", padx=(8, 0))

        # Viewer --------------------------------------------------------
        viewer_frame = ttk.Frame(self)
        viewer_frame.grid(row=2, column=0, sticky="nsew")
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        viewer_frame.rowconfigure(0, weight=1)
        viewer_frame.columnconfigure(0, weight=1)

        self._text = tk.Text(
            viewer_frame,
            wrap="none",
            relief="flat",
            highlightthickness=0,
            state="disabled",
        )
        self._text.grid(row=0, column=0, sticky="nsew")
        y_scroll = AmberScrollbar(
            viewer_frame, orient="vertical", command=self._text.yview
        )
        x_scroll = AmberScrollbar(
            viewer_frame, orient="horizontal", command=self._text.xview
        )
        self._text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self._y_scroll = y_scroll
        self._x_scroll = x_scroll

        # Polish pass 4: vault-tec empty-state glyph stacked above the
        # Text widget for when today's log is missing/empty.
        self._empty_state = EmptyStatePanel(
            viewer_frame,
            caption=_("[ NO LOGS RECORDED ]"),
            source_caption="[ NO LOGS RECORDED ]",
            sub_line=_("Today's JSONL is empty"),
        )
        self._empty_state.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._empty_state.lift()

        # Color tags.
        self._text.tag_configure("log-error", foreground="#ff5544")
        self._text.tag_configure("log-warn", foreground="#ffcc44")
        self._text.tag_configure("log-info", foreground="#ffb000")
        self._text.tag_configure("log-debug", foreground="#a07000")
        self._text.tag_configure("log-ts", foreground="#a07000")

        self._refresh()
        self._schedule_refresh()

    def destroy(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None
        super().destroy()

    # Internals --------------------------------------------------------
    def _log_path_for_today(self) -> Path:
        return self._log_path_for_day(self.day_var.get())

    def _log_path_for_day(self, day: str) -> Path:
        return paths.logs_root() / f"{day}.log"

    def refresh(self) -> None:
        self._refresh()

    def toggle_tail(self) -> None:
        self._live.set(not self._live.get())
        self.pause_button.configure(text=_("Pause tail") if self._live.get() else _("Resume tail"))

    def open_logs_folder(self) -> None:
        self._open_path_in_explorer(paths.logs_root())

    def _refresh(self) -> None:
        log_path = self._log_path_for_today()
        if not log_path.exists():
            self._render([])
            return
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            log.warning("Could not read %s: %s", log_path, exc)
            self._render([])
            return
        # Tail.
        if len(lines) > _MAX_LINES:
            lines = lines[-_MAX_LINES:]
        self._render(lines)

    def _schedule_refresh(self) -> None:
        if not self._live.get():
            self._after_id = self.after(_REFRESH_INTERVAL_MS, self._schedule_refresh)
            return
        self._refresh()
        self._after_id = self.after(_REFRESH_INTERVAL_MS, self._schedule_refresh)

    def _render(self, lines: list[str]) -> None:
        level_filter = _localized_filter_to_raw(self._level_filter.get(), ["all", "error", "warn", "info", "debug"])
        source_filter = _localized_filter_to_raw(self._source_filter.get(), ["all", "batch", "glossary", "sst-write", "profile-probe", "validator"])

        # Toggle empty-state visibility based on whether there is any
        # content to show after filtering.
        if not lines:
            self._empty_state.lift()
        else:
            self._empty_state.lower()

        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        for line in lines:
            ts, level, src, message = _parse_jsonl_line(line)
            if level_filter != "all" and level != level_filter:
                continue
            if source_filter != "all" and src != source_filter:
                continue
            tag = _LEVEL_TAGS.get(level, "log-info")
            self._text.insert("end", f"{ts} ", ("log-ts",))
            self._text.insert("end", f"[{level:<5}] ", (tag,))
            self._text.insert("end", f"{src:<14} ", ("log-ts",))
            self._text.insert("end", message, (tag,))
            self._text.insert("end", "\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def text_content(self) -> str:
        return str(self._text.get("1.0", "end"))

    @staticmethod
    def _open_path_in_explorer(path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except OSError as exc:
            log.warning("Could not open %s: %s", path, exc)


def _parse_jsonl_line(line: str) -> tuple[str, str, str, str]:
    """Best-effort parse of a JSONL log line into (ts, level, source, message)."""

    line = line.strip()
    if not line:
        return ("", "info", "-", "")
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return ("", "info", "-", line)
    if not isinstance(obj, dict):
        return ("", "info", "-", line)
    ts = str(obj.get("ts") or obj.get("timestamp") or "")
    level = str(obj.get("level") or "info").lower()
    src = str(obj.get("source") or obj.get("src") or "-")
    message = str(obj.get("msg") or obj.get("message") or "")
    return (ts, level, src, message)


def _last_seven_days() -> list[str]:
    today = datetime.now(UTC).date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(7)]


def _localized_filter_to_raw(value: str, raw_values: list[str]) -> str:
    for raw in raw_values:
        if value == _(raw):
            return raw
    return value


__all__ = ["LogsTab"]
