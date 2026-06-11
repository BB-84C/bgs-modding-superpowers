"""Tests for provider profile loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_load_empty_profiles_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    from bgs_translator.config.profiles import load_profiles

    cfg = load_profiles()

    assert cfg.schema_version == 1
    assert cfg.active is None
    assert cfg.profiles == {}


def test_save_then_load_profiles_roundtrips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    from bgs_translator.config.profiles import (
        ProfilesConfig,
        ProviderProfile,
        load_profiles,
        save_profiles,
    )

    cfg = ProfilesConfig(
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

    save_profiles(cfg)
    loaded = load_profiles()

    assert loaded.active == "openai-prod"
    assert loaded.profiles["openai-prod"].model == "gpt-5-mini"


def test_api_key_env_must_be_uppercase_env_name() -> None:
    from pydantic import ValidationError

    from bgs_translator.config.profiles import ProviderProfile

    with pytest.raises(ValidationError):
        ProviderProfile(
            name="bad",
            sdk_kind="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-5-mini",
            api_key_env="lowercase_key",
        )


def test_load_rejects_literal_key_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    profiles_path = tmp_path / "translator" / "profiles" / "profiles.toml"
    profiles_path.parent.mkdir(parents=True)
    profiles_path.write_text(
        """
schema_version = 1

[profiles.bad]
sdk_kind = "openai"
base_url = "https://api.openai.com/v1"
model = "gpt-5-mini"
api_key_env = "BGS_TRANSLATOR_KEY_OPENAI"
key = "sk-real-key"
""".strip(),
        encoding="utf-8",
    )

    from bgs_translator.config.profiles import ProfileValidationError, load_profiles

    with pytest.raises(ProfileValidationError, match="literal API key"):
        load_profiles()


def test_deepseek_json_schema_guard() -> None:
    from pydantic import ValidationError

    from bgs_translator.config.profiles import ProviderProfile

    with pytest.raises(ValidationError, match="DeepSeek"):
        ProviderProfile(
            name="deepseek",
            sdk_kind="openai-compat",
            base_url="https://api.deepseek.com",
            model="deepseek-chat",
            api_key_env="BGS_TRANSLATOR_KEY_DEEPSEEK",
            json_mode="json_schema",
        )


def test_openai_compat_requires_json_mode() -> None:
    from pydantic import ValidationError

    from bgs_translator.config.profiles import ProviderProfile

    with pytest.raises(ValidationError, match="json_mode"):
        ProviderProfile(
            name="compat",
            sdk_kind="openai-compat",
            base_url="https://openrouter.ai/api/v1",
            model="anthropic/claude",
            api_key_env="BGS_TRANSLATOR_KEY_OPENROUTER",
        )
