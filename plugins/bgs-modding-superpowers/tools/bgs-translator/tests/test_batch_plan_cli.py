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


def test_batch_plan_cli_uses_queue_batch_size_and_order(
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
            TranslationUnit("A.esp", index, index, f"Q{index}", "QUST", "FULL", source=f"Quest {index}")
            for index in range(1, 6)
        ]
        + [TranslationUnit("A.esp", 6, 6, "Q6", "QUST", "QMDP", source="<Alias=TargetLocation>")],
    )
    rows = conn.execute("SELECT row_id, source FROM units ORDER BY formid").fetchall()
    conn.close()
    by_source = {str(source): str(row_id) for row_id, source in rows}
    queued = [
        by_source["Quest 5"],
        by_source["Quest 3"],
        by_source["<Alias=TargetLocation>"],
        by_source["Quest 1"],
        by_source["Quest 4"],
        by_source["Quest 2"],
    ]
    queue_dir = project_root / "batches" / "selection-queue"
    queue_dir.mkdir(parents=True)
    (queue_dir / "queue-sized.json").write_text(
        json.dumps({"queue_id": "queue-sized", "row_ids": queued, "batch_size": 2}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "batch",
            "plan",
            "demo",
            "--queue",
            "queue-sized",
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
    assert envelope["data"]["batch_size"] == 2
    assert envelope["data"]["selected_item_count"] == 6
    assert envelope["data"]["candidate_item_count"] == 6
    assert envelope["data"]["skipped_item_count"] == 1
    assert envelope["data"]["skipped_reasons"] == {"all_protected": 1}
    plan_json = json.loads(Path(envelope["data"]["plan_path"]).read_text(encoding="utf-8"))
    assert [len(batch["items"]) for batch in plan_json["batches"]] == [2, 2, 1]
    sources = [item["unit"]["source"] for batch in plan_json["batches"] for item in batch["items"]]
    assert sources == ["Quest 5", "Quest 3", "Quest 1", "Quest 4", "Quest 2"]


def test_batch_plan_cli_reports_translation_budget_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bgs_translator.cli.app import app
    from bgs_translator.config.settings import Settings, save_settings
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit

    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    save_settings(
        Settings.model_validate(
            {
                "behavior": {
                    "glossary_max_terms": 777,
                    "glossary_max_prompt_chars": 123456,
                    "glossary_candidate_source_terms": 88,
                }
            }
        )
    )
    project_root = tmp_path / "translator" / "projects" / "demo"
    conn = open_memory_db(project_root)
    insert_units(conn, [TranslationUnit("A.esp", 1, 1, "A", "QUST", "FULL", source="Quest Board")])
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
    assert envelope["data"]["glossary_max_terms"] == 777
    assert envelope["data"]["glossary_max_prompt_chars"] == 123456
    assert envelope["data"]["glossary_candidate_source_terms"] == 88


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
    assert "Iron Sword → 铁剑" in plan_json["batches"][0]["system_prompt"]

    from bgs_translator.cli.batch import _load_plan

    loaded = _load_plan(plan_path)
    assert [entry.source for entry in loaded.batches[0].glossary_subset] == ["Iron Sword"]
    assert loaded.batches[0].system_prompt is not None
    assert "Iron Sword → 铁剑" in loaded.batches[0].system_prompt
