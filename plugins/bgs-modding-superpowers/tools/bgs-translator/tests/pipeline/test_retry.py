"""Retry addendum regression tests."""

from __future__ import annotations

from bgs_translator.pipeline.retry import CorrectiveAddendum
from bgs_translator.pipeline.validator import ValidationFailure


def test_empty_completion_addendum_prepends_reasoning_trace_instruction() -> None:
    addendum = CorrectiveAddendum(
        item_failures={
            "I1": [
                ValidationFailure(
                    item_id="I1",
                    gate="empty_dest_for_nonempty_source",
                    reason="empty_completion",
                    soft=False,
                )
            ]
        }
    )

    body = addendum.render()

    assert body.startswith(
        "Your previous response had empty content. Return the JSON object directly without "
        "any reasoning trace, thinking tags, or preamble."
    )
    assert "Item I1" in body
