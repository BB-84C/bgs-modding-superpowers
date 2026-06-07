"""Tests for provider rate tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


def _profile(rpm: int | None = 60, tpm: int | None = None) -> object:
    from bgs_translator.config.profiles import ProviderProfile

    return ProviderProfile(
        name="p",
        sdk_kind="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
        rate_limit_rpm=rpm,
        rate_limit_tpm=tpm,
    )


async def test_acquire_blocks_when_rpm_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    from bgs_translator.observability.rate_tracker import RateTracker

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    tracker = RateTracker(_profile(rpm=1))

    await tracker.acquire(0)
    await tracker.acquire(0)

    assert sleeps


def test_update_from_headers_reduces_remaining_capacity() -> None:
    from bgs_translator.observability.rate_tracker import RateTracker
    from bgs_translator.pipeline.clients.base import RateLimit

    tracker = RateTracker(_profile(rpm=60))
    tracker.update_from_headers(
        RateLimit(
            limit_requests=10,
            remaining_requests=0,
            reset_requests=datetime.now(UTC) + timedelta(seconds=5),
        )
    )

    assert tracker.request_tokens == 0


async def test_observed_429_with_retry_after_schedules_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bgs_translator.observability.rate_tracker import RateTracker

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    tracker = RateTracker(_profile(rpm=None))
    tracker.observed_429(2.5)

    await tracker.acquire(0)

    assert sleeps == [pytest.approx(2.5)]
