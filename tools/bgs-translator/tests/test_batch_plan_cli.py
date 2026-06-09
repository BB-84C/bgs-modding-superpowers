"""Tests for ``xtl batch plan``."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

GlossaryPackFactory = Callable[[str, Sequence[Mapping[str, object]], bool], Path]


def test_batch_plan_cli_persists_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Iron Sword")])

    result = CliRunner().invoke(
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
            "fake",
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
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    plan_path = Path(envelope["data"]["plan_path"])
    assert plan_path.exists()
    plan_json = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan_json["plan_id"] == envelope["data"]["plan_id"]
    assert plan_json["total_items"] == 1


def test_batch_plan_cli_accepts_gui_selection_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(
        conn,
        [
            TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Queued Sword"),
            TranslationUnit("A.esp", 2, 2, "B", "WEAP", "FULL", source="Other Sword"),
        ],
    )
    row_id = str(conn.execute("SELECT row_id FROM units WHERE source = 'Queued Sword'").fetchone()[0])
    conn.close()
    queue_dir = project_root / "batches" / "selection-queue"
    queue_dir.mkdir(parents=True)
    (queue_dir / "queue-test.json").write_text(
        json.dumps({"queue_id": "queue-test", "row_ids": [row_id]}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "batch",
            "plan",
            "demo",
            "--queue",
            "queue-test",
            "--register",
            "dialogue",
            "--target-lang",
            "zh-cn",
            "--profile",
            "fake",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["selected_row_ids"] == [row_id]
    plan_json = json.loads(Path(envelope["data"]["plan_path"]).read_text(encoding="utf-8"))
    sources = [item["unit"]["source"] for batch in plan_json["batches"] for item in batch["items"]]
    assert sources == ["Queued Sword"]


def test_batch_plan_splits_lore_world_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "MESG", "FULL", source="Start")])
    conn.close()

    result = CliRunner().invoke(
        app,
        [
            "batch",
            "plan",
            "demo",
            "--register",
            "system_message",
            "--target-lang",
            "zh-cn",
            "--profile",
            "fake",
            "--game-lore-world",
            "World Header Only",
            "--game-lore-summary",
            "Detailed lore paragraph only.",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    plan_json = json.loads(Path(envelope["data"]["plan_path"]).read_text(encoding="utf-8"))
    prompt = plan_json["sample_system_prompt"]
    assert "World Header Only" in prompt
    assert "Detailed lore paragraph only." in prompt
    assert prompt.count("World Header Only") == 1


def test_batch_plan_queries_real_glossary_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_fixture_pack: GlossaryPackFactory
) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    monkeypatch.setenv("BGS_KB_USER_PACKS", str(tmp_path / "user-packs"))
    make_fixture_pack(
        "translator-overrides-en-zhcn",
        [
            {
                "record_id": "glossary.test.iron-sword",
                "source": "Iron Sword",
                "target": "铁剑",
                "target_lang": "zh-cn",
                "scope": "player",
                "category": "item",
                "confidence": "canonical",
            }
        ],
        True,
    )
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "WEAP", "FULL", source="Iron Sword")])
    conn.close()

    result = CliRunner().invoke(
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
            "fake",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    plan_path = Path(envelope["data"]["plan_path"])
    plan_json = json.loads(plan_path.read_text(encoding="utf-8"))
    assert "Iron Sword → 铁剑" in plan_json["sample_system_prompt"]
