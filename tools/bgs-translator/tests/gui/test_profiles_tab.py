"""Profiles tab GUI regressions."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path

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


def test_profile_dialog_strips_endpoint_suffix_from_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import ProfilesConfig, load_profiles
    from bgs_translator.gui.tabs.profiles_tab import ProfileDialog

    root = tk.Tk()
    try:
        dialog = ProfileDialog(root, title="Add new provider profile", config=ProfilesConfig())
        dialog.values["name"].set("openrouter")
        dialog.values["sdk_kind"].set("openai-compat")
        dialog.values["base_url"].set("https://openrouter.ai/api/v1/chat/completions")
        dialog.values["model"].set("deepseek/deepseek-chat")
        dialog.values["api_key_env"].set("BGS_TRANSLATOR_KEY_OPENROUTER")
        dialog.values["json_mode"].set("json_schema")

        assert dialog.save()

        profile = load_profiles().profiles["openrouter"]
        assert profile.base_url == "https://openrouter.ai/api/v1"
    finally:
        root.destroy()
