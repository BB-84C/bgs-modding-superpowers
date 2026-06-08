"""Tests for the Batches tab monitoring surface."""

from __future__ import annotations

from pathlib import Path

import pytest


def _need_tk_runtime() -> None:
    tkinter = pytest.importorskip("tkinter")
    try:
        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"Tk runtime unavailable: {exc}")


def _seed_run(project_root: Path) -> None:
    from bgs_translator.core.memory import open_memory_db

    conn = open_memory_db(project_root)
    conn.execute(
        """
        INSERT INTO runs (
            run_id, project, plan_id, started_at, completed_at, status,
            batches_total, cost_total_usd, cost_exact
        ) VALUES ('rn_recent', 'sample', 'plan_a', '2026-06-07T19:23:00+00:00', NULL,
                  'running', 2, 0.42, 0)
        """
    )
    conn.execute(
        """
        INSERT INTO batches (
            batch_id, run_id, plan_id, profile_snapshot_json, item_count,
            started_at, completed_at, status, tokens_in, tokens_out, cost_usd,
            cost_exact, retry_count, notes
        ) VALUES ('b_db', 'rn_recent', 'plan_a', '{"profile":"anthropic"}', 10,
                  '2026-06-07T19:23:01+00:00', NULL, 'running', 100, 80, 0.12, 0, 1, NULL)
        """
    )
    conn.commit()
    conn.close()


def test_batches_tab_updates_rows_from_batch_events(tmp_path: Path) -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.core.event_queue import EventQueueBridge, GuiEvent
    from bgs_translator.gui.tabs.batches_tab import BatchesTab

    bridge = EventQueueBridge()
    root = tk.Tk()
    try:
        tab = BatchesTab(root, project_root_provider=lambda: tmp_path, gui_event_bridge=bridge)

        bridge.emit(
            GuiEvent(
                kind="batch.start",
                run_id="rn_live",
                batch_id="b_live",
                payload={"client": "#1", "model": "claude", "total": 10},
            )
        )
        bridge.drain()
        assert "b_live" in tab._tree.get_children()

        bridge.emit(
            GuiEvent(
                kind="batch.progress",
                run_id="rn_live",
                batch_id="b_live",
                payload={"done": 5, "total": 10, "tokens_in": 1200, "tokens_out": 980, "cost": 0.06},
            )
        )
        bridge.drain()
        assert "50%" in tab._tree.set("b_live", "progress")
        assert tab._tree.set("b_live", "tokens") == "1200/980"

        bridge.emit(
            GuiEvent(kind="batch.complete", run_id="rn_live", batch_id="b_live", payload={"cost": 0.08})
        )
        bridge.drain()
        assert tab._tree.set("b_live", "status") == "complete"
        assert tab._summary_cost_var.get() == "Cost: $0.08"
    finally:
        root.destroy()


def test_batches_tab_lists_recent_runs_and_loads_batches(tmp_path: Path) -> None:
    _need_tk_runtime()
    import tkinter as tk

    from bgs_translator.gui.tabs.batches_tab import BatchesTab

    _seed_run(tmp_path)
    root = tk.Tk()
    try:
        tab = BatchesTab(root, project_root_provider=lambda: tmp_path)
        assert tab.list_recent_runs() == ["rn_recent"]

        tab.load_run("rn_recent")
        assert "b_db" in tab._tree.get_children()
        assert tab._tree.set("b_db", "tokens") == "100/80"
    finally:
        root.destroy()


def test_batches_cancel_confirmation_invokes_cancel_handler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _need_tk_runtime()
    import tkinter as tk
    from tkinter import messagebox

    from bgs_translator.gui.tabs.batches_tab import BatchesTab

    calls: list[str] = []
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    root = tk.Tk()
    try:
        tab = BatchesTab(
            root,
            project_root_provider=lambda: tmp_path,
            cancel_handler=lambda run_id: calls.append(run_id) or "cancelled",
        )
        tab._current_run_id = "rn_cancel"
        tab._upsert_batch("b_cancel", {"status": "running", "cost": 0.42})

        tab._on_cancel_run()

        assert calls == ["rn_cancel"]
        assert "cancelled" in tab._selected_run_var.get()
    finally:
        root.destroy()
