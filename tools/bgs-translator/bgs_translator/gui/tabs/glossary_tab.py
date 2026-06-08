"""Glossary tab with four-scope display and user override editing."""

from __future__ import annotations

import re
import sqlite3
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

from bgs_translator.config import paths
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.empty_state import EmptyStatePanel
from bgs_translator.kb._schema import apply_stub_schema
from bgs_translator.kb.models import GlossaryEntry
from bgs_translator.kb.reader import KBGlossaryReader

_SCOPE_LABELS: dict[str, str] = {
    "vanilla": "Vanilla",
    "mod": "Mod",
    "player": "Player",
    "do_not_translate": "DNT",
}
_WRITABLE_SCOPES = {"player", "do_not_translate"}
_CATEGORIES = ("", "character", "faction", "place", "item", "spell", "lore_term", "ui_label", "brand")
_CONFIDENCES = ("canonical", "preferred", "candidate")


def user_pack_db_path(user_packs_root: Path, source_lang: str = "en", target_lang: str = "zhcn") -> Path:
    """Return the translator override pack DB path, creating no files."""

    return user_packs_root / f"translator-overrides-{source_lang}-{target_lang}" / "kb.sqlite"


class GlossaryEntryDialog(tk.Toplevel):
    """Add/edit dialog for writable glossary scopes."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        scope: str,
        kb_root: Path | None = None,
        user_packs_root: Path | None = None,
        entry: GlossaryEntry | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title(_("Add glossary entry"))
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self._scope = scope
        self._entry = entry
        self._kb_root = kb_root or paths.kb_root()
        self._user_packs_root = user_packs_root or paths.kb_user_packs_root()
        self._on_saved = on_saved
        self.values: dict[str, tk.StringVar] = {
            "source": tk.StringVar(value=entry.source if entry else ""),
            "source_aliases": tk.StringVar(value=", ".join(entry.source_aliases) if entry else ""),
            "target": tk.StringVar(value=entry.target if entry else ""),
            "target_aliases": tk.StringVar(value=", ".join(entry.target_aliases) if entry else ""),
            "category": tk.StringVar(value=entry.category or "lore_term" if entry else "character"),
            "confidence": tk.StringVar(value=entry.confidence if entry else "preferred"),
            "notes": tk.StringVar(value=entry.notes or "" if entry else ""),
        }
        self.error_var = tk.StringVar(value="")

        body = ttk.Frame(self, padding=(14, 12))
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        rows = [
            (_("Source"), "source", "entry"),
            (_("Source aliases"), "source_aliases", "entry"),
            (_("Target"), "target", "entry"),
            (_("Target aliases"), "target_aliases", "entry"),
            (_("Category"), "category", "category"),
            (_("Confidence"), "confidence", "confidence"),
            (_("Notes"), "notes", "entry"),
        ]
        for row, (caption, key, kind) in enumerate(rows):
            ttk.Label(body, text=f"{caption}:", style="Dim.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            if kind == "category":
                ttk.Combobox(body, textvariable=self.values[key], values=_CATEGORIES[1:], state="readonly", width=28).grid(row=row, column=1, sticky="ew", pady=3)
            elif kind == "confidence":
                ttk.Combobox(body, textvariable=self.values[key], values=_CONFIDENCES, state="readonly", width=28).grid(row=row, column=1, sticky="ew", pady=3)
            else:
                ttk.Entry(body, textvariable=self.values[key], width=36).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Label(body, textvariable=self.error_var, style="Dim.TLabel").grid(row=len(rows), column=0, columnspan=2, sticky="w")
        buttons = ttk.Frame(body)
        buttons.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text=_("Save"), style="Accent.TButton", command=self.save).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text=_("Cancel"), command=self.destroy).pack(side="left")

    def save(self) -> bool:
        source = self.values["source"].get().strip()
        target = self.values["target"].get().strip()
        if not source:
            self.error_var.set(_("Source is required"))
            return False
        if not target and self._scope != "do_not_translate":
            self.error_var.set(_("Target is required"))
            return False
        db_path = user_pack_db_path(self._user_packs_root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            apply_stub_schema(conn)
            record_id = self._entry.record_id if self._entry else _next_record_id(conn, self._scope, source)
            pack_id = db_path.parent.name
            conn.execute(
                "INSERT OR REPLACE INTO records (id, pack_id, kind, title, body_md) VALUES (?, ?, 'glossary-entry', ?, ?)",
                (record_id, pack_id, source, self.values["notes"].get().strip() or None),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO glossary_entries (
                    record_id, source, source_lang, target, target_lang, scope,
                    scope_key, category, confidence, notes
                ) VALUES (?, ?, 'en', ?, 'zh-cn', ?, NULL, ?, ?, ?)
                """,
                (
                    record_id,
                    source,
                    target or source,
                    self._scope,
                    self.values["category"].get().strip() or None,
                    self.values["confidence"].get().strip() or "preferred",
                    self.values["notes"].get().strip() or None,
                ),
            )
            conn.execute("DELETE FROM glossary_aliases WHERE record_id = ?", (record_id,))
            for alias in _split_aliases(self.values["source_aliases"].get()):
                conn.execute("INSERT INTO glossary_aliases (record_id, alias, alias_kind) VALUES (?, ?, 'source')", (record_id, alias))
            for alias in _split_aliases(self.values["target_aliases"].get()):
                conn.execute("INSERT INTO glossary_aliases (record_id, alias, alias_kind) VALUES (?, ?, 'target')", (record_id, alias))
            conn.commit()
        finally:
            conn.close()
        if self._on_saved is not None:
            self._on_saved()
        self.destroy()
        return True


class GlossaryTab(ttk.Frame):
    """Four-scope glossary table with filter row."""

    def __init__(self, master: tk.Misc, *, kb_root: Path | None = None, user_packs_root: Path | None = None) -> None:
        super().__init__(master, padding=(12, 10))
        self._kb_root = kb_root or paths.kb_root()
        self._user_packs_root = user_packs_root or paths.kb_user_packs_root()
        self.scope_var = tk.StringVar(value="vanilla")
        self.game_var = tk.StringVar(value="")
        self.category_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")
        self._entries: list[GlossaryEntry] = []
        self._visible_entries: list[GlossaryEntry] = []

        ttk.Label(self, text=_("Glossary"), style="Phosphor.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        scope_row = ttk.Frame(self)
        scope_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(scope_row, text=f"{_('Scope')}:", style="Dim.TLabel").pack(side="left", padx=(0, 6))
        for value, caption in _SCOPE_LABELS.items():
            ttk.Radiobutton(scope_row, text=_(caption), value=value, variable=self.scope_var, command=self.refresh).pack(side="left", padx=(0, 8))

        filters = ttk.Frame(self)
        filters.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(filters, text=f"{_('Game')}:", style="Dim.TLabel").pack(side="left")
        ttk.Entry(filters, textvariable=self.game_var, width=14).pack(side="left", padx=(4, 10))
        ttk.Label(filters, text=f"{_('Category')}:", style="Dim.TLabel").pack(side="left")
        ttk.Combobox(filters, textvariable=self.category_var, values=_CATEGORIES, width=14, state="readonly").pack(side="left", padx=(4, 10))
        ttk.Label(filters, text=f"{_('Search')}:", style="Dim.TLabel").pack(side="left")
        ttk.Entry(filters, textvariable=self.search_var, width=24).pack(side="left", padx=(4, 10))
        ttk.Button(filters, text=_("Filter"), command=self.refresh).pack(side="left")

        table_frame = ttk.Frame(self)
        table_frame.grid(row=3, column=0, sticky="nsew")
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("source", "target", "aliases", "category", "pack", "confidence")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        headings = {
            "source": _("Source"),
            "target": _("Target"),
            "aliases": _("Aliases"),
            "category": _("Category"),
            "pack": _("Pack"),
            "confidence": _("Confidence"),
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=130, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = AmberScrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self._empty_state = EmptyStatePanel(
            table_frame,
            caption=_("[ NO GLOSSARY LOADED ]"),
            sub_line=_("Install a pack OR add player entries with [Add]"),
        )
        self._empty_state.grid(row=0, column=0, columnspan=2, sticky="nsew")

        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.add_button = ttk.Button(actions, text=_("Add entry"), command=self._on_add)
        self.edit_button = ttk.Button(actions, text=_("Edit entry"), command=self._on_edit)
        self.delete_button = ttk.Button(actions, text=_("Delete entry"), command=self._on_delete)
        self.add_button.pack(side="left", padx=(0, 6))
        self.edit_button.pack(side="left", padx=(0, 6))
        self.delete_button.pack(side="left")

        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        self._entries = _load_all_entries(self._kb_root, self._user_packs_root)
        self._visible_entries = self._filter_entries(self._entries)
        for row in self.tree.get_children():
            self.tree.delete(row)
        for entry in self._visible_entries:
            aliases = ", ".join([*entry.source_aliases, *entry.target_aliases])
            self.tree.insert("", "end", iid=entry.record_id, values=(entry.source, entry.target, aliases, entry.category or "", entry.pack_id, entry.confidence))
        if self._visible_entries:
            self._empty_state.lower()
        else:
            self._empty_state.lift()
        self._update_action_visibility()

    def visible_entries(self) -> list[GlossaryEntry]:
        return list(self._visible_entries)

    def _filter_entries(self, entries: list[GlossaryEntry]) -> list[GlossaryEntry]:
        scope = self.scope_var.get()
        game = self.game_var.get().strip()
        category = self.category_var.get().strip()
        search = self.search_var.get().strip().casefold()
        filtered: list[GlossaryEntry] = []
        for entry in entries:
            if entry.scope != scope:
                continue
            if game and entry.games and game not in entry.games:
                continue
            if category and entry.category != category:
                continue
            if search:
                haystack = " ".join([entry.source, entry.target, *entry.source_aliases, *entry.target_aliases]).casefold()
                if search not in haystack:
                    continue
            filtered.append(entry)
        return filtered

    def _update_action_visibility(self) -> None:
        writable = self.scope_var.get() in _WRITABLE_SCOPES
        for button in (self.add_button, self.edit_button, self.delete_button):
            if writable:
                button.pack(side="left", padx=(0, 6))
            else:
                button.pack_forget()
        self.update_idletasks()

    def _on_add(self) -> None:
        GlossaryEntryDialog(self, scope=self.scope_var.get(), kb_root=self._kb_root, user_packs_root=self._user_packs_root, on_saved=self.refresh)

    def _selected_entry(self) -> GlossaryEntry | None:
        selection = self.tree.selection()
        if not selection:
            return None
        selected_id = selection[0]
        return next((entry for entry in self._visible_entries if entry.record_id == selected_id), None)

    def _on_edit(self) -> None:
        entry = self._selected_entry()
        if entry is not None and entry.scope in _WRITABLE_SCOPES:
            GlossaryEntryDialog(self, scope=entry.scope, kb_root=self._kb_root, user_packs_root=self._user_packs_root, entry=entry, on_saved=self.refresh)

    def _on_delete(self) -> None:
        entry = self._selected_entry()
        if entry is None or entry.scope not in _WRITABLE_SCOPES:
            return
        db_path = user_pack_db_path(self._user_packs_root)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("DELETE FROM glossary_aliases WHERE record_id = ?", (entry.record_id,))
            conn.execute("DELETE FROM record_games WHERE record_id = ?", (entry.record_id,))
            conn.execute("DELETE FROM glossary_entries WHERE record_id = ?", (entry.record_id,))
            conn.execute("DELETE FROM records WHERE id = ?", (entry.record_id,))
            conn.commit()
        finally:
            conn.close()
        self.refresh()


def _load_all_entries(kb_root: Path, user_packs_root: Path) -> list[GlossaryEntry]:
    reader = KBGlossaryReader(kb_root=kb_root, user_packs_root=user_packs_root)
    try:
        dbs = [*reader.pack_dbs, *reader.user_pack_dbs]
    finally:
        reader.close()
    deduped: dict[str, GlossaryEntry] = {}
    for pack_id, db_path in dbs:
        for entry in _read_pack_entries(pack_id, db_path):
            deduped[entry.record_id] = entry
    return sorted(deduped.values(), key=lambda entry: (entry.scope, entry.source.casefold(), entry.record_id))


def _read_pack_entries(pack_id: str, db_path: Path) -> list[GlossaryEntry]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ge.*, r.pack_id AS row_pack_id
            FROM glossary_entries ge
            JOIN records r ON r.id = ge.record_id
            WHERE r.kind = 'glossary-entry'
            ORDER BY ge.source
            """
        ).fetchall()
        entries: list[GlossaryEntry] = []
        for row in rows:
            record_id = str(row["record_id"])
            entries.append(
                GlossaryEntry(
                    record_id=record_id,
                    source=str(row["source"]),
                    source_aliases=_aliases(conn, record_id, "source"),
                    source_lang=str(row["source_lang"]),
                    target=str(row["target"]),
                    target_aliases=_aliases(conn, record_id, "target"),
                    target_lang=str(row["target_lang"]),
                    scope=row["scope"],
                    scope_key=row["scope_key"],
                    category=row["category"],
                    confidence=row["confidence"],
                    notes=row["notes"],
                    pack_id=str(row["row_pack_id"] or pack_id),
                    games=_games(conn, record_id),
                )
            )
        return entries
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _aliases(conn: sqlite3.Connection, record_id: str, alias_kind: str) -> list[str]:
    rows = conn.execute("SELECT alias FROM glossary_aliases WHERE record_id = ? AND alias_kind = ? ORDER BY rowid", (record_id, alias_kind)).fetchall()
    return [str(row[0]) for row in rows]


def _games(conn: sqlite3.Connection, record_id: str) -> list[str]:
    rows = conn.execute("SELECT game FROM record_games WHERE record_id = ? ORDER BY game", (record_id,)).fetchall()
    return [str(row[0]) for row in rows]


def _split_aliases(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]


def _next_record_id(conn: sqlite3.Connection, scope: str, source: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", source.casefold()).strip("-") or "entry"
    base = f"translator.override.{scope}.{slug}"
    record_id = base
    counter = 2
    while conn.execute("SELECT 1 FROM records WHERE id = ?", (record_id,)).fetchone() is not None:
        record_id = f"{base}.{counter}"
        counter += 1
    return record_id


__all__ = ["GlossaryEntryDialog", "GlossaryTab", "user_pack_db_path"]
