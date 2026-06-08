"""Batches tab: live run monitoring and cancellation controls."""

from __future__ import annotations

import json
import subprocess
import tkinter as tk
import tomllib
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from bgs_translator.core.event_queue import EventQueueBridge, GuiEvent
from bgs_translator.core.memory import (
    list_recent_runs as memory_list_recent_runs,
)
from bgs_translator.core.memory import (
    open_memory_db,
    select_batches_for_run,
)
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.themes import ThemeConfig, get_theme
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.empty_state import EmptyStatePanel
from bgs_translator.gui.widgets.progress_cell import render_progress_bar
from bgs_translator.gui.widgets.sparkline import Sparkline

ProjectRootProvider = Callable[[], Path | None]
CancelHandler = Callable[[str], str]


@dataclass
class BatchState:
    """One row of batch-monitor state."""

    batch_id: str
    run_id: str | None = None
    client: str = "-"
    model: str = "-"
    profile: str = "-"
    done: int = 0
    total: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost: float | None = None
    status: str = "queued"
    retry_count: int = 0


class BatchesTab(ttk.Frame):
    """Primary monitoring surface for translation batches."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        project_root_provider: ProjectRootProvider | None = None,
        theme: ThemeConfig | str | None = None,
        gui_event_bridge: EventQueueBridge | None = None,
        cancel_handler: CancelHandler | None = None,
    ) -> None:
        super().__init__(parent, padding=(8, 8))
        self._get_project_root = project_root_provider or (lambda: None)
        self._theme = get_theme(theme) if isinstance(theme, str) else theme or get_theme("amber")
        self._event_bridge = gui_event_bridge
        self._cancel_handler = cancel_handler
        self._unsubscribe: Callable[[], None] | None = None
        self._current_run_id: str | None = None
        self._batches: list[BatchState] = []
        self._throughput_buf: deque[float] = deque(maxlen=30)
        self._cost_buf: deque[float] = deque(maxlen=60)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_run_selector()
        self._build_batch_table()
        self._build_sparklines()
        self._build_summary()

        self._empty_state = EmptyStatePanel(
            self,
            caption=_("[ NO RUNS YET ]"),
            sub_line=_("Start a batch from the CLI: xtl batch run <project> --plan <plan_id>"),
            theme_name=self._theme.name,
        )
        self._show_empty_state(True)

        if self._event_bridge is not None:
            self._unsubscribe = self._event_bridge.subscribe(self._on_event)

    def attach_app(self, app: object) -> None:
        """Follow-up integration seam for app-level wiring without editing app.py here."""

        provider = getattr(app, "current_project_root", None)
        if callable(provider):
            self._get_project_root = provider

    def destroy(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        super().destroy()

    def _build_run_selector(self) -> None:
        top = ttk.Frame(self, style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        self._selected_run_var = tk.StringVar(value="")
        self._in_flight_only_var = tk.BooleanVar(value=False)

        ttk.Label(top, text=f"{_('Run')}:", style="Phosphor.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._run_combo = ttk.Combobox(top, textvariable=self._selected_run_var, values=(), state="readonly", width=28)
        self._run_combo.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self._run_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_run(self._selected_run_var.get()))
        ttk.Checkbutton(top, text=_("In-flight only"), variable=self._in_flight_only_var, command=self._refresh_tree).grid(
            row=0, column=2, sticky="w", padx=(0, 12)
        )
        ttk.Button(top, text=_("Refresh"), command=self._refresh_runs).grid(row=0, column=3, sticky="e")

    def _build_batch_table(self) -> None:
        table_frame = ttk.Frame(self, style="Surface.TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("batch_id", "client", "model", "progress", "tokens", "cost", "status")
        self._tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "batch_id": _("Batch ID"),
            "client": _("Client"),
            "model": _("Model"),
            "progress": _("Progress"),
            "tokens": "Toks In/Out",
            "cost": _("Cost"),
            "status": "Stat",
        }
        widths = {"batch_id": 130, "client": 80, "model": 180, "progress": 150, "tokens": 110, "cost": 80, "status": 90}
        for column in columns:
            self._tree.heading(column, text=headings[column])
            self._tree.column(column, width=widths[column], minwidth=55, stretch=column in {"model", "progress"})
        y_scroll = AmberScrollbar(table_frame, orient="vertical", command=self._tree.yview, theme_name=self._theme.name)
        self._tree.configure(yscrollcommand=y_scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")

    def _build_sparklines(self) -> None:
        frame = ttk.Frame(self, style="Surface.TFrame")
        frame.grid(row=2, column=0, sticky="ew", pady=(8, 8))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        ttk.Label(frame, text=_("Throughput"), style="Phosphor.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._throughput_sparkline = Sparkline(frame, values=self._throughput_buf, maxlen=30, theme_name=self._theme.name)
        self._throughput_sparkline.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        ttk.Label(frame, text=_("Cumulative cost"), style="Phosphor.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self._cost_sparkline = Sparkline(frame, values=self._cost_buf, maxlen=60, theme_name=self._theme.name)
        self._cost_sparkline.grid(row=0, column=3, sticky="ew")

    def _build_summary(self) -> None:
        frame = ttk.Frame(self, style="Surface.TFrame")
        frame.grid(row=3, column=0, sticky="ew")
        for column in range(7):
            frame.columnconfigure(column, weight=0)
        frame.columnconfigure(6, weight=1)
        self._summary_total_var = tk.StringVar(value="Total: 0 items")
        self._summary_succeeded_var = tk.StringVar(value="Succeeded: 0")
        self._summary_retried_var = tk.StringVar(value="Retried: 0")
        self._summary_manual_var = tk.StringVar(value="Manual: 0")
        self._summary_cost_var = tk.StringVar(value="Cost: $0.00")
        for index, var in enumerate(
            (
                self._summary_total_var,
                self._summary_succeeded_var,
                self._summary_retried_var,
                self._summary_manual_var,
                self._summary_cost_var,
            )
        ):
            ttk.Label(frame, textvariable=var, style="Dim.TLabel").grid(row=0, column=index, sticky="w", padx=(0, 12))
        ttk.Button(frame, text=_("Cancel entire run"), command=self._on_cancel_run).grid(row=0, column=6, sticky="e")

    def _on_event(self, event: GuiEvent) -> None:
        if event.kind.startswith("batch."):
            if event.run_id is not None and self._current_run_id not in {None, event.run_id}:
                return
            self._current_run_id = event.run_id or self._current_run_id
            if self._current_run_id is not None:
                self._selected_run_var.set(self._current_run_id)
            if event.batch_id is None:
                return
            payload = dict(event.payload)
            if event.kind == "batch.start":
                payload.setdefault("status", "running")
                payload.setdefault("done", 0)
            elif event.kind == "batch.progress":
                payload.setdefault("status", "running")
            elif event.kind == "batch.complete":
                payload.setdefault("status", "complete")
                batch = self._find_batch(event.batch_id)
                if batch is not None:
                    payload.setdefault("done", batch.total or batch.done)
            elif event.kind == "batch.failed":
                payload.setdefault("status", "failed")
            elif event.kind == "batch.cancelled":
                payload.setdefault("status", "cancelled")
            self._upsert_batch(event.batch_id, payload, run_id=event.run_id)
            self._refresh_tree()
            self._refresh_summary()
            self._show_empty_state(False)
        elif event.kind == "cost.update":
            cost = _payload_float(event.payload, "cost", default=0.0)
            self._cost_sparkline.update_value(cost)
            self._refresh_summary(extra_cost=cost)

    def load_run(self, run_id: str) -> None:
        """Read project memory/status files for one run and render it."""

        if not run_id:
            return
        self._current_run_id = run_id
        self._selected_run_var.set(run_id)
        self._batches.clear()
        project_root = self._get_project_root()
        if project_root is None:
            self._refresh_tree()
            self._show_empty_state(True)
            return
        conn = open_memory_db(project_root)
        try:
            rows = select_batches_for_run(conn, run_id)
        finally:
            conn.close()
        if rows:
            for row in rows:
                profile, model = _profile_model_from_snapshot(str(row["profile_snapshot_json"]))
                self._batches.append(
                    BatchState(
                        batch_id=str(row["batch_id"]),
                        run_id=str(row["run_id"]),
                        client="-",
                        model=model,
                        profile=profile,
                        done=int(row["item_count"] if row["status"] == "complete" else 0),
                        total=int(row["item_count"]),
                        tokens_in=_optional_int(row["tokens_in"]),
                        tokens_out=_optional_int(row["tokens_out"]),
                        cost=_optional_float(row["cost_usd"]),
                        status=str(row["status"]),
                        retry_count=int(row["retry_count"] or 0),
                    )
                )
        else:
            self._load_run_sidecar(project_root, run_id)
        self._refresh_tree()
        self._refresh_summary()
        self._show_empty_state(not self._batches)

    def list_recent_runs(self) -> list[str]:
        """Return recent run ids from project memory."""

        project_root = self._get_project_root()
        if project_root is None:
            return []
        conn = open_memory_db(project_root)
        try:
            rows = memory_list_recent_runs(conn, limit=20)
        finally:
            conn.close()
        return [str(row["run_id"]) for row in rows]

    def _refresh_runs(self) -> None:
        runs = self.list_recent_runs()
        self._run_combo.configure(values=tuple(runs))
        if runs and not self._selected_run_var.get():
            self.load_run(runs[0])

    def _upsert_batch(self, batch_id: str, payload: dict[str, Any], run_id: str | None = None) -> None:
        batch = self._find_batch(batch_id)
        if batch is None:
            batch = BatchState(batch_id=batch_id, run_id=run_id or self._current_run_id)
            self._batches.append(batch)
        batch.run_id = run_id or batch.run_id or self._current_run_id
        batch.client = str(payload.get("client", batch.client))
        batch.model = str(payload.get("model", batch.model))
        batch.profile = str(payload.get("profile", batch.profile))
        batch.done = _payload_int(payload, "done", default=batch.done)
        batch.total = _payload_int(payload, "total", "item_count", default=batch.total)
        batch.tokens_in = _payload_optional_int(payload, "tokens_in", default=batch.tokens_in)
        batch.tokens_out = _payload_optional_int(payload, "tokens_out", default=batch.tokens_out)
        batch.cost = _payload_optional_float(payload, "cost", "cost_usd", default=batch.cost)
        batch.status = str(payload.get("status", batch.status))
        batch.retry_count = _payload_int(payload, "retry_count", default=batch.retry_count)
        self._throughput_sparkline.update_value(float(batch.done))
        self._cost_sparkline.update_value(batch.cost or 0.0)

    def _on_cancel_run(self) -> None:
        if self._current_run_id is None:
            return
        if not self._confirm_cancel_run(self._current_run_id):
            return
        result = self._cancel_run(self._current_run_id)
        self._selected_run_var.set(f"{self._current_run_id} — {result}")
        for batch in self._batches:
            if batch.status in {"running", "queued", "retrying"}:
                batch.status = "cancelled"
        self._refresh_tree()
        self._refresh_summary()

    def _confirm_cancel_run(self, run_id: str) -> bool:
        in_flight = sum(1 for batch in self._batches if batch.status in {"running", "queued", "retrying"})
        cost = sum(batch.cost or 0.0 for batch in self._batches)
        low = cost * 0.8
        high = cost * 1.2
        message = (
            f"In-flight batches: {in_flight}\n"
            f"Cost so far: ${cost:.2f} (±20%: ${low:.2f} - ${high:.2f})\n\n"
            "Warning: provider may have already billed for in-flight tokens.\n"
            "Cancel anyway?"
        )
        return bool(
            messagebox.askyesno(
                f"Cancel run {run_id}?",
                message,
                default=messagebox.NO,
            )
        )

    def _cancel_run(self, run_id: str) -> str:
        if self._cancel_handler is not None:
            return self._cancel_handler(run_id)
        completed = subprocess.run(
            ["xtl", "batch", "cancel", run_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return (completed.stdout or "cancel requested").strip()
        return (completed.stderr or completed.stdout or "cancel failed").strip()

    def _load_run_sidecar(self, project_root: Path, run_id: str) -> None:
        run_dir = project_root / "batches" / run_id
        status_path = run_dir / "status.toml"
        if not status_path.exists():
            return
        data = tomllib.loads(status_path.read_text(encoding="utf-8"))
        raw_batches = data.get("batches", [])
        if isinstance(raw_batches, list):
            for item in raw_batches:
                if isinstance(item, dict) and "batch_id" in item:
                    batch_id = str(item["batch_id"])
                    self._upsert_batch(batch_id, item, run_id=run_id)

    def _refresh_tree(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for batch in self._visible_batches():
            self._tree.insert(
                "",
                "end",
                iid=batch.batch_id,
                values=(
                    batch.batch_id,
                    batch.client,
                    batch.model,
                    self._format_progress(batch),
                    self._format_tokens(batch),
                    self._format_cost(batch.cost),
                    batch.status,
                ),
            )

    def _refresh_summary(self, extra_cost: float | None = None) -> None:
        total_items = sum(batch.total for batch in self._batches)
        succeeded = sum(1 for batch in self._batches if batch.status == "complete")
        retried = sum(batch.retry_count for batch in self._batches)
        manual = sum(1 for batch in self._batches if batch.status == "manual")
        cost = extra_cost if extra_cost is not None else sum(batch.cost or 0.0 for batch in self._batches)
        self._summary_total_var.set(f"Total: {total_items} items")
        self._summary_succeeded_var.set(f"Succeeded: {succeeded}")
        self._summary_retried_var.set(f"Retried: {retried}")
        self._summary_manual_var.set(f"Manual: {manual}")
        self._summary_cost_var.set(f"Cost: ${cost:.2f}")

    def _visible_batches(self) -> list[BatchState]:
        if not self._in_flight_only_var.get():
            return list(self._batches)
        return [batch for batch in self._batches if batch.status in {"running", "queued", "retrying"}]

    def _find_batch(self, batch_id: str) -> BatchState | None:
        return next((batch for batch in self._batches if batch.batch_id == batch_id), None)

    def _show_empty_state(self, show: bool) -> None:
        if show:
            self._empty_state.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._empty_state.lift()
        else:
            self._empty_state.place_forget()

    @staticmethod
    def _format_progress(batch: BatchState) -> str:
        total = max(0, batch.total)
        done = min(max(0, batch.done), total) if total else max(0, batch.done)
        percent = 0 if total <= 0 else int((done / total) * 100)
        return f"{render_progress_bar(done, total)} {percent:3d}%"

    @staticmethod
    def _format_tokens(batch: BatchState) -> str:
        tokens_in = "-" if batch.tokens_in is None else str(batch.tokens_in)
        tokens_out = "-" if batch.tokens_out is None else str(batch.tokens_out)
        return f"{tokens_in}/{tokens_out}"

    @staticmethod
    def _format_cost(cost: float | None) -> str:
        return "-" if cost is None else f"${cost:.2f}"


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float | str | bytes | bytearray):
        return int(value)
    return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | str | bytes | bytearray):
        return float(value)
    return None


def _payload_int(payload: dict[str, Any], *keys: str, default: int) -> int:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return int(value)
    return default


def _payload_float(payload: dict[str, Any], key: str, *, default: float) -> float:
    value = payload.get(key)
    return default if value is None else float(value)


def _payload_optional_int(payload: dict[str, Any], key: str, *, default: int | None) -> int | None:
    value = payload.get(key)
    return default if value is None else int(value)


def _payload_optional_float(payload: dict[str, Any], *keys: str, default: float | None) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return float(value)
    return default


def _profile_model_from_snapshot(raw: str) -> tuple[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ("-", "-")
    if not isinstance(data, dict):
        return ("-", "-")
    profile = str(data.get("profile") or data.get("name") or "-")
    model = str(data.get("model") or "-")
    return (profile, model)


__all__ = ["BatchState", "BatchesTab"]
