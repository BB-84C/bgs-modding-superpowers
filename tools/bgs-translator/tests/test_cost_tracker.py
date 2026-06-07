"""Tests for cost tracking and cap enforcement."""

from __future__ import annotations


def _profile() -> object:
    from bgs_translator.config.profiles import ProviderProfile

    return ProviderProfile(
        name="p",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
        cost_cap_usd=1.0,
    )


def test_record_accumulates_estimated_cost() -> None:
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.pipeline.clients.base import TokenUsage

    tracker = CostTracker(_profile())
    tracker.record(TokenUsage(input_tokens=1_000_000, output_tokens=0), exact_cost=None)

    assert tracker.estimated_total() == 0.5
    assert tracker.cost_exact is False


def test_record_accumulates_exact_cost() -> None:
    from bgs_translator.observability.cost_tracker import CostTracker
    from bgs_translator.pipeline.clients.base import TokenUsage

    tracker = CostTracker(_profile())
    tracker.record(TokenUsage(input_tokens=1, output_tokens=1), exact_cost=0.25)

    assert tracker.estimated_total() == 0.25
    assert tracker.cost_exact is True


def test_would_exceed_cap_checks_profile_and_project_caps() -> None:
    from bgs_translator.observability.cost_tracker import CostTracker


    tracker = CostTracker(_profile(), project_cap=0.75)
    assert tracker.would_exceed_cap(0.5) is False
    assert tracker.would_exceed_cap(0.8) is True
