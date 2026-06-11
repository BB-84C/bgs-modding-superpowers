"""Tests for SST ``sStrParams`` byte (de)serialization and UI color mapping."""

from __future__ import annotations

import pytest

from bgs_translator.sst.status import (
    DEFAULT_UI_COLOR,
    STATUS_PRIORITY,
    SStrParam,
    from_byte,
    to_byte,
    ui_color,
)


def test_bit_ordinals_match_pascal_enum() -> None:
    # Pascal sStrParam ordinals 0..7.
    assert SStrParam.TRANSLATED.value == 1 << 0
    assert SStrParam.LOCKED_TRANS.value == 1 << 1
    assert SStrParam.INCOMPLETE_TRANS.value == 1 << 2
    assert SStrParam.VALIDATED.value == 1 << 3
    assert SStrParam.DEPRECATED_PARAM1.value == 1 << 4
    assert SStrParam.DEPRECATED_PARAM2.value == 1 << 5
    assert SStrParam.OLD_DATA.value == 1 << 6
    assert SStrParam.PENDING.value == 1 << 7


def test_to_byte_strips_validated() -> None:
    # SaveSSTFile: tmpParams := sk.sparams - [validated]
    p = SStrParam.TRANSLATED | SStrParam.VALIDATED
    assert to_byte(p) == int(SStrParam.TRANSLATED)
    # Even if every bit is set, VALIDATED is the only one stripped.
    assert to_byte(0xFF) == 0xFF & ~int(SStrParam.VALIDATED)


def test_round_trip_persists_non_validated_bits() -> None:
    for raw in (0x00, 0x01, 0x02, 0x04, 0x40, 0x80, 0xC1):
        # VALIDATED never survives a round trip — that's the whole point.
        decoded = from_byte(to_byte(raw))
        assert int(decoded) == raw & ~int(SStrParam.VALIDATED)


def test_from_byte_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        from_byte(256)
    with pytest.raises(ValueError):
        from_byte(-1)


def test_ui_color_priority_order() -> None:
    # Pending wins over everything else.
    assert ui_color(SStrParam.PENDING | SStrParam.TRANSLATED) == "orange"
    # Without pending, locked wins.
    assert ui_color(SStrParam.LOCKED_TRANS | SStrParam.TRANSLATED) == "yellow"
    # Without pending/locked, incomplete wins over translated.
    assert ui_color(SStrParam.INCOMPLETE_TRANS | SStrParam.TRANSLATED) == "pink"
    # Pure translated.
    assert ui_color(SStrParam.TRANSLATED) == "white"
    # Old-data flag without translated reads as gray.
    assert ui_color(SStrParam.OLD_DATA) == "gray"
    # Validated alone reads as blue.
    assert ui_color(SStrParam.VALIDATED) == "blue"


def test_ui_color_empty_is_default() -> None:
    assert ui_color(SStrParam.NONE) == DEFAULT_UI_COLOR
    assert ui_color(0) == DEFAULT_UI_COLOR


def test_status_priority_lists_known_flags_only() -> None:
    for flag, color in STATUS_PRIORITY:
        assert isinstance(flag, SStrParam)
        assert color != DEFAULT_UI_COLOR
