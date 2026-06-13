"""Gated acceptance test against the local MO2 harness.

Skips automatically when the harness path is not present (CI / fresh clones).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mo2_assets_engine.cli.app import app

HARNESS_PROFILE = Path(
    os.environ.get(
        "BGS_MO2_ROOT",
        r"D:\awesome-bgs-mod-master\.artifacts\mo2",
    )
) / "profiles" / "Default"

HARNESS_MODS = HARNESS_PROFILE.parent.parent / "mods"


pytestmark = pytest.mark.skipif(
    not (HARNESS_PROFILE / "modlist.txt").exists(),
    reason="MO2 harness profile not present; run on a dev box with .artifacts/mo2",
)


def test_harness_summary_returns_json_with_at_least_one_mod() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(HARNESS_PROFILE),
            "--mods", str(HARNESS_MODS),
            "--game", "fallout4",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["mods"]) >= 1


def test_harness_mod_conflicts_for_first_mod_returns_three_sections() -> None:
    runner = CliRunner()
    summary_result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(HARNESS_PROFILE),
            "--mods", str(HARNESS_MODS),
            "--game", "fallout4",
            "--format", "json",
        ],
    )
    summary_data = json.loads(summary_result.output)
    first_mod = summary_data["mods"][0]["name"]

    result = runner.invoke(
        app,
        [
            "mod-conflicts", first_mod,
            "--profile", str(HARNESS_PROFILE),
            "--mods", str(HARNESS_MODS),
            "--game", "fallout4",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mod"] == first_mod
    assert "kept" in data
    assert "overwritten" in data
    assert "no_conflict" in data
