"""Tests for settings persistence."""

from __future__ import annotations

import logging

import pytest


def test_load_defaults_when_missing(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.settings import Settings, load_settings

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    assert load_settings() == Settings()


def test_save_then_load_roundtrip(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.settings import Settings, UiSettings, load_settings, save_settings

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    settings = Settings(ui=UiSettings(language="zh-cn", theme="green"))

    save_settings(settings)

    assert load_settings() == settings


def test_update_setting_simple(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.settings import update_setting

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    updated = update_setting("ui.theme", "green")

    assert updated.ui.theme == "green"


def test_update_setting_validation(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.settings import update_setting

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    with pytest.raises(ValueError, match="Invalid value"):
        update_setting("ui.theme", "purple")


def test_update_setting_nested(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.config.settings import update_setting

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    updated = update_setting("behavior.prompt_preview_required", True)

    assert updated.behavior.prompt_preview_required is True


def test_schema_version_warning_on_mismatch(monkeypatch, tmp_path, caplog) -> None:  # type: ignore[no-untyped-def]
    import tomli_w

    from bgs_translator.config import paths
    from bgs_translator.config.settings import load_settings

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    settings_path = paths.settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(tomli_w.dumps({"schema_version": 99, "ui": {"theme": "mono"}}))

    with caplog.at_level(logging.WARNING):
        loaded = load_settings()

    assert loaded.ui.theme == "mono"
    assert "Unsupported settings schema_version" in caplog.text
