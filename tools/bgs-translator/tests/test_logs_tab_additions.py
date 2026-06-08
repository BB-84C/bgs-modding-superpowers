"""Tests for Logs tab additions."""

from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk logs tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_open_logs_folder_button_invokes_platform_opener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.gui.tabs.logs_tab import LogsTab

    opened: list[str] = []
    monkeypatch.setattr(LogsTab, "_open_path_in_explorer", staticmethod(lambda path: opened.append(str(path))))
    root = tk.Tk()
    try:
        tab = LogsTab(root)
        tab.open_logs_folder()
        assert opened == [str(tmp_path / "translator" / "logs")]
    finally:
        root.destroy()


def test_pause_resume_toggle_changes_label() -> None:
    _need_tk_runtime()
    from bgs_translator.gui.i18n import gettext as _
    from bgs_translator.gui.tabs.logs_tab import LogsTab

    root = tk.Tk()
    try:
        tab = LogsTab(root)
        assert tab.pause_button.cget("text") == _("Pause tail")
        tab.toggle_tail()
        assert tab.pause_button.cget("text") == _("Resume tail")
        tab.toggle_tail()
        assert tab.pause_button.cget("text") == _("Pause tail")
    finally:
        root.destroy()


def test_day_dropdown_navigates_selected_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    logs_root = tmp_path / "translator" / "logs"
    logs_root.mkdir(parents=True)
    day = "2026-06-06"
    (logs_root / f"{day}.log").write_text(
        json.dumps({"ts": "t", "level": "info", "source": "batch", "message": "selected day"}) + "\n",
        encoding="utf-8",
    )
    from bgs_translator.gui.tabs.logs_tab import LogsTab

    root = tk.Tk()
    try:
        tab = LogsTab(root)
        tab.day_var.set(day)
        tab.refresh()
        assert "selected day" in tab.text_content()
    finally:
        root.destroy()
