"""Tests for the Entries tab implementation."""

from __future__ import annotations

from pathlib import Path

import pytest


def _need_tk_runtime() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def _build_memory(project_root: Path) -> str:
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = open_memory_db(project_root)
    units: list[TranslationUnit] = []
    for sig in ("MESG", "WEAP", "ARMO"):
        for idx in range(5):
            units.append(
                TranslationUnit(
                    "Sample.esm",
                    int(f"{len(units) + 1:X}", 16),
                    len(units) + 1,
                    f"{sig}_Edid_{idx}",
                    sig,
                    "FULL" if idx % 2 == 0 else "DESC",
                    source=f"{sig} source {idx}",
                    index_n=idx,
                    index_max=4,
                )
            )
    insert_units(conn, units)
    first_row_id = str(conn.execute("SELECT row_id FROM units ORDER BY row_id LIMIT 1").fetchone()[0])
    conn.execute("UPDATE units SET status = 'translated', dest = '已翻译' WHERE signature = 'WEAP'")
    conn.execute("UPDATE units SET status = 'partial', dest = '部分' WHERE signature = 'ARMO'")
    conn.commit()
    conn.close()
    return first_row_id


def test_entries_tab_filters_by_signature_and_status(tmp_path: Path) -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.tabs.entries_tab import EntriesTab

    _build_memory(tmp_path)
    root = tk.Tk()
    try:
        tab = EntriesTab(root, project_root_provider=lambda: tmp_path)
        tab.load_project("sample")

        tab._signature_var.set("MESG")
        tab._on_filter_apply()
        assert len(tab._tree.get_children()) == 5
        assert {tab._tree.set(iid, "sig_field") for iid in tab._tree.get_children()} == {
            "MESG:DESC",
            "MESG:FULL",
        }

        tab._signature_var.set("All")
        tab._status_var.set("untranslated")
        tab._on_filter_apply()
        assert len(tab._tree.get_children()) == 5
        assert {tab._tree.set(iid, "status") for iid in tab._tree.get_children()} == {
            "untranslated"
        }
    finally:
        root.destroy()


def test_entries_tab_row_click_populates_detail_and_save_updates_memory(tmp_path: Path) -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.core.memory import open_memory_db
    from bgs_translator.gui.tabs.entries_tab import EntriesTab

    row_id = _build_memory(tmp_path)
    root = tk.Tk()
    try:
        tab = EntriesTab(root, project_root_provider=lambda: tmp_path)
        tab.load_project("sample")
        tab._tree.selection_set(row_id)
        tab._on_row_select(None)

        assert "source" in tab._detail_source_var.get()
        assert tab._detail_edid_var.get()

        tab._dest_text.delete("1.0", "end")
        tab._dest_text.insert("1.0", "新译文")
        tab._detail_status_var.set("translated")
        tab._on_save_edit()

        conn = open_memory_db(tmp_path)
        try:
            row = conn.execute("SELECT dest, status FROM units WHERE row_id = ?", (row_id,)).fetchone()
            assert row == ("新译文", "translated")
        finally:
            conn.close()
        assert tab._tree.set(row_id, "dest") == "新译文"
    finally:
        root.destroy()
