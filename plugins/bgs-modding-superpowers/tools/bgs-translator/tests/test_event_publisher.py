"""Tests for sqlite-backed cross-process GUI event publishing."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest

from bgs_translator.core.event_publisher import EventPublisher, reset_publishers_for_tests
from bgs_translator.core.event_queue import GuiEvent
from bgs_translator.core.memory import fetch_events_for_run, open_memory_db


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    reset_publishers_for_tests()


def test_emit_writes_to_project_sqlite() -> None:
    project_root = _project("demo")
    open_memory_db(project_root).close()
    publisher = EventPublisher("demo")

    event_id = publisher.emit(GuiEvent(kind="batch.start", run_id="rn_1", batch_id="b1", payload={"done": 0}))

    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    try:
        events = fetch_events_for_run(conn, "rn_1")
    finally:
        conn.close()
    assert event_id == 1
    assert events == [
        {
            "event_id": 1,
            "run_id": "rn_1",
            "batch_id": "b1",
            "kind": "batch.start",
            "payload": {"done": 0},
            "emitted_at": events[0]["emitted_at"],
        }
    ]


def test_emit_does_not_cross_project_boundaries() -> None:
    project_a = _project("A")
    project_b = _project("B")
    open_memory_db(project_a).close()
    open_memory_db(project_b).close()

    EventPublisher("A").emit(GuiEvent(kind="run.start", run_id="rn_a", payload={"project": "A"}))

    conn_a = sqlite3.connect(project_a / "memory" / "memory.sqlite")
    conn_b = sqlite3.connect(project_b / "memory" / "memory.sqlite")
    try:
        assert len(fetch_events_for_run(conn_a, "rn_a")) == 1
        assert fetch_events_for_run(conn_b, "rn_a") == []
    finally:
        conn_a.close()
        conn_b.close()


def test_emit_swallows_http_push_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = _project("demo")
    open_memory_db(project_root).close()

    def fail_post(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("bgs_translator.core.event_publisher.httpx.post", fail_post)
    publisher = EventPublisher("demo", gui_url="http://127.0.0.1:1", gui_secret="secret")

    assert publisher.emit(GuiEvent(kind="run.start", run_id="rn_1")) == 1


def _project(name: str) -> Path:
    from bgs_translator.config import paths

    root = paths.project_root(name)
    root.mkdir(parents=True, exist_ok=True)
    return root
