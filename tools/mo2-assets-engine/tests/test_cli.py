import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mo2_assets_engine.cli.app import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cli_profile(tmp_path: Path) -> tuple[Path, Path]:
    """Tiny synthetic MO2 layout for CLI tests."""
    profile = tmp_path / "profiles" / "Default"
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("*ModA.esp\n*ModB.esp\n", encoding="utf-8")

    mods = tmp_path / "mods"
    (mods / "ModA" / "textures").mkdir(parents=True)
    (mods / "ModA" / "textures" / "shared.dds").write_bytes(b"a")
    (mods / "ModA" / "textures" / "solo-a.dds").write_bytes(b"a")
    (mods / "ModB" / "textures").mkdir(parents=True)
    (mods / "ModB" / "textures" / "shared.dds").write_bytes(b"b")
    (mods / "ModB" / "textures" / "solo-b.dds").write_bytes(b"b")

    return profile, mods


def test_summary_human_output(runner: CliRunner, cli_profile: tuple[Path, Path]) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "ModA" in result.output
    assert "ModB" in result.output


def test_summary_json_output(runner: CliRunner, cli_profile: tuple[Path, Path]) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "summary",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert {m["name"] for m in data["mods"]} == {"ModA", "ModB"}


def test_mod_conflicts_three_sections(runner: CliRunner, cli_profile: tuple[Path, Path]) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "mod-conflicts", "ModA",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mod"] == "ModA"
    # ModA top of modlist -> highest priority -> wins shared.dds.
    assert any(e["path"] == "textures/shared.dds" for e in data["kept"])
    assert all(e["path"] != "textures/shared.dds" for e in data["overwritten"])
    assert any(e == "textures/solo-a.dds" for e in data["no_conflict"])


def test_resolve_file_returns_winner_and_losers(
    runner: CliRunner, cli_profile: tuple[Path, Path]
) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "resolve-file", "textures/shared.dds",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["path"] == "textures/shared.dds"
    assert data["winner"]["mod"] == "ModA"
    assert any(loser["mod"] == "ModB" for loser in data["losers"])
    assert data["is_conflict"] is True


def test_archive_inventory_empty_for_no_archives(
    runner: CliRunner, cli_profile: tuple[Path, Path]
) -> None:
    profile, mods = cli_profile
    result = runner.invoke(
        app,
        [
            "archive-inventory", "ModA",
            "--profile", str(profile),
            "--mods", str(mods),
            "--game", "skyrim",
            "--format", "json",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["mod"] == "ModA"
    assert data["archives"] == []
