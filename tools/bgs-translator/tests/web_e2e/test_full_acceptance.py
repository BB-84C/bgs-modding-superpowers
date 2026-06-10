"""Full synthetic web-GUI acceptance for Phase 9."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner


def test_full_synthetic_round_trip_through_web_preview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    monkeypatch.setenv("BGS_TRANSLATOR_PREVIEW_BACKEND", "web")

    from bgs_translator.cli.app import app
    from bgs_translator.config import paths
    from bgs_translator.config.settings import Settings, save_settings
    from bgs_translator.core import runtime_pid
    from bgs_translator.core.event_publisher import reset_publishers_for_tests
    from bgs_translator.core.memory import fetch_events_for_run, insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret, remove_shared_secret

    reset_publishers_for_tests()
    web_app._PENDING_PREVIEWS.clear()
    save_settings(Settings.model_validate({"behavior": {"prompt_preview_required": True}}))

    project_root = paths.project_root("demo-web-acceptance")
    (project_root / "project.toml").parent.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text('[project]\ngame = "Starfield"\n', encoding="utf-8")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [
                TranslationUnit("adwryos.esm", 1, 1, "adwMenu", "MESG", "FULL", source="New Beginnings"),
                TranslationUnit("adwryos.esm", 2, 2, "adwStart", "MESG", "FULL", source="Pedestrian Starts"),
                TranslationUnit("adwryos.esm", 3, 3, "adwShip", "MESG", "FULL", source="Autopilot Engaged"),
            ],
        )
    finally:
        conn.close()

    port = _free_port()
    secret = ensure_shared_secret()
    translator_root = paths.translator_root()
    translator_root.mkdir(parents=True, exist_ok=True)
    (translator_root / "gui.port").write_text(str(port), encoding="utf-8")
    runtime_pid.write_gui_pid()

    server, server_thread = _start_uvicorn(web_app.fastapi_app, port)
    approvals: list[dict[str, Any]] = []
    approver_stop = threading.Event()
    approver = threading.Thread(
        target=_approve_pending_previews,
        args=(port, secret, approvals, approver_stop),
        daemon=True,
    )
    approver.start()

    try:
        planned = CliRunner().invoke(
            app,
            [
                "batch",
                "plan",
                "demo-web-acceptance",
                "--register",
                "dialogue",
                "--target-lang",
                "zh-cn",
                "--profile",
                "synthetic",
                "--batch-size",
                "1",
                "--game-lore-world",
                "Starfield 2330 Settled Systems",
                "--game-lore-summary",
                "RYOS alternate-start context for Starfield menus, character starts, ships, and NG+ options.",
                "--mod-name",
                "RYOS - Roll Your Own Start",
                "--mod-theme",
                "Alternate start menu and start-condition configuration.",
                "--style",
                "Chinese UI labels should be concise and player-facing.",
            ],
        )
        assert planned.exit_code == 0, planned.output
        plan_id = json.loads(planned.output)["data"]["plan_id"]

        result = CliRunner().invoke(
            app,
            ["batch", "run", "demo-web-acceptance", "--plan", plan_id, "--dry-run", "--wait"],
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["data"]["dry_run"] is True
        run_id = envelope["data"]["run_id"]
        summary = envelope["data"]["summary"]

        assert summary["succeeded"] == 3
        assert summary["manual_review"] == 0
        assert summary["cancelled"] == 0
        assert summary["cost_usd"] >= 0.0
        assert len(approvals) == 3
        assert {item["item_count"] for item in approvals} == {1}

        headers = {"Authorization": f"Bearer {secret}"}
        batches_response = httpx.get(
            f"http://127.0.0.1:{port}/api/projects/demo-web-acceptance/runs/{run_id}/batches",
            headers=headers,
            timeout=10.0,
        )
        assert batches_response.status_code == 200
        batches = batches_response.json()
        assert len(batches) == 3
        assert {batch["status"] for batch in batches} == {"complete"}

        conn = open_memory_db(project_root)
        try:
            events = fetch_events_for_run(conn, run_id, 0)
        finally:
            conn.close()
        kinds = [str(event["kind"]) for event in events]
        assert kinds.count("prompt.preview_request") == 3
        assert kinds.count("batch.complete") == 3
        assert "run.complete" in kinds

        run_dir = project_root / "batches" / run_id
        for relative in [
            "plan.json",
            "system-prompt.md",
            "results.json",
            "status.toml",
            "validator-failures.jsonl",
            "responses",
        ]:
            assert (run_dir / relative).exists()
    finally:
        approver_stop.set()
        approver.join(timeout=5.0)
        server.should_exit = True
        server_thread.join(timeout=10.0)
        runtime_pid.remove_gui_pid()
        remove_shared_secret()
        try:
            (translator_root / "gui.port").unlink()
        except FileNotFoundError:
            pass
        web_app._PENDING_PREVIEWS.clear()
        reset_publishers_for_tests()
        monkeypatch.delenv("BGS_TRANSLATOR_PREVIEW_BACKEND", raising=False)


def _approve_pending_previews(
    port: int,
    secret: str,
    approvals: list[dict[str, Any]],
    stop: threading.Event,
) -> None:
    headers = {"Authorization": f"Bearer {secret}"}
    seen: set[tuple[str, str]] = set()
    deadline = time.monotonic() + 30.0
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            pending = httpx.get(
                f"http://127.0.0.1:{port}/api/preview/pending",
                headers=headers,
                timeout=2.0,
            ).json()
        except httpx.HTTPError:
            time.sleep(0.05)
            continue
        for item in pending:
            key = (str(item["run_id"]), str(item["batch_id"]))
            if key in seen:
                continue
            seen.add(key)
            approvals.append({"batch_id": key[1], "item_count": len(item.get("items") or [])})
            response = httpx.post(
                f"http://127.0.0.1:{port}/api/preview/respond/{key[0]}/{key[1]}",
                headers=headers,
                json={"op": "approved", "prompt": f"{item['system_prompt']}\nSYNTHETIC_ACCEPTED"},
                timeout=10.0,
            )
            response.raise_for_status()
        time.sleep(0.05)


def _start_uvicorn(app: Any, port: int) -> tuple[Any, threading.Thread]:
    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="off")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1.0)
            if response.status_code == 200:
                return server, thread
        except httpx.HTTPError:
            time.sleep(0.05)
    server.should_exit = True
    thread.join(timeout=5.0)
    raise RuntimeError("web acceptance server did not start")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
