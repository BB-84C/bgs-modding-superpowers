"""Smoke tests for the web control panel."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_healthz_returns_ok(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web.app import fastapi_app

    client = TestClient(fastapi_app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_projects_api_requires_auth_and_accepts_bearer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(web_app.fastapi_app)

    assert client.get("/api/projects").status_code == 401
    secret = ensure_shared_secret()
    response = client.get("/api/projects", headers={"Authorization": f"Bearer {secret}"})
    assert response.status_code == 200
    assert response.json() == []


def test_pending_previews_api_returns_unresolved_requests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    web_app._PENDING_PREVIEWS.clear()
    payload = web_app.PreviewRequest(
        project="ryos-zhcn",
        run_id="rn_web",
        batch_id="batch_web",
        system_prompt="RYOS prompt",
        items=[{"id": "I1", "source": "New Beginnings"}],
        glossary_subset=[{"source": "Starfield", "target": "星空"}],
        do_not_translate=["RYOS"],
    )
    web_app._PENDING_PREVIEWS[(payload.run_id, payload.batch_id)] = (payload, object())  # type: ignore[assignment]
    try:
        client = TestClient(web_app.fastapi_app)
        secret = ensure_shared_secret()
        response = client.get("/api/preview/pending", headers={"Authorization": f"Bearer {secret}"})
    finally:
        web_app._PENDING_PREVIEWS.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "batch_id": "batch_web",
            "run_id": "rn_web",
            "project": "ryos-zhcn",
            "system_prompt": "RYOS prompt",
            "items": [{"id": "I1", "source": "New Beginnings"}],
            "glossary_subset": [{"source": "Starfield", "target": "星空"}],
            "do_not_translate": ["RYOS"],
            "timeout_seconds": 300.0,
        }
    ]


def test_run_batches_and_events_api_read_project_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.event_queue import GuiEvent
    from bgs_translator.core.memory import insert_batch, insert_event, insert_run, open_memory_db
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_web", "plan_web", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
        insert_batch(
            conn,
            "batch_web",
            "rn_web",
            "2026-06-08T00:00:01+00:00",
            3,
            plan_id="plan_web",
            profile_snapshot_json='{"profile":"synthetic"}',
        )
        insert_event(
            conn,
            GuiEvent(kind="batch.progress", run_id="rn_web", batch_id="batch_web", payload={"done": 2, "total": 3}),
        )
    finally:
        conn.close()

    client = TestClient(fastapi_app)
    secret = ensure_shared_secret()
    headers = {"Authorization": f"Bearer {secret}"}

    batches = client.get("/api/projects/ryos-zhcn/runs/rn_web/batches", headers=headers)
    events = client.get("/api/projects/ryos-zhcn/runs/rn_web/events", headers=headers)

    assert batches.status_code == 200
    assert batches.json()[0]["batch_id"] == "batch_web"
    assert batches.json()[0]["item_count"] == 3
    assert events.status_code == 200
    assert events.json()[0]["kind"] == "batch.progress"
    assert events.json()[0]["payload"] == {"done": 2, "total": 3}


def test_run_logs_api_reads_status_failures_and_safe_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.event_queue import GuiEvent
    from bgs_translator.core.memory import insert_event, insert_run, open_memory_db
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_logs", "plan_logs", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
        insert_event(conn, GuiEvent(kind="run.complete", run_id="rn_logs", payload={"succeeded": 1}))
    finally:
        conn.close()
    run_dir = project_root / "batches" / "rn_logs"
    run_dir.mkdir(parents=True)
    (run_dir / "status.toml").write_text("status = \"complete\"\nsucceeded = 1\n", encoding="utf-8")
    (run_dir / "validator-failures.jsonl").write_text('{"row_id": 7, "reason": "empty"}\n', encoding="utf-8")
    (run_dir / "results.json").write_text('{"ok": true}\n', encoding="utf-8")

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    summary = client.get("/api/projects/ryos-zhcn/runs/rn_logs/logs", headers=headers)
    files = client.get("/api/projects/ryos-zhcn/runs/rn_logs/log-files", headers=headers)
    result_file = client.get("/api/projects/ryos-zhcn/runs/rn_logs/log-file/results.json", headers=headers)
    traversal = client.get("/api/projects/ryos-zhcn/runs/rn_logs/log-file/..%5Csettings.toml", headers=headers)

    assert summary.status_code == 200
    assert "status = \"complete\"" in summary.json()["status_toml"]
    assert "empty" in summary.json()["validator_failures"]
    assert files.status_code == 200
    assert [item["name"] for item in files.json()][:3] == [
        "status.toml",
        "validator-failures.jsonl",
        "results.json",
    ]
    assert result_file.status_code == 200
    assert result_file.json()["content"] == '{"ok": true}\n'
    assert traversal.status_code == 400


def test_entries_api_filters_and_saves_manual_edit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [
                TranslationUnit("adwryos.esm", 1, 1, "adwStart", "MESG", "FULL", source="New Beginnings"),
                TranslationUnit("adwryos.esm", 2, 2, "adwBook", "BOOK", "DESC", source="Background notes"),
            ],
        )
        row_id = str(conn.execute("SELECT row_id FROM units WHERE signature = 'MESG'").fetchone()[0])
    finally:
        conn.close()

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    entries = client.get(
        "/api/projects/ryos-zhcn/entries?sig=MESG&search=begin",
        headers=headers,
    )
    assert entries.status_code == 200
    assert len(entries.json()) == 1
    assert entries.json()[0]["row_id"] == row_id

    saved = client.post(
        f"/api/projects/ryos-zhcn/entries/{row_id}",
        headers=headers,
        json={"dest": "新的开始", "status": "translated", "reason": "web test"},
    )
    assert saved.status_code == 200
    assert saved.json()["entry"]["dest"] == "新的开始"
    assert saved.json()["entry"]["status"] == "translated"

    conn = open_memory_db(project_root)
    try:
        row = conn.execute("SELECT dest, status, profile_used FROM units WHERE row_id = ?", (row_id,)).fetchone()
    finally:
        conn.close()
    assert row == ("新的开始", "translated", "manual-edit")
    audit_files = list((project_root / "batches" / "manual-edits").glob("*.jsonl"))
    assert audit_files
    assert row_id in audit_files[0].read_text(encoding="utf-8")


def test_profiles_api_saves_activates_and_masks_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import load_profiles
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    saved = client.post(
        "/api/profiles",
        headers=headers,
        json={
            "name": "openrouter",
            "sdk_kind": "openai-compat",
            "base_url": "https://openrouter.ai/api/v1/chat/completions",
            "model": "deepseek/deepseek-chat-v3-0324",
            "api_key_env": "BGS_TRANSLATOR_KEY_OPENROUTER",
            "json_mode": "json_schema",
            "require_parameters": True,
            "cost_cap_usd": 5.0,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["profile"]["base_url"] == "https://openrouter.ai/api/v1"
    assert saved.json()["stripped_suffix"] == "/chat/completions"
    assert "sk-web-secret" not in saved.text
    assert load_profiles().profiles["openrouter"].base_url == "https://openrouter.ai/api/v1"

    key = client.post(
        "/api/profiles/openrouter/key",
        headers=headers,
        json={"api_key": "sk-web-secret"},
    )
    assert key.status_code == 200, key.text
    assert key.json() == {"ok": True, "api_key_env": "BGS_TRANSLATOR_KEY_OPENROUTER"}
    assert "sk-web-secret" in paths.profiles_env_path().read_text(encoding="utf-8")

    activated = client.post("/api/profiles/openrouter/activate", headers=headers)
    assert activated.status_code == 200
    assert activated.json()["active"] == "openrouter"

    listed = client.get("/api/profiles", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["active"] == "openrouter"
    assert body["profiles"][0]["active"] is True
    assert body["profiles"][0]["key_configured"] is True
    assert body["profiles"][0]["api_key_env"] == "BGS_TRANSLATOR_KEY_OPENROUTER"
    assert "sk-web-secret" not in listed.text


def test_theme_language_api_and_shell_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.settings import load_settings
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(web_app.fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    theme = client.post("/api/theme", headers=headers, json={"theme": "green"})
    language = client.post("/api/language", headers=headers, json={"language": "en"})
    shell_html = web_app._shell_html("logs")

    assert theme.status_code == 200
    assert theme.json() == {"theme": "green"}
    assert language.status_code == 200
    assert language.json() == {"language": "en"}
    settings = load_settings()
    assert settings.ui.theme == "green"
    assert settings.ui.language == "en"
    assert 'class="xtl-tab active" href="/logs" data-marker="tab-logs">Logs</a>' in shell_html
    assert 'data-marker="select-theme"' in shell_html
    assert 'value="green" selected' in shell_html


def test_web_i18n_loader_reads_inherited_po_catalog() -> None:
    from bgs_translator.web.i18n.loader import gettext

    assert gettext("Projects", "zh-cn") == "项目集"
    assert gettext("Projects", "en") == "Projects"
    assert gettext("Not in catalog", "zh-cn") == "Not in catalog"


def test_profiles_probe_missing_key_hard_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    save_profiles(
        ProfilesConfig(
            profiles={
                "openai-prod": ProviderProfile(
                    name="openai-prod",
                    sdk_kind="openai",
                    base_url="https://api.openai.com/v1",
                    model="gpt-5-mini",
                    api_key_env="BGS_TRANSLATOR_KEY_OPENAI",
                )
            }
        )
    )

    client = TestClient(fastapi_app)
    response = client.post(
        "/api/profiles/openai-prod/probe",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "missing_api_key"
    assert response.json()["api_key_env"] == "BGS_TRANSLATOR_KEY_OPENAI"


def test_glossary_api_scope_gating_and_player_entry_reaches_next_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    monkeypatch.setenv("BGS_KB_USER_PACKS", str(tmp_path / "user-packs"))
    from typer.testing import CliRunner

    from bgs_translator.cli.app import app
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    vanilla = client.get("/api/glossary?scope=vanilla", headers=headers)
    assert vanilla.status_code == 200
    assert vanilla.json()["writable"] is False
    assert "工具从知识库自动整理" in vanilla.json()["message"]
    assert "普通玩家不用手动添加" in vanilla.json()["message"]

    blocked = client.post(
        "/api/glossary",
        headers=headers,
        json={"scope": "mod", "source": "RYOS", "target": "RYOS"},
    )
    assert blocked.status_code == 403

    added = client.post(
        "/api/glossary",
        headers=headers,
        json={
            "scope": "player",
            "source": "Starborn",
            "target": "星生子",
            "source_aliases": ["Starborn Guardian"],
            "category": "lore_term",
            "confidence": "preferred",
            "notes": "普通玩家偏好的 Starfield 译名。",
        },
    )
    assert added.status_code == 200, added.text
    record_id = added.json()["entry"]["record_id"]

    player = client.get("/api/glossary?scope=player&search=Starborn", headers=headers)
    assert player.status_code == 200
    assert player.json()["writable"] is True
    assert [entry["source"] for entry in player.json()["entries"]] == ["Starborn"]

    global_player = client.post(
        "/api/glossary",
        headers=headers,
        json={
            "scope": "player",
            "source": "Starfield",
            "target": "星空",
            "category": "lore_term",
            "confidence": "canonical",
        },
    )
    assert global_player.status_code == 200
    global_record_id = global_player.json()["entry"]["record_id"]

    dnt = client.post(
        "/api/glossary",
        headers=headers,
        json={"scope": "do_not_translate", "source": "RYOS", "target": "", "category": "brand"},
    )
    assert dnt.status_code == 200
    assert dnt.json()["entry"]["target"] == "RYOS"
    dnt_record_id = dnt.json()["entry"]["record_id"]

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [TranslationUnit("adwryos.esm", 1, 1, "adwStarborn", "MESG", "FULL", source="Starborn")],
        )
    finally:
        conn.close()

    result = CliRunner().invoke(
        app,
        [
            "batch",
            "plan",
            "ryos-zhcn",
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
    plan_json = json.loads(Path(envelope["data"]["plan_path"]).read_text(encoding="utf-8"))
    assert "Starborn → 星生子" in plan_json["sample_system_prompt"]
    assert "Starfield → 星空" in plan_json["sample_system_prompt"]
    assert "\nRYOS\n" in plan_json["sample_system_prompt"]
    assert plan_json["batches"][0]["do_not_translate"] == ["RYOS"]
    assert {
        (entry["source"], entry["scope"])
        for entry in plan_json["batches"][0]["glossary_subset"]
    } == {
        ("RYOS", "do_not_translate"),
        ("Starborn", "player"),
        ("Starfield", "player"),
    }

    deleted = client.delete(f"/api/glossary/{record_id}", headers=headers)
    assert deleted.status_code == 200
    deleted_global = client.delete(f"/api/glossary/{global_record_id}", headers=headers)
    assert deleted_global.status_code == 200
    deleted_dnt = client.delete(f"/api/glossary/{dnt_record_id}", headers=headers)
    assert deleted_dnt.status_code == 200
