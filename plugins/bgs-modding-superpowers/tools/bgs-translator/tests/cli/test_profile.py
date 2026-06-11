"""Profile CLI regression tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner


def _add_openai_profile(runner: CliRunner, app: Any, *, base_url: str = "https://api.openai.com/v1") -> None:
    result = runner.invoke(
        app,
        [
            "profile",
            "add",
            "openai-prod",
            "--sdk-kind",
            "openai",
            "--base-url",
            base_url,
            "--model",
            "gpt-5-mini",
            "--api-key-env",
            "BGS_TRANSLATOR_KEY_OPENAI",
        ],
    )
    assert result.exit_code == 0, result.output


def test_probe_missing_key_hard_fails_without_client_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app

    runner = CliRunner()
    _add_openai_profile(runner, app)

    result = runner.invoke(app, ["profile", "probe", "openai-prod"])

    assert result.exit_code != 0
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "missing_api_key"
    assert (
        envelope["error"]["message"]
        == "Profile openai-prod requires env var BGS_TRANSLATOR_KEY_OPENAI in profiles/.env; "
        "set it via `xtl profile set-key` or the GUI."
    )


def test_add_profile_strips_chat_completions_endpoint_from_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.config.profiles import load_profiles

    runner = CliRunner()
    _add_openai_profile(runner, app, base_url="https://openrouter.ai/api/v1/chat/completions")

    profile = load_profiles().profiles["openai-prod"]
    assert profile.base_url == "https://openrouter.ai/api/v1"


def test_edit_profile_strips_responses_endpoint_from_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.config.profiles import load_profiles

    runner = CliRunner()
    _add_openai_profile(runner, app)

    result = runner.invoke(
        app,
        ["profile", "edit", "openai-prod", "--base-url", "https://api.openai.com/v1/responses"],
    )

    assert result.exit_code == 0, result.output
    profile = load_profiles().profiles["openai-prod"]
    assert profile.base_url == "https://api.openai.com/v1"
