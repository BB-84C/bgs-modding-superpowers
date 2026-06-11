"""Corrective-feedback retry layer ownership."""

from __future__ import annotations

from dataclasses import dataclass

from bgs_translator.pipeline.mask import MaskedUnit
from bgs_translator.pipeline.validator import ValidationFailure, ValidationResult


@dataclass(frozen=True)
class CorrectiveAddendum:
    """Corrective retry message grouped by item id."""

    item_failures: dict[str, list[ValidationFailure]]

    def render(self) -> str:
        """Build the retry addendum message body."""

        lines: list[str] = []
        if _has_empty_completion_failure(self.item_failures):
            lines.extend(
                [
                    "Your previous response had empty content. Return the JSON object directly "
                    "without any reasoning trace, thinking tags, or preamble.",
                    "",
                ]
            )
        lines.extend([
            "The previous attempt failed validation on these items. Please correct only the "
            "listed items and resend the FULL JSON object:",
            "",
        ])
        for item_id, failures in self.item_failures.items():
            lines.extend(f"- Item {item_id}: {failure.reason}." for failure in failures)
        lines.extend(["", "Original items follow. Please return the full corrected JSON."])
        return "\n".join(lines)


def can_retry(result: ValidationResult, retry_count: int, max_retries: int) -> bool:
    """Return true when a hard failure is still within retry budget."""

    has_hard_failure = any(not failure.soft for failure in result.failures)
    return has_hard_failure and retry_count < max_retries


def build_addendum(
    failures: list[ValidationResult],
    masked_units: dict[str, MaskedUnit],
) -> CorrectiveAddendum:
    """Build a corrective addendum for hard-failed items only."""

    item_failures: dict[str, list[ValidationFailure]] = {}
    for result in failures:
        hard_failures = [failure for failure in result.failures if not failure.soft]
        if not hard_failures:
            continue
        masked_unit = masked_units.get(result.item_id)
        if masked_unit is not None:
            hard_failures = [_with_placeholder_context(failure, masked_unit) for failure in hard_failures]
        item_failures[result.item_id] = hard_failures
    return CorrectiveAddendum(item_failures=item_failures)


def _has_empty_completion_failure(item_failures: dict[str, list[ValidationFailure]]) -> bool:
    return any(
        failure.reason == "empty_completion" or failure.gate == "empty_dest_for_nonempty_source"
        for failures in item_failures.values()
        for failure in failures
    )


def _with_placeholder_context(
    failure: ValidationFailure,
    masked_unit: MaskedUnit,
) -> ValidationFailure:
    context = "; ".join(
        f"{token.placeholder} represents {token.original!r}" for token in masked_unit.mask_map.values()
    )
    if not context:
        return failure
    return ValidationFailure(
        item_id=failure.item_id,
        gate=failure.gate,
        reason=f"{failure.reason} ({context})",
        soft=failure.soft,
    )


__all__ = ["CorrectiveAddendum", "build_addendum", "can_retry"]
