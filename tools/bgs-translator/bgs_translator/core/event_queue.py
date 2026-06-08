"""Thread-safe GUI event bridge between asyncio workers and Tk.

Background translation workers emit ``GuiEvent`` objects from their asyncio
thread. The Tk main thread drains this FIFO from ``root.after`` and dispatches
the events without ever blocking the event loop.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

GuiEventKind = Literal[
    "run.start",
    "run.complete",
    "run.failed",
    "batch.start",
    "batch.progress",
    "batch.complete",
    "batch.failed",
    "batch.cancelled",
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


class EventQueueBridge:
    """Thread-safe FIFO queue between asyncio background thread and Tk.

    Backend thread calls :meth:`emit`. Tk thread calls :meth:`drain`
    periodically (for example, ``root.after(50, drain)``). Subscribers are
    invoked during ``drain`` on the Tk thread, keeping widget mutation on the
    only thread where Tk permits it.
    """

    def __init__(self) -> None:
        self._q: queue.Queue[GuiEvent] = queue.Queue()
        self._subscribers: list[Callable[[GuiEvent], None]] = []
        self._in_flight_count = 0
        self._lock = threading.Lock()

    def emit(self, event: GuiEvent) -> None:
        """Emit an event from a backend thread."""

        self._q.put(event)
        with self._lock:
            if event.kind == "batch.start":
                self._in_flight_count += 1
            elif event.kind in {"batch.complete", "batch.failed", "batch.cancelled"}:
                self._in_flight_count = max(0, self._in_flight_count - 1)

    def drain(self) -> list[GuiEvent]:
        """Return and dispatch all pending events without blocking."""

        events: list[GuiEvent] = []
        try:
            while True:
                events.append(self._q.get_nowait())
        except queue.Empty:
            pass

        if events:
            subscribers = list(self._subscribers)
            for event in events:
                for callback in subscribers:
                    callback(event)
        return events

    def subscribe(self, callback: Callable[[GuiEvent], None]) -> Callable[[], None]:
        """Subscribe to events drained on the Tk thread.

        Returns an idempotent unsubscribe callback.
        """

        self._subscribers.append(callback)

        def unsubscribe() -> None:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

        return unsubscribe

    def in_flight_count(self) -> int:
        """Return the number of batch events currently in flight."""

        with self._lock:
            return self._in_flight_count


_singleton: EventQueueBridge | None = None


def get_bridge() -> EventQueueBridge:
    """Return the module-level bridge singleton."""

    global _singleton
    if _singleton is None:
        _singleton = EventQueueBridge()
    return _singleton


def in_flight_count() -> int:
    """Return the singleton bridge's current in-flight batch count."""

    return get_bridge().in_flight_count()


__all__ = ["EventQueueBridge", "GuiEvent", "GuiEventKind", "get_bridge", "in_flight_count"]
