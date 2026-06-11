"""Tests for protected-span masking and unmasking."""

from __future__ import annotations

import pytest

from bgs_translator.parsers.tes4_family import TranslationUnit


def unit(source: str) -> TranslationUnit:
    return TranslationUnit("Test.esp", 1, 1, "EDID", "WEAP", "FULL", source=source)


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("Value %03d", "format_printf"),
        ("Hello {name}", "format_brace_named"),
        ("Slot {0}", "format_brace_indexed"),
        ("Hi <Alias=PlayerRef>", "alias_substitution"),
        ("Level <Global.PlayerLevel>", "global_substitution"),
        ("<font color='#fff'>Hello", "tag_open_font"),
        ("Hello</font>", "tag_close_font"),
        ("Line 1\nLine 2", "newline_structural"),
    ],
)
def test_mask_kind_in_isolation(source: str, kind: str) -> None:
    from bgs_translator.pipeline.mask import mask_source

    masked, mask_map, prefix = mask_source(source)

    assert prefix is None
    assert "{{P0}}" in masked
    assert mask_map["{{P0}}"].kind == kind


def test_pure_format_string_skips_llm() -> None:
    from bgs_translator.pipeline.mask import build_masked_unit

    masked = build_masked_unit(unit("%d %s %d"))

    assert masked.skip_llm is True
    assert masked.skip_reason == "all_protected"


def test_mcm_prefix_detection_and_stripping() -> None:
    from bgs_translator.pipeline.mask import mask_source, unmask_dest

    source = "$Token\tHello %s"
    masked, mask_map, prefix = mask_source(source)

    assert prefix == "$Token\t"
    assert masked == "Hello {{P0}}"
    assert unmask_dest(masked, mask_map, prefix) == source


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("quest_stage", "snake_case"),
        ("MCMSettingIDValue", "camel_case_id"),
        ("\n\r\n", "only_line_breaks"),
        ("OK", "too_short"),
        ("1234!!!", "punctuation_digits"),
        ("10%+2.5", "numeric_formatting"),
        (r"Textures\Foo", "backslash_containing"),
    ],
)
def test_heuristic_skip_rules(source: str, reason: str) -> None:
    from bgs_translator.pipeline.mask import apply_skip_heuristics

    assert apply_skip_heuristics(source) == reason


def test_mask_unmask_roundtrip_for_non_skip_case() -> None:
    from bgs_translator.pipeline.mask import mask_source, unmask_dest

    source = "<font color='#fff'>Hello {name}, use %s</font>\nNow!"
    masked, mask_map, prefix = mask_source(source)

    assert masked != source
    assert unmask_dest(masked, mask_map, prefix) == source


def test_multi_kind_masks_all_placeholders() -> None:
    from bgs_translator.pipeline.mask import mask_source

    masked, mask_map, _prefix = mask_source("Hello %s, %d items in {area}!")

    assert masked == "Hello {{P0}}, {{P1}} items in {{P2}}!"
    assert [token.kind for token in mask_map.values()] == [
        "format_printf",
        "format_printf",
        "format_brace_named",
    ]
