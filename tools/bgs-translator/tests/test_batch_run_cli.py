"""Tests for ``xtl batch run``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner


def test_batch_run_dry_run_uses_synthetic_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Iron Sword")])
    conn.close()
    runner = CliRunner()
    planned = runner.invoke(
        app,
        [
            "batch",
            "plan",
            "demo",
            "--register",
            "dialogue",
            "--target-lang",
            "zh-cn",
            "--profile",
            "synthetic",
            "--game-lore",
            "Skyrim",
            "--mod-name",
            "Demo",
            "--mod-theme",
            "Weapons",
            "--style",
            "Concise",
        ],
    )
    plan_id = json.loads(planned.output)["data"]["plan_id"]

    result = runner.invoke(app, ["batch", "run", "demo", "--plan", plan_id, "--dry-run"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["data"]["run_id"]
    assert envelope["data"]["summary"]["succeeded"] == 1
    assert envelope["data"]["dry_run"] is True
