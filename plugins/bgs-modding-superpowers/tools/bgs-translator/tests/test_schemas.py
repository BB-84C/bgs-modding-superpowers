"""Tests for YAML-backed per-game schemas."""

from __future__ import annotations

from pathlib import Path

import yaml

SCHEMA_EXPECTATIONS = [
    ("Oblivion", (0, 0), "oblivion"),
    ("Fallout3", (0, 0), "fo3"),
    ("FalloutNV", (0, 0), "fnv"),
    ("SkyrimLE", (43, 43), "skyrim_le"),
    ("SkyrimSE", (43, 44), "skyrim_se"),
    ("Fallout4", (131, 131), "fo4"),
    ("Fallout76", (131, 250), "fo76"),
    ("Starfield", (552, 576), "starfield"),
    ("Morrowind", (0, 0), "morrowind"),
]


def test_yaml_backed_schemas_expose_weap_fields() -> None:
    from bgs_translator.parsers.schemas import get_schema_for_game

    for game, expected_range, _manifest in SCHEMA_EXPECTATIONS:
        schema = get_schema_for_game(game)

        assert schema.name == game
        assert schema.form_version_range == expected_range
        assert len(schema.form_version_range) == 2
        assert schema.get_translatable_subrecords("WEAP")


def test_schema_registry_aliases() -> None:
    from bgs_translator.parsers.schemas import SCHEMAS_BY_GAME

    assert len(SCHEMAS_BY_GAME) == 12
    assert SCHEMAS_BY_GAME["SkyrimAE"] is SCHEMAS_BY_GAME["SkyrimSE"]
    assert SCHEMAS_BY_GAME["SkyrimVR"] is SCHEMAS_BY_GAME["SkyrimSE"]
    assert SCHEMAS_BY_GAME["Fallout4VR"] is SCHEMAS_BY_GAME["Fallout4"]


def test_yaml_manifests_have_minimum_record_coverage() -> None:
    data_dir = Path(__file__).parents[1] / "bgs_translator" / "parsers" / "schemas" / "data"

    for _game, _expected_range, manifest in SCHEMA_EXPECTATIONS:
        data = yaml.safe_load((data_dir / f"{manifest}.yaml").read_text(encoding="utf-8"))

        assert len(data["records"]) >= 20
