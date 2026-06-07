"""Tests for xtl config commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner


def test_config_show_envelope(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))

    result = CliRunner().invoke(app, ["config", "show"])

    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["data"]["settings"]["ui"]["theme"] == "amber"
    assert envelope["data"]["paths"]["home"] == str(tmp_path.resolve())


def test_config_set_then_get(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    runner = CliRunner()

    set_result = runner.invoke(app, ["config", "set", "ui.theme", "green"])
    get_result = runner.invoke(app, ["config", "get", "ui.theme"])

    assert set_result.exit_code == 0
    assert get_result.exit_code == 0
    assert json.loads(get_result.stdout)["data"]["value"] == "green"


def test_config_set_invalid_value(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    result = CliRunner().invoke(app, ["config", "set", "ui.theme", "purple"])

    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "invalid_value"
