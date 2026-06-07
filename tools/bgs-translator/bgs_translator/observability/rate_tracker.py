"""Provider rate-limit observation ownership."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from bgs_translator.config.profiles import ProviderProfile
from bgs_translator.pipeline.clients.base import RateLimit


class RateTracker:
    """Tracks RPM + TPM per profile via token buckets and observed backoff."""

    def __init__(self, profile: ProviderProfile) -> None:
        self.profile = profile
        self.request_capacity = float(profile.rate_limit_rpm) if profile.rate_limit_rpm else None
        self.token_capacity = float(profile.rate_limit_tpm) if profile.rate_limit_tpm else None
        self.request_tokens = self.request_capacity if self.request_capacity is not None else float("inf")
        self.token_tokens = self.token_capacity if self.token_capacity is not None else float("inf")
        self._last_refill = time.monotonic()
        self._throttled_until: float | None = None
        self._consecutive_429 = 0

    async def acquire(self, est_tokens: int) -> None:
        """Block until profile-defined, observed, and 429 limits permit dispatch."""

        while True:
            self._refill()
            wait = self._backoff_wait()
            if wait is None and self.request_tokens >= 1 and self.token_tokens >= est_tokens:
                self.request_tokens -= 1
                if self.token_capacity is not None:
                    self.token_tokens -= est_tokens
                return
            wait_seconds = wait if wait is not None else self._bucket_wait(est_tokens)
            await asyncio.sleep(wait_seconds)
            self._advance_after_sleep(wait_seconds)

    def update_from_headers(self, rl: RateLimit) -> None:
        """Fold provider-observed remaining capacity into the buckets."""

        if rl.limit_requests is not None:
            configured = self.profile.rate_limit_rpm
            self.request_capacity = float(min(configured, rl.limit_requests) if configured else rl.limit_requests)
        if rl.remaining_requests is not None:
            self.request_tokens = min(self.request_tokens, float(rl.remaining_requests))
        if rl.limit_tokens is not None:
            configured_tokens = self.profile.rate_limit_tpm
            self.token_capacity = float(
                min(configured_tokens, rl.limit_tokens) if configured_tokens else rl.limit_tokens
            )
        if rl.remaining_tokens is not None:
            self.token_tokens = min(self.token_tokens, float(rl.remaining_tokens))
        if rl.retry_after_seconds is not None:
            self.observed_429(rl.retry_after_seconds)

    def observed_429(self, retry_after: float | None) -> None:
        """Record a 429 and schedule reactive backoff."""

        self._consecutive_429 += 1
        delay = retry_after if retry_after is not None else min(16.0, 2.0 ** (self._consecutive_429 + 1))
        self._throttled_until = time.monotonic() + max(0.0, delay)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = max(0.0, now - self._last_refill)
        self._last_refill = now
        if self.request_capacity is not None:
            self.request_tokens = min(
                self.request_capacity, self.request_tokens + elapsed * (self.request_capacity / 60.0)
            )
        if self.token_capacity is not None:
            self.token_tokens = min(self.token_capacity, self.token_tokens + elapsed * (self.token_capacity / 60.0))

    def _backoff_wait(self) -> float | None:
        if self._throttled_until is None:
            return None
        remaining = self._throttled_until - time.monotonic()
        if remaining <= 0:
            self._throttled_until = None
            return None
        return remaining

    def _bucket_wait(self, est_tokens: int) -> float:
        waits: list[float] = []
        if self.request_capacity is not None and self.request_tokens < 1:
            waits.append((1 - self.request_tokens) / (self.request_capacity / 60.0))
        if self.token_capacity is not None and self.token_tokens < est_tokens:
            waits.append((est_tokens - self.token_tokens) / (self.token_capacity / 60.0))
        return max(0.01, min(waits) if waits else 0.01)

    def _advance_after_sleep(self, seconds: float) -> None:
        if self._throttled_until is not None and self._throttled_until <= time.monotonic() + seconds:
            self._throttled_until = None
        if self.request_capacity is not None:
            self.request_tokens = min(
                self.request_capacity, self.request_tokens + seconds * (self.request_capacity / 60.0)
            )
        if self.token_capacity is not None:
            self.token_tokens = min(self.token_capacity, self.token_tokens + seconds * (self.token_capacity / 60.0))


def parse_http_date_or_seconds(value: str) -> float | None:
    """Parse Retry-After seconds or HTTP-date strings."""

    try:
        return float(value)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (parsed - datetime.now(UTC)).total_seconds())


__all__ = ["RateTracker", "parse_http_date_or_seconds"]
