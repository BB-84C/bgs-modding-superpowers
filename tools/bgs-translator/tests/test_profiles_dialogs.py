"""Tests for Profiles tab dialog behavior."""

from __future__ import annotations

import os
import subprocess
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


def test_add_profile_dialog_validates_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import ProfilesConfig, load_profiles
    from bgs_translator.gui.tabs.profiles_tab import ProfileDialog

    root = tk.Tk()
    try:
        dialog = ProfileDialog(root, title="Add new provider profile", config=ProfilesConfig())
        dialog.values["name"].set("openai-prod")
        dialog.values["sdk_kind"].set("openai")
        dialog.values["base_url"].set("https://api.openai.com/v1")
        dialog.values["model"].set("gpt-5-mini")
        dialog.values["api_key_env"].set("BGS_TRANSLATOR_KEY_OPENAI")
        assert dialog.save()
        loaded = load_profiles()
        assert loaded.profiles["openai-prod"].model == "gpt-5-mini"
    finally:
        root.destroy()


def test_add_profile_dialog_invalid_env_shows_error_no_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import ProfilesConfig, load_profiles
    from bgs_translator.gui.tabs.profiles_tab import ProfileDialog

    root = tk.Tk()
    try:
        dialog = ProfileDialog(root, title="Add new provider profile", config=ProfilesConfig())
        dialog.values["name"].set("bad")
        dialog.values["sdk_kind"].set("openai")
        dialog.values["base_url"].set("https://api.openai.com/v1")
        dialog.values["model"].set("gpt-5-mini")
        dialog.values["api_key_env"].set("lowercase")
        assert not dialog.save()
        assert "api_key_env" in dialog.error_var.get()
        assert load_profiles().profiles == {}
    finally:
        root.destroy()


def test_edit_profile_dialog_updates_existing_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import (
        ProfilesConfig,
        ProviderProfile,
        load_profiles,
        save_profiles,
    )
    from bgs_translator.gui.tabs.profiles_tab import ProfileDialog

    cfg = ProfilesConfig(
        profiles={
            "openai-prod": ProviderProfile(
                name="openai-prod",
                sdk_kind="openai",
                base_url="https://api.openai.com/v1",
                model="old-model",
                api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
            )
        }
    )
    save_profiles(cfg)

    root = tk.Tk()
    try:
        dialog = ProfileDialog(
            root,
            title="Edit provider profile",
            config=load_profiles(),
            profile=load_profiles().profiles["openai-prod"],
        )
        dialog.values["model"].set("gpt-5-mini")
        assert dialog.save()
        assert load_profiles().profiles["openai-prod"].model == "gpt-5-mini"
    finally:
        root.destroy()


def test_profiles_tab_delete_confirmation_updates_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import (
        ProfilesConfig,
        ProviderProfile,
        load_profiles,
        save_profiles,
    )
    from bgs_translator.gui.tabs.profiles_tab import ProfilesTab

    save_profiles(
        ProfilesConfig(
            active="openai-prod",
            profiles={
                "openai-prod": ProviderProfile(
                    name="openai-prod",
                    sdk_kind="openai",
                    base_url="https://api.openai.com/v1",
                    model="gpt-5-mini",
                    api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
                )
            },
        )
    )
    root = tk.Tk()
    try:
        tab = ProfilesTab(root)
        tab.delete_profile("openai-prod", confirm=True)
        loaded = load_profiles()
        assert loaded.profiles == {}
        assert loaded.active is None
    finally:
        root.destroy()


def test_probe_button_invokes_subprocess_and_populates_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _need_tk_runtime()
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.gui.tabs.profiles_tab import ProfilesTab

    save_profiles(
        ProfilesConfig(
            profiles={
                "openai-prod": ProviderProfile(
                    name="openai-prod",
                    sdk_kind="openai",
                    base_url="https://api.openai.com/v1",
                    model="gpt-5-mini",
                    api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
                )
            }
        )
    )
    called: list[list[str]] = []

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        called.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="Connection successful\nModel verified", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    root = tk.Tk()
    try:
        tab = ProfilesTab(root)
        tab.probe_profile("openai-prod")
        assert called and called[0][-3:] == ["profile", "probe", "openai-prod"]
        assert "Connection successful" in tab.probe_result_var.get()
    finally:
        root.destroy()
