"""Tests for the Morrowind YAML-backed schema."""

from __future__ import annotations


def test_morrowind_schema_loads_known_fields() -> None:
    from bgs_translator.parsers.schemas.morrowind import MorrowindSchema

    schema = MorrowindSchema()

    book_fields = {field.subrecord_sig for field in schema.get_translatable_subrecords("BOOK")}
    info_fields = {field.subrecord_sig for field in schema.get_translatable_subrecords("INFO")}
    dial_fields = {field.subrecord_sig for field in schema.get_translatable_subrecords("DIAL")}

    assert schema.name == "Morrowind"
    assert schema.form_version_range == (0, 0)
    assert {"FNAM", "DESC", "TEXT"}.issubset(book_fields)
    assert {"BNAM", "INAM", "PNAM", "NNAM"}.issubset(info_fields)
    assert "NAME" in dial_fields


def test_morrowind_schema_registered() -> None:
    from bgs_translator.parsers.schemas import SCHEMAS_BY_GAME, get_schema_for_game

    assert "Morrowind" in SCHEMAS_BY_GAME
    assert get_schema_for_game("Morrowind").name == "Morrowind"
