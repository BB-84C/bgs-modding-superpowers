"""Tests for corrective retry logic."""

from __future__ import annotations

from bgs_translator.parsers.tes4_family import TranslationUnit


def result(soft: bool):  # type: ignore[no-untyped-def]
    from bgs_translator.pipeline.validator import ValidationFailure, ValidationResult
    return ValidationResult(
        item_id="I1",
        ok=soft,
        failures=[ValidationFailure(item_id="I1", gate="mask_completeness", reason="missing {{P0}}", soft=soft)],
    )


def test_can_retry_true_for_hard_failures_within_budget() -> None:
    from bgs_translator.pipeline.retry import can_retry
    assert can_retry(result(False), retry_count=1, max_retries=2) is True


def test_can_retry_false_after_budget_exhausted() -> None:
    from bgs_translator.pipeline.retry import can_retry
    assert can_retry(result(False), retry_count=2, max_retries=2) is False


def test_can_retry_false_for_only_soft_failures() -> None:
    from bgs_translator.pipeline.retry import can_retry
    assert can_retry(result(True), retry_count=0, max_retries=2) is False


def test_build_addendum_renders_placeholder_names() -> None:
    from bgs_translator.pipeline.mask import build_masked_unit
    from bgs_translator.pipeline.retry import build_addendum
    unit = TranslationUnit("Test.esp", 1, 1, "EDID", "WEAP", "FULL", source="Hello %s")
    addendum = build_addendum([result(False)], {"I1": build_masked_unit(unit)})
    body = addendum.render()
    assert "Item I1" in body
    assert "{{P0}}" in body
    assert "Original items follow" in body
