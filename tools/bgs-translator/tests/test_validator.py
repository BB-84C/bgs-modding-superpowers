"""Tests for post-LLM validation gates."""

from __future__ import annotations

from bgs_translator.parsers.tes4_family import TranslationUnit


def unit(source: str) -> TranslationUnit:
    return TranslationUnit("Test.esp", 1, 1, "EDID", "WEAP", "FULL", source=source)


def masked(source: str):  # type: ignore[no-untyped-def]
    from bgs_translator.pipeline.mask import build_masked_unit
    return build_masked_unit(unit(source))


def gate(source: str, dest: str, dnt: list[str] | None = None, enc: list[str] | None = None):  # type: ignore[no-untyped-def]
    from bgs_translator.pipeline.validator import validate_item
    return validate_item(masked(source), dest, dnt or [], enc or ["utf-8"])


def test_gate_1_missing_placeholder_fails() -> None:
    result = gate("Hello %s", "你好")
    assert result.ok is False
    assert result.failures[0].gate == "mask_completeness"


def test_gate_2_unmatched_tag_pair_fails() -> None:
    result = gate("<font color='#fff'>Hello</font>", "{{P1}} translated {{P0}}")
    assert result.ok is False
    assert result.failures[0].gate == "pair_nesting"


def test_gate_3_hallucinated_placeholder_fails() -> None:
    result = gate("Hello", "你好 {{P99}}")
    assert result.ok is False
    assert result.failures[0].gate == "no_hallucinated_placeholders"


def test_gate_4_byte_budget_exceeded_fails() -> None:
    mu = masked("Hello")
    object.__setattr__(mu, "byte_budget", 2)
    from bgs_translator.pipeline.validator import validate_item
    result = validate_item(mu, "你好", [], ["utf-8"])
    assert result.ok is False
    assert result.failures[0].gate == "byte_budget"


def test_gate_5_encoding_feasibility_fails() -> None:
    result = gate("Hello", "你好", enc=["ascii"])
    assert result.ok is False
    assert result.failures[0].gate == "encoding_feasibility"


def test_gate_6_do_not_translate_term_missing_fails() -> None:
    result = gate("Requires SKSE", "需要脚本扩展器", dnt=["SKSE"])
    assert result.ok is False
    assert result.failures[0].gate == "do_not_translate_intact"


def test_gate_7_mcm_prefix_violated_fails() -> None:
    result = gate("$Token\tHello", "你好")
    assert result.ok is False
    assert result.failures[0].gate == "mcm_key_intact"


def test_gate_8_length_ratio_is_soft_warning() -> None:
    result = gate("Hello there", "x" * 100)
    assert result.ok is True
    assert result.failures[0].gate == "length_sanity"
    assert result.failures[0].soft is True


def test_all_pass_case() -> None:
    result = gate("Hello %s", "你好 {{P0}}")
    assert result.ok is True
    assert result.failures == []
