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
