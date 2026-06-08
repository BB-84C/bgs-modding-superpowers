"""GUI smoke tests for prompt tab polish."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from typing import Any

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk prompt GUI tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def _make_prompt_tab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[tk.Tk, Any]:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path / "home"))

    from bgs_translator.gui.tabs.prompt_tab import PromptTab

    root = tk.Tk()
    tab = PromptTab(root, project_root_provider=lambda: None, theme="amber")
    tab.pack(fill="both", expand=True)
    root.update_idletasks()
    return root, tab


def test_prompt_preview_required_checkbox_present_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.config.settings import load_settings

    root, tab = _make_prompt_tab(tmp_path, monkeypatch)
    try:
        assert tab._preview_required_checkbox.winfo_manager() == "grid"
        assert tab._preview_required_checkbox.value is False

        tab._preview_required_checkbox.value = True
        tab._on_preview_required_toggled()

        assert load_settings().behavior.prompt_preview_required is True
    finally:
        root.destroy()


def test_prompt_side_panel_hidden_without_selected_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, tab = _make_prompt_tab(tmp_path, monkeypatch)
    try:
        assert tab._side_panel.winfo_manager() == ""
    finally:
        root.destroy()


def test_prompt_side_panels_render_only_non_empty_batch_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, tab = _make_prompt_tab(tmp_path, monkeypatch)
    try:
        tab._batch_prompt_by_id["b1"] = "Prompt"
        tab._batch_payload_by_id["b1"] = {
            "glossary_subset": [{"source": "Constellation", "target": "群星组织"}],
            "dnt_terms": ["%PLAYER%"],
        }

        tab.render_prompt_for_batch("b1")

        assert tab._glossary_panel.winfo_manager() == "grid"
        assert tab._dnt_panel.winfo_manager() == "grid"
        assert "Constellation → 群星组织" in tab._glossary_text.get("1.0", "end-1c")
        assert "%PLAYER%" in tab._dnt_text.get("1.0", "end-1c")

        tab._batch_prompt_by_id["b2"] = "Prompt"
        tab._batch_payload_by_id["b2"] = {}
        tab.render_prompt_for_batch("b2")

        assert tab._side_panel.winfo_manager() == ""
    finally:
        root.destroy()
