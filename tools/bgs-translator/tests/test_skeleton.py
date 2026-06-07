"""Smoke tests for the bgs-translator Chunk B skeleton."""

from __future__ import annotations

import json

from typer.testing import CliRunner


def test_package_imports() -> None:
    import bgs_translator

    assert bgs_translator.__version__ == "0.1.0-dev"


def test_version_command_envelope() -> None:
    from bgs_translator.cli.app import app

    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["error"] is None
    assert envelope["data"]["version"] == "0.1.0-dev"
    assert "python" in envelope["data"]
    assert envelope["data"]["capabilities"]["parser"] == {
        "tes3": False,
        "tes4_family": False,
    }


def test_envelope_success_failure() -> None:
    from bgs_translator.cli.envelopes import exit_code_for, failure, success

    ok = success({"answer": 42})
    assert ok.ok is True
    assert ok.data == {"answer": 42}
    assert ok.error is None
    assert exit_code_for(ok) == 0

    failed = failure("validation_error", "Invalid reactor coolant ratio", field="coolant")
    assert failed.ok is False
    assert failed.data is None
    assert failed.error == {
        "code": "validation_error",
        "message": "Invalid reactor coolant ratio",
        "field": "coolant",
    }
    assert exit_code_for(failed) == 2


def test_i18n_coverage_passes_when_empty() -> None:
    from bgs_translator.gui.i18n._coverage_check import find_missing_translations

    assert find_missing_translations() == []
