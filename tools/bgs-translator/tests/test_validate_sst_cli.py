"""Tests for SST validation CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from bgs_translator.sst import SStrParam, SSTUnit, write_sst


def _run_validate(args: list[str]) -> dict[str, Any]:
    from bgs_translator.cli.app import app

    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    loaded = json.loads(result.output)
    assert isinstance(loaded, dict)
    return loaded


def _unit(*, s_params: int = 0, dest: str = "铁剑") -> SSTUnit:
    return SSTUnit(
        list_index=0,
        strid=1,
        formid=0x00000001,
        signature="WEAP",
        field="FULL",
        source="Iron Sword",
        dest=dest,
        s_params=s_params,
    )


def test_validate_sst_round_trip_identical(tmp_path: Path) -> None:
    sst_path = tmp_path / "ok.sst"
    write_sst(sst_path, [_unit()], ["Starfield.esm"])

    envelope = _run_validate(["validate", "sst", str(sst_path)])

    assert envelope["ok"] is True
    data = envelope["data"]
    assert data["round_trip_ok"] is True
    assert data["byte_identical"] is True
    assert data["version"] == "SSU9"
    assert data["entry_count"] == 1
    assert data["masters"] == ["Starfield.esm"]
    assert data["signatures"] == ["WEAP"]


def test_validate_sst_round_trip_divergence_is_reported(tmp_path: Path) -> None:
    sst_path = tmp_path / "validated-bit.sst"
    write_sst(sst_path, [_unit()], ["Starfield.esm"])
    data = bytearray(sst_path.read_bytes())
    # SSU9 header for one master/no labels + fixed entry prefix places sParams here.
    sparams_offset = 4 + 1 + 4 + 4 + len("Starfield.esm".encode("utf-16-le")) + 4 + 1 + 24 + 1
    data[sparams_offset] = int(SStrParam.VALIDATED)
    sst_path.write_bytes(bytes(data))

    envelope = _run_validate(["validate", "sst", str(sst_path)])

    assert envelope["data"]["round_trip_ok"] is True
    assert envelope["data"]["byte_identical"] is False


def test_validate_sst_reference_match(tmp_path: Path) -> None:
    sst_path = tmp_path / "ok.sst"
    reference = tmp_path / "reference.sst"
    write_sst(sst_path, [_unit(dest="铁剑")], ["Starfield.esm"])
    reference.write_bytes(sst_path.read_bytes())

    envelope = _run_validate(["validate", "sst", str(sst_path), "--reference", str(reference)])

    assert envelope["data"]["byte_identical"] is True
    assert envelope["data"]["reference_byte_identical"] is True
    assert envelope["data"]["reference_differing_entries"] == []
