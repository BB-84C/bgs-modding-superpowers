"""Tests for ``xtl project init``."""

from __future__ import annotations

import json
import sqlite3
import tomllib
from pathlib import Path

import pytest
from test_tes4_family_walker import grup, record, subrecord, tes4_header
from typer.testing import CliRunner


def starfield_plugin_bytes(*, fv: int = 560) -> bytes:
    data = subrecord(b"EDID", b"TestWeapon\x00") + subrecord(b"FULL", b"Test Rifle\x00")
    return tes4_header(fv=fv) + grup(record(b"WEAP", data, formid=0x01001234, fv=fv))


def write_starfield_plugin(path: Path, *, fv: int = 560) -> None:
    path.write_bytes(starfield_plugin_bytes(fv=fv))


def test_project_init_creates_project_and_seeds_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    plugin = tmp_path / "Test.esm"
    write_starfield_plugin(plugin)

    result = CliRunner().invoke(
        app,
        ["project", "init", "test-project", "--plugin", str(plugin), "--game", "Starfield"],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    project_root = Path(envelope["data"]["project_root"])
    assert envelope["data"]["units_extracted"] == 1
    assert envelope["data"]["signature_distribution"] == {"WEAP": 1}
    assert len(envelope["data"]["plugin_sha256"]) == 64
    for child in ["sources", "memory", "batches", "exports"]:
        assert (project_root / child).is_dir()

    project_toml = tomllib.loads((project_root / "project.toml").read_text(encoding="utf-8"))
    assert project_toml["schema_version"] == 1
    assert project_toml["project"]["name"] == "test-project"
    assert project_toml["project"]["game"] == "Starfield"
    assert project_toml["project"]["source_lang"] == "en"
    assert project_toml["project"]["target_lang"] == "zh-cn"

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    assert conn.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 1
    assert list((project_root / "sources").glob("*.cache.bin"))
    assert list((project_root / "sources").glob("*.cache.toml"))


def test_project_init_auto_detects_unique_form_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    plugin = tmp_path / "Detected.esm"
    write_starfield_plugin(plugin, fv=560)

    result = CliRunner().invoke(app, ["project", "init", "detected", "--plugin", str(plugin)])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["data"]["game"] == "Starfield"


def test_project_init_reports_ambiguous_form_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    plugin = tmp_path / "Ambiguous.esm"
    plugin.write_bytes(tes4_header(fv=131) + grup(record(b"WEAP", subrecord(b"FULL", b"X\x00"), fv=131)))

    result = CliRunner().invoke(app, ["project", "init", "ambiguous", "--plugin", str(plugin)])

    assert result.exit_code == 1
    envelope = json.loads(result.output)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "ambiguous_game"
    assert set(envelope["error"]["details"]["candidates"]) == {"Fallout4", "Fallout76"}
