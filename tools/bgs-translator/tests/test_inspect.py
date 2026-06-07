"""Tests for inspect CLI subcommands."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from test_project_init import write_starfield_plugin
from typer.testing import CliRunner


def init_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    plugin = tmp_path / "Inspect.esm"
    write_starfield_plugin(plugin)
    result = CliRunner().invoke(
        app, ["project", "init", "inspect-project", "--plugin", str(plugin), "--game", "Starfield"]
    )
    assert result.exit_code == 0, result.output
    project_root = tmp_path / "translator" / "projects" / "inspect-project"
    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    row_id = conn.execute("SELECT row_id FROM units").fetchone()[0]
    return plugin, str(row_id)


def test_inspect_plugin_returns_header_and_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app

    plugin, _row_id = init_project(tmp_path, monkeypatch)
    result = CliRunner().invoke(app, ["inspect", "plugin", str(plugin), "--game", "Starfield"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["data"]["header"]["form_version"] == 560
    assert envelope["data"]["signature_distribution"] == {"WEAP": 1}


def test_inspect_project_read_commands_are_well_formed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app

    _plugin, row_id = init_project(tmp_path, monkeypatch)
    runner = CliRunner()

    signatures = runner.invoke(app, ["inspect", "signatures", "inspect-project"])
    assert signatures.exit_code == 0, signatures.output
    assert json.loads(signatures.output)["data"]["signatures"] == {"WEAP": 1}

    entries = runner.invoke(app, ["inspect", "entries", "inspect-project", "--sig", "WEAP"])
    assert entries.exit_code == 0, entries.output
    entries_envelope = json.loads(entries.output)
    assert entries_envelope["ok"] is True
    assert entries_envelope["data"]["returned"] == 1
    assert {entry["signature"] for entry in entries_envelope["data"]["entries"]} == {"WEAP"}

    entry = runner.invoke(app, ["inspect", "entry", "inspect-project", row_id])
    assert entry.exit_code == 0, entry.output
    entry_envelope = json.loads(entry.output)
    assert entry_envelope["ok"] is True
    assert entry_envelope["data"]["entry"]["row_id"] == row_id

    orphans = runner.invoke(app, ["inspect", "orphans", "inspect-project"])
    assert orphans.exit_code == 0, orphans.output
    orphans_envelope = json.loads(orphans.output)
    assert orphans_envelope["ok"] is True
    assert orphans_envelope["data"]["entries"] == []
