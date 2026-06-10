"""Tests for ``xtl profile`` CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner


def test_profile_add_accepts_api_key_env_and_rejects_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app

    runner = CliRunner()
    ok = runner.invoke(
        app,
        [
            "profile",
            "add",
            "openai-prod",
            "--sdk-kind",
            "openai",
            "--base-url",
            "https://api.openai.com/v1",
            "--model",
            "gpt-5-mini",
            "--api-key-env",
            "BGS_TRANSLATOR_KEY_OPENAI",
        ],
    )
    assert ok.exit_code == 0, ok.output
    assert json.loads(ok.output)["data"]["profile"] == "openai-prod"

    bad = runner.invoke(app, ["profile", "add", "bad", "--api-key", "sk-secret"])
    assert bad.exit_code != 0
    assert json.loads(bad.output)["error"]["code"] == "invalid_argument"


def test_profile_list_and_activate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app

    runner = CliRunner()
    runner.invoke(
        app,
        [
            "profile",
            "add",
            "p1",
            "--sdk-kind",
            "openai",
            "--base-url",
            "https://api.openai.com/v1",
            "--model",
            "gpt-5-mini",
            "--api-key-env",
            "BGS_TRANSLATOR_KEY_OPENAI",
        ],
    )

    activated = runner.invoke(app, ["profile", "activate", "p1"])
    assert activated.exit_code == 0, activated.output
    listed = runner.invoke(app, ["profile", "list"])
    assert listed.exit_code == 0, listed.output
    envelope = json.loads(listed.output)

    assert envelope["data"]["active"] == "p1"
    assert envelope["data"]["profiles"][0]["name"] == "p1"
    assert envelope["data"]["profiles"][0]["active"] is True


def test_profile_set_key_writes_profiles_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.config import paths

    runner = CliRunner()
    added = runner.invoke(
        app,
        [
            "profile",
            "add",
            "openrouter",
            "--sdk-kind",
            "openai-compat",
            "--base-url",
            "https://openrouter.ai/api/v1",
            "--model",
            "deepseek/deepseek-chat",
            "--api-key-env",
            "BGS_TRANSLATOR_KEY_OPENROUTER",
            "--json-mode",
            "json_object",
        ],
    )
    assert added.exit_code == 0, added.output

    result = runner.invoke(app, ["profile", "set-key", "openrouter"], input="sk-test\n")

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output[result.output.index("{") :])
    assert envelope["data"]["api_key_env"] == "BGS_TRANSLATOR_KEY_OPENROUTER"
    assert "BGS_TRANSLATOR_KEY_OPENROUTER=sk-test" in paths.profiles_env_path().read_text(
        encoding="utf-8"
    )


def test_profile_edit_updates_advanced_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.config.profiles import load_profiles

    runner = CliRunner()
    runner.invoke(
        app,
        [
            "profile",
            "add",
            "router",
            "--sdk-kind",
            "openai-compat",
            "--base-url",
            "https://openrouter.ai/api/v1",
            "--model",
            "deepseek/deepseek-chat",
            "--api-key-env",
            "BGS_TRANSLATOR_KEY_OPENROUTER",
            "--json-mode",
            "json_object",
        ],
    )

    edited = runner.invoke(
        app,
        [
            "profile",
            "edit",
            "router",
            "--max-concurrency",
            "8",
            "--rate-limit-rpm",
            "120",
            "--rate-limit-tpm",
            "90000",
            "--json-mode",
            "json_object",
            "--require-parameters",
            "--prompt-caching",
            "--notes",
            "CLI tuned",
        ],
    )

    assert edited.exit_code == 0, edited.output
    profile = load_profiles().profiles["router"]
    assert profile.max_concurrency == 8
    assert profile.rate_limit_rpm == 120
    assert profile.rate_limit_tpm == 90000
    assert profile.require_parameters is True
    assert profile.prompt_caching is True
    assert profile.notes == "CLI tuned"
