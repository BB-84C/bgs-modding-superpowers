"""Pipeline validator regression tests."""

from __future__ import annotations

from bgs_translator.parsers.tes4_family import TranslationUnit
from bgs_translator.pipeline.mask import build_masked_unit
from bgs_translator.pipeline.validator import validate_item


def test_gate_9_empty_dest_for_nonempty_source_fails_hard() -> None:
    unit = TranslationUnit("Test.esp", 1, 1, "EDID", "WEAP", "FULL", source="Merchant's Scion")

    result = validate_item(build_masked_unit(unit), "   ", [], ["utf-8"])

    assert result.ok is False
    assert result.failures[0].gate == "empty_dest_for_nonempty_source"
    assert result.failures[0].reason == "empty_completion"
    assert result.failures[0].soft is False
