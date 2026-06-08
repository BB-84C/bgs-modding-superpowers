"""GUI smoke tests for app-level Prompt tab routing."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk app GUI tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_preview_event_selects_prompt_tab_and_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path / "home"))

    from bgs_translator.core.event_queue import GuiEvent
    from bgs_translator.core.ipc import IPCServer
    from bgs_translator.gui.app import TranslatorApp

    monkeypatch.setattr(IPCServer, "start", lambda self: None)
    monkeypatch.setattr(IPCServer, "stop", lambda self: None)

    app = TranslatorApp()
    try:
        event = GuiEvent(
            kind="prompt.preview_request",
            batch_id="batch-42",
            payload={"batch_id": "batch-42", "prompt": "System prompt"},
        )
        app._bridge.emit(event)
        for drained in app._bridge.drain():
            app._dispatch_event(drained)
        app.update_idletasks()

        assert app.notebook.select() == str(app._tabs["prompt"])  # type: ignore[no-untyped-call]
        assert app._prompt_tab.batch_combo.get() == "batch-42"
    finally:
        app.destroy()
