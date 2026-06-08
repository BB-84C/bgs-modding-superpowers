"""Thread-safe asyncio-to-Tk event queue bridge tests."""

from __future__ import annotations

import threading

from bgs_translator.core.event_queue import EventQueueBridge, GuiEvent


def test_emit_from_thread_then_drain_on_main_thread_returns_events() -> None:
    bridge = EventQueueBridge()
    event = GuiEvent(kind="log.entry", payload={"message": "hello"})

    worker = threading.Thread(target=lambda: bridge.emit(event))
    worker.start()
    worker.join(timeout=2)

    assert bridge.drain() == [event]
    assert bridge.drain() == []


def test_in_flight_count_tracks_batch_lifecycle() -> None:
    bridge = EventQueueBridge()

    bridge.emit(GuiEvent(kind="batch.start", batch_id="b1"))
    bridge.emit(GuiEvent(kind="batch.start", batch_id="b2"))
    assert bridge.in_flight_count() == 2

    bridge.emit(GuiEvent(kind="batch.complete", batch_id="b1"))
    assert bridge.in_flight_count() == 1

    bridge.emit(GuiEvent(kind="batch.failed", batch_id="b2"))
    bridge.emit(GuiEvent(kind="batch.cancelled", batch_id="extra"))
    assert bridge.in_flight_count() == 0


def test_subscribe_unsubscribe_lifecycle_receives_drained_events() -> None:
    bridge = EventQueueBridge()
    received: list[GuiEvent] = []
    unsubscribe = bridge.subscribe(received.append)

    first = GuiEvent(kind="cost.update", payload={"usd": 1.25})
    bridge.emit(first)
    assert bridge.drain() == [first]
    assert received == [first]

    unsubscribe()
    second = GuiEvent(kind="rate.observed", payload={"rpm": 10})
    bridge.emit(second)
    assert bridge.drain() == [second]
    assert received == [first]
