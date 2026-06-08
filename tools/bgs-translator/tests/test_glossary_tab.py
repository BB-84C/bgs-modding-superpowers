"""Tests for the Glossary tab implementation."""

from __future__ import annotations

import os
import sqlite3
import tkinter as tk
from pathlib import Path

import pytest
from conftest import PackFactory


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk glossary tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_glossary_tab_loads_fixture_pack_and_filters(
    tmp_path: Path, make_fixture_pack: PackFactory
) -> None:
    _need_tk_runtime()
    make_fixture_pack(
        "bgs-kb-l10n-skyrim-en-zhcn",
        [
            {"record_id": "whiterun", "source": "Whiterun", "target": "白漫城", "category": "place", "games": ["SkyrimSE"]},
            {"record_id": "daedra", "source": "Daedra", "target": "迪德拉", "category": "lore_term", "games": ["SkyrimSE"]},
        ],
    )
    from bgs_translator.gui.tabs.glossary_tab import GlossaryTab

    root = tk.Tk()
    try:
        tab = GlossaryTab(root, kb_root=tmp_path, user_packs_root=tmp_path / "user-packs")
        tab.scope_var.set("vanilla")
        tab.game_var.set("SkyrimSE")
        tab.category_var.set("place")
        tab.search_var.set("White")
        tab.refresh()
        rows = tab.visible_entries()
        assert [entry.source for entry in rows] == ["Whiterun"]
        assert not tab.add_button.winfo_ismapped()
    finally:
        root.destroy()


def test_player_scope_add_dialog_persists_user_pack_entry(tmp_path: Path) -> None:
    _need_tk_runtime()
    from bgs_translator.gui.tabs.glossary_tab import GlossaryEntryDialog, user_pack_db_path

    root = tk.Tk()
    try:
        dialog = GlossaryEntryDialog(
            root,
            scope="player",
            kb_root=tmp_path,
            user_packs_root=tmp_path / "user-packs",
        )
        dialog.values["source"].set("Whiterun")
        dialog.values["source_aliases"].set("Whiterun's")
        dialog.values["target"].set("白漫城")
        dialog.values["target_aliases"].set("雪漫")
        dialog.values["category"].set("place")
        dialog.values["confidence"].set("preferred")
        assert dialog.save()
    finally:
        root.destroy()

    db_path = user_pack_db_path(tmp_path / "user-packs")
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT source, target, scope FROM glossary_entries").fetchone()
        aliases = conn.execute("SELECT alias FROM glossary_aliases ORDER BY alias_kind, alias").fetchall()
    finally:
        conn.close()
    assert row == ("Whiterun", "白漫城", "player")
    assert {alias[0] for alias in aliases} == {"Whiterun's", "雪漫"}
