"""Entries tab: filtered TranslationUnit table plus row detail pane."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from bgs_translator.cli.edit import _append_audit, _apply_edit, _get_unit_or_exit
from bgs_translator.core.memory import open_memory_db, select_units_filtered
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.themes import ThemeConfig, get_theme
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.empty_state import EmptyStatePanel

ProjectRootProvider = Callable[[], Path | None]

_STATUS_VALUES: tuple[str, ...] = (
    "All",
    "untranslated",
    "partial",
    "translated",
    "locked",
    "orphan",
)


class EntriesTab(ttk.Frame):
    """Entries browser for project translation memory."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        project_root_provider: ProjectRootProvider | None = None,
        theme: ThemeConfig | str | None = None,
        gui_event_bridge: object | None = None,
    ) -> None:
        super().__init__(parent, padding=(8, 8))
        self._get_project_root = project_root_provider or (lambda: None)
        self._theme = get_theme(theme) if isinstance(theme, str) else theme or get_theme("amber")
        self._event_bridge = gui_event_bridge
        self._project_name: str | None = None
        self._all_units: list[dict[str, Any]] = []
        self._filtered_units: list[dict[str, Any]] = []
        self._selected_unit: dict[str, Any] | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_filter_row()
        self._build_table()
        self._build_detail_pane()

        self._empty_state = EmptyStatePanel(
            self,
            caption=_("[ NO ENTRIES LOADED ]"),
            sub_line=_("Select a project from the nav tree"),
            theme_name=self._theme.name,
        )
        self._show_empty_state(True)

    def attach_app(self, app: object) -> None:
        """Follow-up integration seam for app-level wiring without editing app.py here."""

        provider = getattr(app, "current_project_root", None)
        if callable(provider):
            self._get_project_root = provider

    def load_project(self, project_name: str) -> None:
        """Load all entries for the current project root."""

        self._project_name = project_name
        project_root = self._get_project_root()
        if project_root is None:
            self.clear()
            return
        conn = open_memory_db(project_root)
        try:
            rows = select_units_filtered(conn)
            self._all_units = [self._unit_from_row(row) for row in rows]
        finally:
            conn.close()
        self._refresh_filter_values()
        self._on_filter_apply()
        self._show_empty_state(not self._filtered_units)

    def clear(self) -> None:
        """Clear table and detail state."""

        self._project_name = None
        self._all_units.clear()
        self._filtered_units.clear()
        self._selected_unit = None
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._clear_detail()
        self._show_empty_state(True)

    def _build_filter_row(self) -> None:
        filter_frame = ttk.Frame(self, style="Surface.TFrame")
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for column in range(10):
            filter_frame.columnconfigure(column, weight=0)
        filter_frame.columnconfigure(8, weight=1)

        self._project_var = tk.StringVar(value="-")
        self._signature_var = tk.StringVar(value="All")
        self._field_var = tk.StringVar(value="All")
        self._status_var = tk.StringVar(value="All")
        self._search_var = tk.StringVar(value="")

        ttk.Label(filter_frame, text=f"{_('Project')}:", style="Phosphor.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 4)
        )
        self._project_combo = ttk.Combobox(
            filter_frame, textvariable=self._project_var, values=("-",), width=18, state="readonly"
        )
        self._project_combo.grid(row=0, column=1, sticky="w", padx=(0, 12))

        ttk.Label(filter_frame, text=f"{_('Signature')}:", style="Phosphor.TLabel").grid(
            row=0, column=2, sticky="w", padx=(0, 4)
        )
        self._signature_combo = ttk.Combobox(
            filter_frame, textvariable=self._signature_var, values=("All",), width=10, state="readonly"
        )
        self._signature_combo.grid(row=0, column=3, sticky="w", padx=(0, 12))

        ttk.Label(filter_frame, text=f"{_('Field')}:", style="Phosphor.TLabel").grid(
            row=0, column=4, sticky="w", padx=(0, 4)
        )
        self._field_combo = ttk.Combobox(
            filter_frame, textvariable=self._field_var, values=("All",), width=10, state="readonly"
        )
        self._field_combo.grid(row=0, column=5, sticky="w", padx=(0, 12))

        ttk.Label(filter_frame, text=f"{_('Status')}:", style="Phosphor.TLabel").grid(
            row=0, column=6, sticky="w", padx=(0, 4)
        )
        self._status_combo = ttk.Combobox(
            filter_frame, textvariable=self._status_var, values=_STATUS_VALUES, width=14, state="readonly"
        )
        self._status_combo.grid(row=0, column=7, sticky="w", padx=(0, 12))

        ttk.Label(filter_frame, text=f"{_('Search')}:", style="Phosphor.TLabel").grid(
            row=0, column=8, sticky="e", padx=(0, 4)
        )
        self._search_entry = ttk.Entry(filter_frame, textvariable=self._search_var)
        self._search_entry.grid(row=0, column=9, sticky="ew", padx=(0, 8))
        ttk.Button(filter_frame, text=_("Apply"), command=self._on_filter_apply).grid(
            row=0, column=10, padx=(0, 4)
        )
        ttk.Button(filter_frame, text=_("Reset"), command=self._on_filter_reset).grid(row=0, column=11)

    def _build_table(self) -> None:
        self._paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self._paned.grid(row=1, column=0, sticky="nsew")

        table_frame = ttk.Frame(self._paned, style="Surface.TFrame")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self._paned.add(table_frame, weight=4)

        columns = ("formid", "edid", "sig_field", "idx", "source", "dest", "status")
        self._tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "formid": _("FormID"),
            "edid": _("EditorID"),
            "sig_field": "Sig:Field",
            "idx": "Idx",
            "source": _("Source"),
            "dest": _("Dest"),
            "status": _("Status"),
        }
        widths = {"formid": 110, "edid": 170, "sig_field": 90, "idx": 55, "source": 220, "dest": 220, "status": 95}
        for column in columns:
            self._tree.heading(column, text=headings[column])
            self._tree.column(column, width=widths[column], minwidth=45, stretch=column in {"source", "dest"})

        y_scroll = AmberScrollbar(table_frame, orient="vertical", command=self._tree.yview, theme_name=self._theme.name)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Button-3>", self._on_context_menu)

        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(label=_("Copy source"), command=lambda: self._copy_selected("source"))
        self._context_menu.add_command(label=_("Copy dest"), command=lambda: self._copy_selected("dest"))
        self._context_menu.add_command(label=_("Copy row_id"), command=lambda: self._copy_selected("row_id"))
        self._context_menu.add_separator()
        self._context_menu.add_command(label=_("Show source/dest split view"), command=self._show_split_view)

    def _build_detail_pane(self) -> None:
        detail = ttk.Frame(self._paned, style="Surface.TFrame", padding=(8, 8))
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(0, weight=1)
        self._paned.add(detail, weight=2)
        self._detail_pane = detail

        self._detail_source_var = tk.StringVar(value="")
        self._detail_edid_var = tk.StringVar(value="")
        self._detail_rhash_var = tk.StringVar(value="")
        self._detail_status_var = tk.StringVar(value="untranslated")

        self._detail_paned = ttk.PanedWindow(detail, orient=tk.VERTICAL)
        self._detail_paned.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        source_frame = ttk.Frame(self._detail_paned, style="Surface.TFrame")
        dest_frame = ttk.Frame(self._detail_paned, style="Surface.TFrame")
        for frame in (source_frame, dest_frame):
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
        self._detail_paned.add(source_frame, weight=1)
        self._detail_paned.add(dest_frame, weight=1)

        ttk.Label(source_frame, text="源 / Source", style="Phosphor.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 3))
        self._source_text = self._make_detail_text(source_frame)
        source_scroll = AmberScrollbar(source_frame, orient="vertical", command=self._source_text.yview, theme_name=self._theme.name)
        self._source_text.configure(yscrollcommand=source_scroll.set, state="disabled")
        self._source_text.grid(row=1, column=0, sticky="nsew")
        source_scroll.grid(row=1, column=1, sticky="ns")

        ttk.Label(dest_frame, text="译 / Dest", style="Phosphor.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 3))
        self._dest_text = self._make_detail_text(dest_frame)
        dest_scroll = AmberScrollbar(dest_frame, orient="vertical", command=self._dest_text.yview, theme_name=self._theme.name)
        self._dest_text.configure(yscrollcommand=dest_scroll.set)
        self._dest_text.grid(row=1, column=0, sticky="nsew")
        dest_scroll.grid(row=1, column=1, sticky="ns")
        self.after_idle(self._set_initial_detail_sash)

        meta = ttk.Frame(detail, style="Surface.TFrame")
        meta.grid(row=1, column=0, sticky="ew")
        meta.columnconfigure(1, weight=1)

        ttk.Label(meta, text=f"{_('Status')}:", style="Phosphor.TLabel").grid(row=0, column=0, sticky="w")
        self._detail_status_combo = ttk.Combobox(
            meta, textvariable=self._detail_status_var, values=_STATUS_VALUES[1:], state="readonly", width=16
        )
        self._detail_status_combo.grid(row=0, column=1, sticky="w", pady=(0, 4))

        ttk.Label(meta, text="EDID:", style="Phosphor.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(meta, textvariable=self._detail_edid_var, style="Dim.TLabel").grid(row=1, column=1, sticky="ew")

        ttk.Label(meta, text="rHash:", style="Phosphor.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(meta, textvariable=self._detail_rhash_var, style="Dim.TLabel").grid(row=2, column=1, sticky="ew")

        buttons = ttk.Frame(meta, style="Surface.TFrame")
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text=_("Save edit"), command=self._on_save_edit).pack(side="left", padx=(0, 4))
        ttk.Button(buttons, text=_("Revert"), command=self._on_revert_detail).pack(side="left", padx=(0, 4))
        ttk.Button(buttons, text=_("Lock"), command=self._on_lock_selected).pack(side="left", padx=(0, 4))
        ttk.Button(buttons, text=_("Mark orphan"), command=self._on_mark_orphan).pack(side="left")

    def _make_detail_text(self, parent: tk.Misc) -> tk.Text:
        return tk.Text(
            parent,
            height=6,
            wrap="word",
            background=self._theme.background,
            foreground=self._theme.foreground,
            insertbackground=self._theme.foreground,
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self._theme.border,
            highlightcolor=self._theme.accent,
            font=("Consolas", 10),
        )

    def _set_initial_detail_sash(self) -> None:
        try:
            self._detail_paned.sashpos(0, max(120, self._detail_paned.winfo_height() // 2))  # type: ignore[no-untyped-call]
        except tk.TclError:
            pass

    def _on_row_select(self, _event: object) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        row_id = selection[0]
        unit = next((item for item in self._filtered_units if item["row_id"] == row_id), None)
        if unit is None:
            return
        self._selected_unit = unit
        self._detail_source_var.set(str(unit["source"]))
        self._detail_edid_var.set(str(unit.get("edid") or "-"))
        self._detail_rhash_var.set(str(unit.get("rhash") or "-"))
        self._detail_status_var.set(str(unit["status"]))
        self._set_source_text(str(unit["source"]))
        self._dest_text.delete("1.0", "end")
        self._dest_text.insert("1.0", str(unit.get("dest") or ""))

    def _on_filter_apply(self) -> None:
        project_root = self._get_project_root()
        if project_root is None:
            self.clear()
            return
        sig = self._signature_var.get()
        field = self._field_var.get()
        status = self._status_var.get()
        conn = open_memory_db(project_root)
        try:
            rows = select_units_filtered(
                conn,
                sigs=None if sig == "All" else [sig],
                fields=None if field == "All" else [field],
                statuses=None if status == "All" else [status],
                search=self._search_var.get(),
            )
            self._filtered_units = [self._unit_from_row(row) for row in rows]
        finally:
            conn.close()
        self._populate_table()
        self._show_empty_state(not self._filtered_units)

    def _on_save_edit(self) -> None:
        if self._selected_unit is None:
            return
        project_root = self._get_project_root()
        if project_root is None:
            return
        row_id = str(self._selected_unit["row_id"])
        dest = self._dest_text.get("1.0", "end-1c")
        status = self._detail_status_var.get()
        conn = open_memory_db(project_root)
        try:
            before = _get_unit_or_exit(conn, row_id)
            conn.execute("BEGIN")
            after = _apply_edit(conn, row_id, dest=dest, status=status)
            conn.commit()
            _append_audit(project_root, row_id=row_id, before=before, after=after, reason="GUI Entries tab edit")
        except (sqlite3.Error, RuntimeError) as exc:
            conn.rollback()
            messagebox.showerror(_("Save edit"), str(exc))
            return
        finally:
            conn.close()
        self._on_filter_apply()
        if self._tree.exists(row_id):
            self._tree.selection_set(row_id)
            self._tree.see(row_id)
            self._on_row_select(None)

    def _on_filter_reset(self) -> None:
        self._signature_var.set("All")
        self._field_var.set("All")
        self._status_var.set("All")
        self._search_var.set("")
        self._on_filter_apply()

    def _on_revert_detail(self) -> None:
        if self._selected_unit is None:
            return
        self._dest_text.delete("1.0", "end")
        self._dest_text.insert("1.0", str(self._selected_unit.get("dest") or ""))
        self._detail_status_var.set(str(self._selected_unit["status"]))

    def _on_lock_selected(self) -> None:
        self._detail_status_var.set("locked")
        self._on_save_edit()

    def _on_mark_orphan(self) -> None:
        self._detail_status_var.set("orphan")
        self._on_save_edit()

    def _on_context_menu(self, event: tk.Event[tk.Misc]) -> str:
        row_id = self._tree.identify_row(event.y)
        if row_id:
            self._tree.selection_set(row_id)
            self._on_row_select(None)
            self._context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _copy_selected(self, key: str) -> None:
        if self._selected_unit is None:
            return
        value = self._selected_unit["row_id"] if key == "row_id" else self._selected_unit.get(key)
        self.clipboard_clear()
        self.clipboard_append(str(value or ""))

    def _show_split_view(self) -> None:
        if self._selected_unit is None:
            return
        source = self._selected_unit.get("source") or ""
        dest = self._selected_unit.get("dest") or ""
        messagebox.showinfo(_("Show source/dest split view"), f"{_('Source')}: {source}\n\n{_('Dest')}: {dest}")

    def _refresh_filter_values(self) -> None:
        sigs = ["All", *sorted({str(unit["signature"]) for unit in self._all_units})]
        fields = ["All", *sorted({str(unit["field"]) for unit in self._all_units})]
        self._signature_combo.configure(values=tuple(sigs))
        self._field_combo.configure(values=tuple(fields))
        if self._project_name is not None:
            self._project_var.set(self._project_name)
            self._project_combo.configure(values=(self._project_name,))

    def _populate_table(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for unit in self._filtered_units:
            self._tree.insert(
                "",
                "end",
                iid=str(unit["row_id"]),
                values=(
                    unit["formid"],
                    unit.get("edid") or "-",
                    f"{unit['signature']}:{unit['field']}",
                    unit["idx"],
                    self._shorten(str(unit["source"])),
                    self._shorten(str(unit.get("dest") or "-")),
                    unit["status"],
                ),
            )

    def _clear_detail(self) -> None:
        self._detail_source_var.set("")
        self._detail_edid_var.set("")
        self._detail_rhash_var.set("")
        self._detail_status_var.set("untranslated")
        self._set_source_text("")
        self._dest_text.delete("1.0", "end")

    def _set_source_text(self, value: str) -> None:
        self._source_text.configure(state="normal")
        self._source_text.delete("1.0", "end")
        self._source_text.insert("1.0", value)
        self._source_text.configure(state="disabled")

    def _show_empty_state(self, show: bool) -> None:
        if show:
            self._empty_state.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._empty_state.lift()
        else:
            self._empty_state.place_forget()

    @staticmethod
    def _shorten(value: str, limit: int = 64) -> str:
        return value if len(value) <= limit else f"{value[: limit - 1]}…"

    @staticmethod
    def _unit_from_row(row: sqlite3.Row) -> dict[str, Any]:
        index_max = int(row["index_max"])
        index_n = int(row["index_n"])
        return {
            "row_id": row["row_id"],
            "plugin": row["plugin"],
            "formid": f"0x{int(row['formid']):08X}",
            "edid": row["edid"],
            "signature": row["signature"],
            "field": row["field"],
            "idx": f"{index_n}/{index_max}" if index_max else str(index_n),
            "source": row["source"],
            "dest": row["dest"],
            "status": row["status"],
            "rhash": f"0x{int(row['rhash']):08X}",
            "parent_context_json": row["parent_context_json"],
        }


__all__ = ["EntriesTab"]
