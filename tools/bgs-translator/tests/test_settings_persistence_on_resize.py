"""Settings persistence when window state changes."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk settings-persistence tests skipped under CI")
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_configure_debounce_persists_window_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.settings import load_settings
    from bgs_translator.gui.app import TranslatorApp

    app = TranslatorApp()
    try:
        app.geometry("1111x777+20+20")
        app.update_idletasks()
        app.event_generate("<Configure>", width=1111, height=777)
        app.after(260, app.quit)
        app.mainloop()

        settings = load_settings()
        assert settings.ui.window_width == 1111
        assert settings.ui.window_height == 777
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
