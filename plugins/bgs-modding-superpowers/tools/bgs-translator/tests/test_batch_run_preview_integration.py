"""Prompt-preview IPC integration for ``xtl batch run``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner


def test_batch_run_requests_gui_preview_when_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.config.settings import Settings, save_settings
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.pipeline.clients.synthetic import SyntheticLLMClient

    save_settings(Settings.model_validate({"behavior": {"prompt_preview_required": True}}))
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Iron Sword")])
    conn.close()

    captured_requests: list[dict[str, Any]] = []
    captured_prompts: list[str] = []

    def fake_discover_gui() -> tuple[str, str]:
        return ("http://127.0.0.1:7847", "secret")

    def fake_request_preview_http(**kwargs: Any) -> dict[str, str]:
        captured_requests.append(
            {
                "batch_id": kwargs["batch_id"],
                "prompt": kwargs["system_prompt"],
                "items": kwargs["items"],
                "timeout": kwargs["timeout"],
            }
        )
        return {"op": "approved", "prompt": str(kwargs["system_prompt"]) + "\nEDITED BY GUI"}

    original_translate = SyntheticLLMClient.translate_batch

    async def capture_translate(
        self: SyntheticLLMClient, batch: Any, system_prompt: str
    ) -> Any:
        captured_prompts.append(system_prompt)
        return await original_translate(self, batch, system_prompt)

    monkeypatch.setattr("bgs_translator.cli.batch.discover_gui", fake_discover_gui)
    monkeypatch.setattr("bgs_translator.cli.batch.request_preview_http", fake_request_preview_http)
    monkeypatch.setattr(SyntheticLLMClient, "translate_batch", capture_translate)

    runner = CliRunner()
    planned = runner.invoke(
        app,
        [
            "batch",
            "plan",
            "demo",
            "--register",
            "dialogue",
            "--target-lang",
            "zh-cn",
            "--profile",
            "synthetic",
            "--game-lore",
            "Skyrim",
            "--mod-name",
            "Demo",
            "--mod-theme",
            "Weapons",
            "--style",
            "Concise",
        ],
    )
    assert planned.exit_code == 0, planned.output
    plan_id = json.loads(planned.output)["data"]["plan_id"]

    result = runner.invoke(app, ["batch", "run", "demo", "--plan", plan_id, "--dry-run", "--wait"])

    assert result.exit_code == 0, result.output
    assert len(captured_requests) == 1
    assert captured_requests[0]["batch_id"]
    assert captured_requests[0]["items"][0]["source_masked"] == "Iron Sword"
    assert captured_prompts == [captured_requests[0]["prompt"] + "\nEDITED BY GUI"]


def test_preview_no_gui_emits_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.config.settings import Settings, save_settings

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    save_settings(Settings.model_validate({"behavior": {"prompt_preview_required": True}}))
    plan_id = _create_preview_plan(tmp_path, monkeypatch)

    def fake_discover_gui() -> None:
        return None

    monkeypatch.setattr("bgs_translator.cli.batch.discover_gui", fake_discover_gui)

    result = CliRunner().invoke(app, ["batch", "run", "demo", "--plan", plan_id, "--dry-run", "--wait"])

    assert result.exit_code != 0
    assert "prompt_preview_required=true" in result.output
    assert '"abandoned": 1' in result.output


def test_unsupported_preview_backend_blocks_required_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.config.settings import Settings, save_settings

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    monkeypatch.setenv("BGS_TRANSLATOR_PREVIEW_BACKEND", "ipc")
    save_settings(Settings.model_validate({"behavior": {"prompt_preview_required": True}}))
    plan_id = _create_preview_plan(tmp_path, monkeypatch)

    result = CliRunner().invoke(app, ["batch", "run", "demo", "--plan", plan_id, "--dry-run", "--wait"])

    assert result.exit_code != 0
    assert "prompt_preview_required=true" in result.output
    assert '"abandoned": 1' in result.output


def _create_preview_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Iron Sword")])
    conn.close()

    planned = CliRunner().invoke(
        app,
        [
            "batch",
            "plan",
            "demo",
            "--register",
            "dialogue",
            "--target-lang",
            "zh-cn",
            "--profile",
            "synthetic",
        ],
    )
    assert planned.exit_code == 0, planned.output
    return str(json.loads(planned.output)["data"]["plan_id"])
