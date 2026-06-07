"""Tests for ``xtl batch plan``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner


def test_batch_plan_cli_persists_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Iron Sword")])

    result = CliRunner().invoke(
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
            "fake",
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
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    plan_path = Path(envelope["data"]["plan_path"])
    assert plan_path.exists()
    plan_json = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan_json["plan_id"] == envelope["data"]["plan_id"]
    assert plan_json["total_items"] == 1
