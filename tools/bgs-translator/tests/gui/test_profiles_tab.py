"""Profiles tab GUI regressions."""

from __future__ import annotations

import os
import tkinter as tk

import pytest


def _need_tk_runtime() -> None:
    if os.environ.get("CI"):
        pytest.skip("Tk dialog tests skipped under CI")
    try:
        tk.Tk().destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def test_set_api_key_dialog_uses_read_only_env_label() -> None:
    _need_tk_runtime()
    from bgs_translator.config.profiles import ProviderProfile
    from bgs_translator.gui.tabs.profiles_tab import SetApiKeyDialog

    root = tk.Tk()
    try:
        profile = ProviderProfile(
            name="openrouter",
            sdk_kind="openai-compat",
            base_url="https://openrouter.ai/api/v1",
            model="deepseek/deepseek-chat",
            api_key_env="BGS_TRANSLATOR_KEY_OPENROUTER",
            json_mode="json_schema",
        )
        dialog = SetApiKeyDialog(root, profile=profile)

        assert dialog.title() == (
            "Set API key for `openrouter` → env var `BGS_TRANSLATOR_KEY_OPENROUTER`"
        )
        assert dialog.env_var_value.cget("text") == "BGS_TRANSLATOR_KEY_OPENROUTER"
        assert dialog.env_var_value.cget("state") != "normal"
    finally:
        root.destroy()
