"""Integration smoke for the user-provided Adwryos Starfield fixture."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

ADWRYOS = Path(r"D:\Starfield MO2\mods\adwryos-cc\adwryos.esm")


@pytest.mark.skipif(not ADWRYOS.exists(), reason="adwryos Starfield fixture missing")
def test_adwryos_project_init_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.parsers.extractor import extract_translation_units
    from bgs_translator.parsers.schemas import get_schema_for_game

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["project", "init", "adwryos-test", "--plugin", str(ADWRYOS), "--game", "Starfield"],
    )

    assert result.exit_code == 0, result.output
    project_root = tmp_path / "translator" / "projects" / "adwryos-test"
    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    assert conn.execute("SELECT COUNT(*) FROM units").fetchone()[0] > 50

    inspect_result = runner.invoke(app, ["inspect", "signatures", "adwryos-test"])
    assert inspect_result.exit_code == 0, inspect_result.output
    inspect_distribution = json.loads(inspect_result.output)["data"]["signatures"]

    walker_distribution: dict[str, int] = {}
    for unit in extract_translation_units(ADWRYOS, "Starfield", schema=get_schema_for_game("Starfield")):
        walker_distribution[unit.signature] = walker_distribution.get(unit.signature, 0) + 1
    assert inspect_distribution == walker_distribution
