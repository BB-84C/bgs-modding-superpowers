"""Tests for profile API key resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _profile() -> object:
    from bgs_translator.config.profiles import ProviderProfile

    return ProviderProfile(
        name="openai-prod",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
    )


def test_resolve_api_key_returns_env_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    env_path = tmp_path / "translator" / "profiles" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("BGS_TRANSLATOR_KEY_OPENAI=sk-test\n", encoding="utf-8")
    if os.name != "nt":
        env_path.chmod(0o600)

    from bgs_translator.config.profiles import resolve_api_key

    assert resolve_api_key(_profile()) == "sk-test"


def test_resolve_api_key_missing_var_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    env_path = tmp_path / "translator" / "profiles" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("OTHER=sk-test\n", encoding="utf-8")
    if os.name != "nt":
        env_path.chmod(0o600)

    from bgs_translator.config.profiles import ProfileMissingKeyError, resolve_api_key

    with pytest.raises(ProfileMissingKeyError):
        resolve_api_key(_profile())


@pytest.mark.skipif(os.name == "nt", reason="POSIX chmod semantics are not available on Windows")
def test_resolve_api_key_refuses_insecure_posix_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    env_path = tmp_path / "translator" / "profiles" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("BGS_TRANSLATOR_KEY_OPENAI=sk-test\n", encoding="utf-8")
    env_path.chmod(0o644)

    from bgs_translator.config.profiles import ProfileMissingKeyError, resolve_api_key

    with pytest.raises(ProfileMissingKeyError, match="world-readable"):
        resolve_api_key(_profile())
