"""Project tab for the Tk control panel.

Shows metadata, signature counts pulled from ``memory.sqlite`` via
``core.memory`` helpers, and action buttons. Heavy operations (export,
rescan) are stubbed for MVP; the export hook invokes ``xtl project
export`` as a subprocess so the CLI integration is end-to-end.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
import tkinter as tk
import tomllib
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Final, Literal

from bgs_translator.config import paths
from bgs_translator.core.memory import open_memory_db
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar

log = logging.getLogger(__name__)

_PLACEHOLDER: Final[str] = "-"


def _safe_read_project_toml(project_root: Path) -> dict[str, Any]:
    toml_path = project_root / "project.toml"
    if not toml_path.exists():
        return {}
    try:
        with toml_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("Could not read %s: %s", toml_path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _signature_counts(project_root: Path) -> list[tuple[str, int, int, int, int, int]]:
    """Return a list of (signature, total, translated, partial, locked, orphan).

    Reads counts via ``open_memory_db``. Returns ``[]`` if the project
    has no memory db yet.
    """

    if not (project_root / "memory" / "memory.sqlite").exists():
        return []
    conn: sqlite3.Connection | None = None
    try:
        conn = open_memory_db(project_root)
        rows = conn.execute(
            """
            SELECT
                signature,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'translated' THEN 1 ELSE 0 END) AS translated,
                SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) AS partial,
                SUM(CASE WHEN status = 'locked' THEN 1 ELSE 0 END) AS locked,
                SUM(CASE WHEN status = 'orphan' THEN 1 ELSE 0 END) AS orphan
            FROM units
            GROUP BY signature
            ORDER BY signature
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        log.warning("Memory query failed for %s: %s", project_root, exc)
        return []
    finally:
        if conn is not None:
            conn.close()
    return [
        (
            str(row[0]),
            int(row[1] or 0),
            int(row[2] or 0),
            int(row[3] or 0),
            int(row[4] or 0),
            int(row[5] or 0),
        )
        for row in rows
    ]


class ProjectTab(ttk.Frame):
    """Top-level Project tab frame."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(12, 10))
        self._project_name: str | None = None
        self._project_meta: dict[str, Any] = {}

        # Header --------------------------------------------------------
        self._title_var = tk.StringVar(value=_("No project selected"))
        ttk.Label(self, textvariable=self._title_var, style="Phosphor.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        # Metadata box --------------------------------------------------
        self._meta_frame = ttk.Frame(self, style="Surface.TFrame", padding=(10, 8))
        self._meta_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self._meta_vars: dict[str, tk.StringVar] = {}
        rows = [
            ("Project", "project_name"),
            ("Source", "source_lang"),
            ("Target", "target_lang"),
            ("Game", "game"),
            ("Created", "created_at"),
            ("Plugin", "plugin_path"),
            ("Plugin SHA", "plugin_sha_short"),
            ("Active profile", "active_profile"),
            ("Cost cap", "cost_cap"),
        ]
        for index, (caption, key) in enumerate(rows):
            ttk.Label(self._meta_frame, text=f"{caption}:", style="Dim.TLabel").grid(
                row=index, column=0, sticky="w", padx=(0, 12), pady=1
            )
            var = tk.StringVar(value=_PLACEHOLDER)
            self._meta_vars[key] = var
            ttk.Label(self._meta_frame, textvariable=var, style="TLabel").grid(
                row=index, column=1, sticky="w", pady=1
            )

        # Signature counts table ---------------------------------------
        counts_frame = ttk.Frame(self)
        counts_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        columns = (
            ("signature", _("Signature"), 130),
            ("total", _("Total"), 70),
            ("translated", _("Translated"), 90),
            ("partial", _("Partial"), 70),
            ("locked", _("Locked"), 70),
            ("orphan", _("Orphan"), 70),
        )
        self._tree = ttk.Treeview(
            counts_frame,
            columns=[col[0] for col in columns],
            show="headings",
            height=12,
        )
        for col_id, heading, width in columns:
            self._tree.heading(col_id, text=heading)
            anchor: Literal["w", "e"] = "w" if col_id == "signature" else "e"
            self._tree.column(col_id, width=width, anchor=anchor, stretch=True)
        tree_scroll = AmberScrollbar(
            counts_frame, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self._tree_scroll = tree_scroll
        counts_frame.rowconfigure(0, weight=1)
        counts_frame.columnconfigure(0, weight=1)

        # Toggle row ----------------------------------------------------
        self._preview_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self,
            text=_("Always preview system prompt before batch dispatch"),
            variable=self._preview_var,
            command=self._on_preview_toggled,
        ).grid(row=3, column=0, sticky="w", pady=(0, 6))

        # Action buttons -----------------------------------------------
        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="w")
        ttk.Button(actions, text=_("Rescan plugin"), command=self._on_rescan).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(
            actions,
            text=_("Export SST"),
            style="Accent.TButton",
            command=self._on_export,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text=_("Open exports folder"), command=self._on_open_exports).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(actions, text=_("Project settings"), command=self._on_settings).pack(
            side="left", padx=(0, 6)
        )

    # Public API -------------------------------------------------------
    def load_project(self, name: str) -> None:
        """Load the given project's metadata + signature counts."""

        self._project_name = name
        project_root = paths.project_root(name)
        meta_raw = _safe_read_project_toml(project_root)
        project_section = meta_raw.get("project", {}) if isinstance(meta_raw, dict) else {}
        settings_section = meta_raw.get("settings", {}) if isinstance(meta_raw, dict) else {}
        cost_section = meta_raw.get("cost", {}) if isinstance(meta_raw, dict) else {}

        self._project_meta = {
            "root": project_root,
            "project": project_section,
            "settings": settings_section,
            "cost": cost_section,
        }

        self._title_var.set(f"{_('Project')}: {name}")

        plugin_sha = str(project_section.get("source_plugin_sha256", ""))
        sha_short = plugin_sha[:12] + "..." if plugin_sha else _PLACEHOLDER
        cost_cap = cost_section.get("cap_usd")
        cost_cap_text = f"${float(cost_cap):.2f}" if isinstance(cost_cap, (int, float)) else _PLACEHOLDER

        self._meta_vars["project_name"].set(name)
        self._meta_vars["source_lang"].set(str(project_section.get("source_lang", _PLACEHOLDER)))
        self._meta_vars["target_lang"].set(str(project_section.get("target_lang", _PLACEHOLDER)))
        self._meta_vars["game"].set(str(project_section.get("game", _PLACEHOLDER)))
        self._meta_vars["created_at"].set(str(project_section.get("created_at", _PLACEHOLDER)))
        plugin_path = str(project_section.get("source_plugin_path", _PLACEHOLDER))
        self._meta_vars["plugin_path"].set(plugin_path)
        self._meta_vars["plugin_sha_short"].set(sha_short)
        self._meta_vars["active_profile"].set(
            str(settings_section.get("active_profile", _PLACEHOLDER)) or _PLACEHOLDER
        )
        self._meta_vars["cost_cap"].set(cost_cap_text)

        self._refresh_counts(project_root)

    def clear(self) -> None:
        """Reset all displayed values."""

        self._project_name = None
        self._project_meta = {}
        self._title_var.set(_("No project selected"))
        for var in self._meta_vars.values():
            var.set(_PLACEHOLDER)
        for row in self._tree.get_children():
            self._tree.delete(row)

    # Internals --------------------------------------------------------
    def _refresh_counts(self, project_root: Path) -> None:
        for row in self._tree.get_children():
            self._tree.delete(row)
        for signature, total, translated, partial, locked, orphan in _signature_counts(
            project_root
        ):
            self._tree.insert(
                "",
                "end",
                values=(signature, total, translated, partial, locked, orphan),
            )

    def _on_preview_toggled(self) -> None:
        # TODO(Chunk-L.2): wire to settings.behavior.prompt_preview_required.
        log.info("Prompt preview toggle = %s", self._preview_var.get())

    def _on_rescan(self) -> None:
        # TODO(Chunk-L.2): invoke 'xtl project rescan'.
        messagebox.showinfo(
            title=_("Rescan plugin"),
            message=_("Coming soon") + " (Chunk L.2)",
            parent=self,
        )

    def _on_export(self) -> None:
        if self._project_name is None:
            messagebox.showinfo(
                title=_("Export SST"),
                message=_("No project selected"),
                parent=self,
            )
            return
        cmd = [sys.executable, "-m", "bgs_translator.cli.app", "project", "export", self._project_name]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            messagebox.showerror(
                title=_("Export SST"),
                message=f"Failed to launch xtl project export: {exc}",
                parent=self,
            )
            return
        if result.returncode == 0:
            messagebox.showinfo(
                title=_("Export SST"),
                message=result.stdout[-2000:] or "OK",
                parent=self,
            )
        else:
            messagebox.showerror(
                title=_("Export SST"),
                message=(result.stderr or result.stdout)[-2000:],
                parent=self,
            )

    def _on_open_exports(self) -> None:
        if self._project_name is None:
            return
        exports = paths.project_root(self._project_name) / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        self._open_path_in_explorer(exports)

    def _on_settings(self) -> None:
        # TODO(Chunk-L.2): open a project.toml edit dialog.
        messagebox.showinfo(
            title=_("Project settings"),
            message=_("Coming soon") + " (Chunk L.2)",
            parent=self,
        )

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


__all__ = ["ProjectTab"]
