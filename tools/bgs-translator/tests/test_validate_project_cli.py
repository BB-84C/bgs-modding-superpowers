"""Tests for project validation CLI."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import tomli_w
from typer.testing import CliRunner

from bgs_translator.core.memory import open_memory_db
from bgs_translator.sst.status import SStrParam


def _run_validate(args: list[str]) -> dict[str, Any]:
    from bgs_translator.cli.app import app

    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    loaded = json.loads(result.output)
    assert isinstance(loaded, dict)
    return loaded


def _make_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    project_root = tmp_path / "translator" / "projects" / "validate-project"
    (project_root / "sources").mkdir(parents=True, exist_ok=True)
    plugin = tmp_path / "Validate.esm"
    plugin.write_bytes(b"original plugin bytes")
    stale_sha = hashlib.sha256(plugin.read_bytes()).hexdigest()
    plugin.write_bytes(b"changed plugin bytes")
    project_toml = {
        "project": {
            "name": "validate-project",
            "game": "Starfield",
            "source_plugin_path": str(plugin),
            "source_plugin_sha256": stale_sha,
        }
    }
    (project_root / "project.toml").write_text(tomli_w.dumps(project_toml), encoding="utf-8")
    (project_root / "sources" / "Validate.esm.cache.toml").write_text(
        tomli_w.dumps({"plugin_sha256": stale_sha}), encoding="utf-8"
    )

    conn = open_memory_db(project_root)
    old = (datetime.now(UTC) - timedelta(days=45)).isoformat()
    rows = [
        ("r_old", "WEAP", "FULL", "Iron Sword", None, "untranslated", 0, old),
        ("r_partial", "WEAP", "DESC", "Sharp blade", "锋利刀刃", "partial", 0, old),
        (
            "r_incomplete",
            "ARMO",
            "FULL",
            "Iron Armor",
            "铁甲",
            "translated",
            int(SStrParam.INCOMPLETE_TRANS),
            old,
        ),
        ("r_bad", "WEAP", "FULL", "Requires SKSE", "需要脚本扩展器", "translated", 0, old),
    ]
    for idx, (row_id, sig, field, source, dest, status, sparams, updated_at) in enumerate(
        rows, start=1
    ):
        conn.execute(
            """
            INSERT INTO units (
                row_id, plugin, formid, formid_sanitized, edid, signature, field,
                index_n, index_max, source, list_index, strid, rhash,
                parent_context_json, dest, status, sparams, via_llm, retry_count, updated_at
            ) VALUES (?, 'Validate.esm', ?, ?, ?, ?, ?, 0, 0, ?, 0, 0, 0, NULL, ?, ?, ?, 0, 0, ?)
            """,
            (row_id, idx, idx, f"EDID_{idx}", sig, field, source, dest, status, sparams, updated_at),
        )
    conn.commit()
    conn.close()
    return project_root


def test_validate_project_reports_orphans_partials_cache_drift_and_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_project(tmp_path, monkeypatch)

    envelope = _run_validate(["validate", "project", "validate-project"])

    assert envelope["ok"] is True
    data = envelope["data"]
    assert data["severity"] == "error"
    assert {item["row_id"] for item in data["findings"]["orphans"]} == {"r_old"}
    assert {item["row_id"] for item in data["findings"]["partials"]} == {
        "r_partial",
        "r_incomplete",
    }
    assert data["findings"]["cache_freshness"][0]["severity"] == "warn"
    assert data["findings"]["validator_replay"][0]["row_id"] == "r_bad"
    assert data["findings"]["coverage_gaps"]


def test_validate_project_severity_escalates_error_over_warn_over_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = _make_project(tmp_path, monkeypatch)
    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    conn.execute("DELETE FROM units WHERE row_id = 'r_bad'")
    conn.commit()
    conn.close()

    warn_envelope = _run_validate(["validate", "project", "validate-project"])
    assert warn_envelope["data"]["severity"] == "warn"

    plugin = tmp_path / "Validate.esm"
    cache_toml = project_root / "sources" / "Validate.esm.cache.toml"
    fresh_sha = hashlib.sha256(plugin.read_bytes()).hexdigest()
    cache_toml.write_text(tomli_w.dumps({"plugin_sha256": fresh_sha}), encoding="utf-8")
    project_toml = {
        "project": {
            "name": "validate-project",
            "game": "Starfield",
            "source_plugin_path": str(plugin),
            "source_plugin_sha256": fresh_sha,
        }
    }
    (project_root / "project.toml").write_text(tomli_w.dumps(project_toml), encoding="utf-8")

    info_envelope = _run_validate(["validate", "project", "validate-project"])
    assert info_envelope["data"]["severity"] == "info"
