"""Tests for edit CLI subcommands."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from bgs_translator.core.memory import open_memory_db
from bgs_translator.sst.status import SStrParam


def _make_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list[str]]:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    project_root = tmp_path / "translator" / "projects" / "edit-project"
    conn = open_memory_db(project_root)
    rows = [
        ("r_weap_1", "WEAP", "FULL", "Iron Sword", None, "untranslated", 0),
        ("r_weap_2", "WEAP", "DESC", "Sharp blade", None, "untranslated", 0),
        ("r_armo_1", "ARMO", "FULL", "Iron Armor", None, "untranslated", 0),
    ]
    for idx, (row_id, sig, field, source, dest, status, sparams) in enumerate(rows, start=1):
        conn.execute(
            """
            INSERT INTO units (
                row_id, plugin, formid, formid_sanitized, edid, signature, field,
                index_n, index_max, source, list_index, strid, rhash,
                parent_context_json, dest, status, sparams, via_llm, retry_count, updated_at
            ) VALUES (?, 'Fixture.esm', ?, ?, ?, ?, ?, 0, 0, ?, 0, 0, 0, NULL, ?, ?, ?, 0, 0, '2026-01-01T00:00:00+00:00')
            """,
            (row_id, idx, idx, f"EDID_{idx}", sig, field, source, dest, status, sparams),
        )
    conn.commit()
    conn.close()
    return project_root, [row[0] for row in rows]


def _run_json(args: list[str]) -> dict[str, Any]:
    from bgs_translator.cli.app import app

    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    loaded = json.loads(result.output)
    assert isinstance(loaded, dict)
    return loaded


def _row(project_root: Path, row_id: str) -> sqlite3.Row:
    conn = sqlite3.connect(project_root / "memory" / "memory.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM units WHERE row_id = ?", (row_id,)).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def test_edit_entry_updates_memory_and_appends_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, row_ids = _make_project(tmp_path, monkeypatch)

    envelope = _run_json(
        [
            "edit",
            "entry",
            "edit-project",
            row_ids[0],
            "--dest",
            "铁剑",
            "--status",
            "translated",
            "--reason",
            "manual correction",
        ]
    )

    assert envelope["ok"] is True
    assert envelope["data"]["unit"]["dest"] == "铁剑"
    row = _row(project_root, row_ids[0])
    assert row["dest"] == "铁剑"
    assert row["status"] == "translated"
    assert row["via_llm"] == 0
    assert row["profile_used"] == "manual-edit"
    audits = list((project_root / "batches" / "manual-edits").glob("*.jsonl"))
    assert len(audits) == 1
    audit = json.loads(audits[0].read_text(encoding="utf-8").splitlines()[0])
    assert audit["row_id"] == row_ids[0]
    assert audit["before"]["dest"] is None
    assert audit["after"]["dest"] == "铁剑"
    assert audit["reason"] == "manual correction"


def test_edit_bulk_applies_jsonl_and_dry_run_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, row_ids = _make_project(tmp_path, monkeypatch)
    input_file = tmp_path / "bulk.jsonl"
    input_file.write_text(
        "\n".join(
            [
                json.dumps({"row_id": row_ids[0], "dest": "铁剑", "status": "translated"}),
                json.dumps({"row_id": row_ids[1], "dest": "锋利刀刃", "status": "partial"}),
                json.dumps({"row_id": row_ids[2], "dest": "铁甲", "status": "locked"}),
            ]
        ),
        encoding="utf-8",
    )

    dry = _run_json(["edit", "bulk", "edit-project", "--input", str(input_file), "--dry-run"])
    assert dry["data"]["applied_count"] == 0
    assert dry["data"]["would_apply_count"] == 3
    assert _row(project_root, row_ids[0])["dest"] is None

    applied = _run_json(["edit", "bulk", "edit-project", "--input", str(input_file)])

    assert applied["data"]["applied_count"] == 3
    assert applied["data"]["skipped_count"] == 0
    assert _row(project_root, row_ids[0])["dest"] == "铁剑"
    assert _row(project_root, row_ids[1])["status"] == "partial"
    assert _row(project_root, row_ids[2])["status"] == "locked"


def test_edit_bulk_skips_malformed_line_and_reports_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project_root, row_ids = _make_project(tmp_path, monkeypatch)
    input_file = tmp_path / "bulk-bad.jsonl"
    input_file.write_text(
        "\n".join(
            [
                json.dumps({"row_id": row_ids[0], "dest": "铁剑"}),
                "{not-json",
                json.dumps({"row_id": "missing", "dest": "不存在"}),
            ]
        ),
        encoding="utf-8",
    )

    envelope = _run_json(["edit", "bulk", "edit-project", "--input", str(input_file)])

    assert envelope["data"]["applied_count"] == 1
    assert envelope["data"]["skipped_count"] == 2
    assert [error["line"] for error in envelope["data"]["errors"]] == [2, 3]


def test_edit_status_filters_signature_and_sets_sparams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, row_ids = _make_project(tmp_path, monkeypatch)

    envelope = _run_json(
        ["edit", "status", "edit-project", "locked", "--sig", "WEAP", "--yes"]
    )

    assert envelope["data"]["affected_count"] == 2
    assert _row(project_root, row_ids[0])["status"] == "locked"
    assert _row(project_root, row_ids[1])["sparams"] == int(SStrParam.LOCKED_TRANS)
    assert _row(project_root, row_ids[2])["status"] == "untranslated"


def test_edit_revert_restores_previous_manual_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, row_ids = _make_project(tmp_path, monkeypatch)
    _run_json(
        ["edit", "entry", "edit-project", row_ids[0], "--dest", "铁剑", "--status", "translated"]
    )

    envelope = _run_json(["edit", "revert", "edit-project", row_ids[0]])

    assert envelope["ok"] is True
    row = _row(project_root, row_ids[0])
    assert row["dest"] is None
    assert row["status"] == "untranslated"
    audits = list((project_root / "batches" / "manual-edits").glob("*.jsonl"))
    entries = [json.loads(line) for path in audits for line in path.read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["operation"] == "revert"
