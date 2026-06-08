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


def test_preview_event_shows_approve_action_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: live preview events must NOT race the approve UI off-screen.

    _on_gui_event shows the action row; _focus_prompt_preview used to call
    refresh_for_batch which hid it again immediately. That race meant the
    user never saw the Approve / Approve-all / Discard buttons, and the
    CLI worker stayed blocked in IPC.wait() forever.
    """

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
            batch_id="batch-99",
            payload={
                "batch_id": "batch-99",
                "prompt": "System prompt body",
                "glossary_subset": [],
                "do_not_translate": [],
            },
        )
        app._bridge.emit(event)
        for drained in app._bridge.drain():
            app._dispatch_event(drained)
        app.update_idletasks()

        # After the full drain + dispatch cycle, the action row's geometry
        # manager must still hold its slot. Tk's grid_remove() clears
        # grid_info(); grid() restores it. We can't rely on
        # winfo_ismapped() under headless test conditions where the root
        # window itself is not mapped (overrideredirect + withdraw),
        # but grid_info() reflects intent independently of mapping.
        info = app._prompt_tab._action_row.grid_info()
        assert info, (
            f"approve action row was hidden after preview event; grid_info={info!r}"
        )
        # The editor must carry the prompt body delivered by the event.
        editor_text = app._prompt_tab._editor.get("1.0", "end-1c").strip()
        assert "System prompt body" in editor_text
    finally:
        app.destroy()
