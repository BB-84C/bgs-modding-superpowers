"""Prompt tab behavior tests."""

from __future__ import annotations

import os
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    bool(os.environ.get("CI")),
    reason="Prompt tab tests skipped under CI (no Tk runtime guaranteed)",
)


def _need_tk_runtime() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


class _FakeIPC:
    def __init__(self) -> None:
        self.responses: list[tuple[str, str, str, bool]] = []

    def respond(
        self, batch_id: str, op: str, prompt: str | None = None, *, approve_all: bool = False
    ) -> None:
        self.responses.append((batch_id, op, prompt or "", approve_all))


def _make_tab() -> tuple[Any, Any, Any, Any]:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.core.event_queue import EventQueueBridge
    from bgs_translator.gui.tabs.prompt_tab import PromptTab
    from bgs_translator.gui.themes import AMBER_THEME, apply_theme

    root = tk.Tk()
    apply_theme(root, AMBER_THEME, "Consolas", 11)
    bridge = EventQueueBridge()
    ipc = _FakeIPC()
    tab = PromptTab(
        root,
        project_root_provider=lambda: None,
        theme="amber",
        gui_event_bridge=bridge,
        ipc_server=ipc,
    )
    tab.pack(fill="both", expand=True)
    root.update_idletasks()
    return root, tab, bridge, ipc


def test_render_sample_prompt_with_slot_values_populates_editor() -> None:
    root, tab, _bridge, _ipc = _make_tab()
    try:
        tab.render_sample_prompt(
            {
                "game_lore_world": "Starfield Settled Systems",
                "game_context_lore_summary": "NASA-punk frontier.",
                "mod_context_name": "RYOS",
                "mod_context_theme": "Alternate starts.",
                "style_directives": "Matter-of-fact UI Chinese.",
                "glossary_subset_rendered": "Whiterun → 白漫城 (place)",
                "do_not_translate_list": "EnaiSiaion",
            }
        )

        text = tab._editor.get("1.0", "end-1c")
        assert "Starfield Settled Systems" in text
        assert "RYOS" in text
        assert "Whiterun → 白漫城" in text
    finally:
        root.destroy()


def test_editable_toggle_controls_text_state() -> None:
    root, tab, _bridge, _ipc = _make_tab()
    try:
        assert str(tab._editor.cget("state")) == "disabled"
        tab._editable.set(True)
        tab._on_editable_toggled()
        assert str(tab._editor.cget("state")) == "normal"
        tab._editor.insert("end", "manual edit")
        assert "manual edit" in tab._editor.get("1.0", "end-1c")
    finally:
        root.destroy()


def test_approve_buttons_hidden_without_pending_preview() -> None:
    root, tab, _bridge, _ipc = _make_tab()
    try:
        assert not tab._action_row.winfo_ismapped()
    finally:
        root.destroy()


def test_preview_event_shows_buttons_and_approve_responds() -> None:
    root, tab, bridge, ipc = _make_tab()
    try:
        from bgs_translator.core.event_queue import GuiEvent

        bridge.emit(
            GuiEvent(
                kind="prompt.preview_request",  # type: ignore[arg-type]
                batch_id="b42",
                payload={
                    "prompt": "Prompt with {{P0}} and ${slot_name}",
                    "items": [{"source": "Iron Sword"}],
                    "glossary_subset": [
                        {"source": "Whiterun", "target": "白漫城", "category": "place", "confidence": "canon"}
                    ],
                    "do_not_translate": ["%s"],
                },
            )
        )
        bridge.drain()
        root.update_idletasks()

        assert tab._action_row.winfo_ismapped()
        assert "Prompt with" in tab._editor.get("1.0", "end-1c")
        assert "Whiterun → 白漫城" in tab._glossary_text.get("1.0", "end-1c")
        assert "- %s" in tab._dnt_text.get("1.0", "end-1c")

        tab._approve_button.invoke()

        assert ipc.responses == [("b42", "approved", "Prompt with {{P0}} and ${slot_name}", False)]
        assert not tab._action_row.winfo_ismapped()
    finally:
        root.destroy()
