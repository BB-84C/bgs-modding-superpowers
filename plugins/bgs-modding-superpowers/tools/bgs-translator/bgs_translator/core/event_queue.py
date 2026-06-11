"""Structured GUI event payloads shared by CLI workers and the web UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

GuiEventKind = Literal[
    "run.start",
    "run.complete",
    "run.failed",
    "run.abandoned",
    "batch.start",
    "batch.progress",
    "batch.request_sent",
    "batch.response_received",
    "batch.complete",
    "batch.failed",
    "batch.cancelled",
    "batch.abandoned",
    "batch.waiting_preview",
    "cost.update",
    "rate.observed",
    "log.entry",
    "prompt.preview_request",
]


@dataclass(frozen=True)
class GuiEvent:
    """One backend-to-GUI update event."""

    kind: GuiEventKind
    run_id: str | None = None
    batch_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)


__all__ = ["GuiEvent", "GuiEventKind"]
