"""Smoke tests for the web control panel."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

from fastapi.testclient import TestClient
from test_strings_io import _strings_bytes, write_ba2_gnrl


def test_healthz_returns_ok(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web.app import fastapi_app

    client = TestClient(fastapi_app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _tes4_subrecord(sig: bytes, data: bytes) -> bytes:
    return sig + struct.pack("<H", len(data)) + data


def _tes4_record(sig: bytes, data: bytes, *, flags: int = 0, formid: int = 0x01020304, fv: int = 552) -> bytes:
    return sig + struct.pack("<III I H H", len(data), flags, formid, 0, fv, 0) + data


def _tes4_header(*, flags: int = 0, fv: int = 552) -> bytes:
    return _tes4_record(b"TES4", _tes4_subrecord(b"HEDR", struct.pack("<fII", 1.0, 1, fv)), flags=flags, formid=0, fv=fv)


def _tes4_grup(*children: bytes) -> bytes:
    payload = b"".join(children)
    return b"GRUP" + struct.pack("<I4sIII", 24 + len(payload), b"WEAP", 0, 0, 0) + payload


def _minimal_tes4_plugin(*, localized: bool = False) -> bytes:
    flags = 0x80 if localized else 0
    child = _tes4_record(b"WEAP", _tes4_subrecord(b"FULL", b"Test Sword\x00"), fv=552)
    return _tes4_header(flags=flags, fv=552) + _tes4_grup(child)


def _localized_tes4_plugin_with_full_strid(strid: int) -> bytes:
    child = _tes4_record(b"WEAP", _tes4_subrecord(b"FULL", struct.pack("<I", strid)), fv=552)
    return _tes4_header(flags=0x80, fv=552) + _tes4_grup(child)


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


def test_project_import_api_creates_project_from_plugin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Demo.esm"
    plugin.write_bytes(_minimal_tes4_plugin())

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    response = client.post(
        "/api/projects/import",
        headers=headers,
        json={"project_name": "demo-import", "plugin_path": str(plugin)},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["project"] == "demo-import"
    assert data["game"] == "Starfield"
    assert data["form_version"] == 552
    assert data["plugin_type"] == "ESM"
    assert data["is_localized"] is False
    assert data["units_extracted"] == 1
    assert data["signature_distribution"] == {"WEAP": 1}
    assert (paths.project_root("demo-import") / "memory" / "memory.sqlite").is_file()


def test_entry_quick_translate_uses_active_provider_and_writes_audit(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.pipeline.clients import base as clients_base
    from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Demo.esm"
    plugin.write_bytes(_minimal_tes4_plugin())
    save_profiles(
        ProfilesConfig(
            active="OpenRouter-Test",
            profiles={
                "OpenRouter-Test": ProviderProfile(
                    name="OpenRouter-Test",
                    sdk_kind="openai-compat",
                    base_url="https://openrouter.ai/api/v1",
                    model="anthropic/claude-opus-4.6",
                    api_key_env="OPENROUTER_API_KEY",
                    json_mode="json_object",
                )
            },
        )
    )

    class FakeClient:
        def __init__(self, profile: ProviderProfile) -> None:
            self.profile = profile

        async def translate_batch(self, batch, system_prompt: str) -> LLMResponse:
            assert "Starfield" in system_prompt
            assert "Demo" in system_prompt
            assert batch.items[0].source_masked == "Test Sword"
            return LLMResponse(
                items={"I1": "测试剑"},
                usage=TokenUsage(input_tokens=12, output_tokens=3, total_tokens=15),
                cost_usd=0.001,
                cost_exact=True,
                request_id="req_test",
                via="chat_completions",
            )

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(clients_base, "build_client_for", lambda profile: FakeClient(profile))
    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    created = client.post(
        "/api/projects/import",
        headers=headers,
        json={"project_name": "demo-import", "plugin_path": str(plugin)},
    )
    assert created.status_code == 200, created.text
    conn = sqlite3.connect(paths.project_root("demo-import") / "memory" / "memory.sqlite")
    row_id = str(conn.execute("SELECT row_id FROM units LIMIT 1").fetchone()[0])
    conn.close()

    response = client.post(
        f"/api/projects/demo-import/entries/{row_id}/quick-translate",
        headers=headers,
        json={"apply": True},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["entry"]["dest"] == "测试剑"
    assert data["entry"]["status"] == "translated"
    assert data["profile"] == "OpenRouter-Test"
    assert data["cost_usd"] == 0.001
    conn = sqlite3.connect(paths.project_root("demo-import") / "memory" / "memory.sqlite")
    stored = conn.execute(
        "SELECT dest, status, via_llm, profile_used, sdk_via, last_batch_id FROM units WHERE row_id = ?",
        (row_id,),
    ).fetchone()
    conn.close()
    assert stored[:5] == ("测试剑", "translated", 1, "OpenRouter-Test", "chat_completions")
    assert str(stored[5]).startswith("quick-")
    audit_lines = list((paths.project_root("demo-import") / "batches" / "manual-edits").glob("*.jsonl"))
    assert audit_lines
    audit = json.loads(audit_lines[0].read_text(encoding="utf-8").splitlines()[0])
    assert audit["operation"] == "quick-translate"
    assert audit["after"]["dest"] == "测试剑"


def test_entry_quick_translate_falls_back_from_empty_json_schema_response(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.pipeline.clients import base as clients_base
    from bgs_translator.pipeline.clients.base import LLMResponse, TokenUsage
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Demo.esm"
    plugin.write_bytes(_minimal_tes4_plugin())
    save_profiles(
        ProfilesConfig(
            active="OpenRouter-Test",
            profiles={
                "OpenRouter-Test": ProviderProfile(
                    name="OpenRouter-Test",
                    sdk_kind="openai-compat",
                    base_url="https://openrouter.ai/api/v1",
                    model="anthropic/claude-opus-4.6",
                    api_key_env="OPENROUTER_API_KEY",
                    json_mode="json_schema",
                )
            },
        )
    )
    seen_modes: list[str | None] = []

    class FakeClient:
        def __init__(self, profile: ProviderProfile) -> None:
            self.profile = profile
            seen_modes.append(profile.json_mode)

        async def translate_batch(self, batch, system_prompt: str) -> LLMResponse:
            items = {} if self.profile.json_mode == "json_schema" else {"I1": "测试剑"}
            return LLMResponse(
                items=items,
                usage=TokenUsage(input_tokens=12, output_tokens=3, total_tokens=15),
                via="chat_completions",
            )

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(clients_base, "build_client_for", lambda profile: FakeClient(profile))
    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    created = client.post(
        "/api/projects/import",
        headers=headers,
        json={"project_name": "demo-import", "plugin_path": str(plugin)},
    )
    assert created.status_code == 200, created.text
    conn = sqlite3.connect(paths.project_root("demo-import") / "memory" / "memory.sqlite")
    row_id = str(conn.execute("SELECT row_id FROM units LIMIT 1").fetchone()[0])
    conn.close()

    response = client.post(
        f"/api/projects/demo-import/entries/{row_id}/quick-translate",
        headers=headers,
        json={"apply": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["entry"]["dest"] == "测试剑"
    assert seen_modes == ["json_schema", "json_object"]


def test_batch_queue_api_writes_cli_handoff_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Demo.esm"
    plugin.write_bytes(_minimal_tes4_plugin())
    save_profiles(
        ProfilesConfig(
            active="OpenRouter-Test",
            profiles={
                "OpenRouter-Test": ProviderProfile(
                    name="OpenRouter-Test",
                    sdk_kind="openai-compat",
                    base_url="https://openrouter.ai/api/v1",
                    model="anthropic/claude-opus-4.6",
                    api_key_env="OPENROUTER_API_KEY",
                    json_mode="json_object",
                )
            },
        )
    )
    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    created = client.post(
        "/api/projects/import",
        headers=headers,
        json={"project_name": "demo-import", "plugin_path": str(plugin)},
    )
    assert created.status_code == 200, created.text
    from bgs_translator.core.memory import insert_units
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = sqlite3.connect(paths.project_root("demo-import") / "memory" / "memory.sqlite")
    insert_units(
        conn,
        [TranslationUnit("Demo.esm", 99, 99, "AliasOnly", "QUST", "QMDP", source="<Alias=TargetLocation>")],
    )
    row_ids = [str(row[0]) for row in conn.execute("SELECT row_id FROM units ORDER BY rowid LIMIT 2").fetchall()]
    conn.close()

    response = client.post(
        "/api/projects/demo-import/batch-queue",
        headers=headers,
        json={"row_ids": row_ids, "batch_size": 1},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["queued_count"] == 1
    assert data["llm_skipped_count"] == 1
    assert data["llm_skipped_reasons"] == {"all_protected": 1}
    assert "--queue" in data["command"]
    queue_path = Path(data["queue_path"])
    assert queue_path.is_file()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert queue["row_ids"] == row_ids[:1]
    assert queue["batch_size"] == 1
    assert queue["llm_skipped_count"] == 1
    assert queue["profile"] == "OpenRouter-Test"
    assert "CLI" not in data["message"]
    assert data["command"].startswith("xtl batch plan")
    assert "--batch-size 1" in data["command"]
    assert data["batch_size"] == 1
    assert data["group_count"] == 1
    assert data["last_group_size"] == 1

    hidden = client.get("/api/projects/demo-import/entries?sig=QUST", headers=headers)
    assert hidden.status_code == 200
    assert hidden.json() == []


def test_batch_queue_api_reports_actual_group_size_when_under_cap(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Demo.esm"
    plugin.write_bytes(_minimal_tes4_plugin())
    save_profiles(
        ProfilesConfig(
            active="OpenRouter-Test",
            profiles={
                "OpenRouter-Test": ProviderProfile(
                    name="OpenRouter-Test",
                    sdk_kind="openai-compat",
                    base_url="https://openrouter.ai/api/v1",
                    model="anthropic/claude-opus-4.6",
                    api_key_env="OPENROUTER_API_KEY",
                    json_mode="json_object",
                )
            },
        )
    )
    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    created = client.post(
        "/api/projects/import",
        headers=headers,
        json={"project_name": "demo-import", "plugin_path": str(plugin)},
    )
    assert created.status_code == 200, created.text
    from bgs_translator.core.memory import insert_units
    from bgs_translator.parsers.tes4_family import TranslationUnit

    conn = sqlite3.connect(paths.project_root("demo-import") / "memory" / "memory.sqlite")
    insert_units(
        conn,
        [TranslationUnit("Demo.esm", 100, 100, "Second", "QUST", "FULL", source="Second objective")],
    )
    row_ids = [str(row[0]) for row in conn.execute("SELECT row_id FROM units ORDER BY rowid LIMIT 2").fetchall()]
    conn.close()

    response = client.post(
        "/api/projects/demo-import/batch-queue",
        headers=headers,
        json={"row_ids": row_ids, "batch_size": 500},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["queued_count"] == 2


def test_entries_api_folds_duplicates_only_within_signature_field(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("dupes")
    project_root.mkdir(parents=True)
    (project_root / "project.toml").write_text("[project]\ngame = \"Starfield\"\n", encoding="utf-8")
    conn = open_memory_db(project_root)
    insert_units(
        conn,
        [
            TranslationUnit("A.esm", 1, 1, "WeaponA", "WEAP", "FULL", source="Ship"),
            TranslationUnit("A.esm", 2, 2, "WeaponB", "WEAP", "FULL", source="Ship"),
            TranslationUnit("A.esm", 3, 3, "MessageA", "MESG", "FULL", source="Ship"),
        ],
    )
    conn.close()

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    response = client.get("/api/projects/dupes/entries?limit=20", headers=headers)

    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2
    grouped = next(row for row in rows if row["signature"] == "WEAP")
    separate = next(row for row in rows if row["signature"] == "MESG")
    assert grouped["member_count"] == 2
    assert len(grouped["member_row_ids"]) == 2
    assert grouped["cross_signature_field_count"] == 2
    assert separate["member_count"] == 1
    assert separate["cross_signature_field_count"] == 2


def test_batch_queue_dedupes_safe_duplicate_groups(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    save_profiles(
        ProfilesConfig(
            active="OpenRouter-Test",
            profiles={
                "OpenRouter-Test": ProviderProfile(
                    name="OpenRouter-Test",
                    sdk_kind="openai-compat",
                    base_url="https://openrouter.ai/api/v1",
                    model="anthropic/claude-opus-4.6",
                    api_key_env="OPENROUTER_API_KEY",
                    json_mode="json_object",
                )
            },
        )
    )
    project_root = paths.project_root("queue-dupes")
    project_root.mkdir(parents=True)
    (project_root / "project.toml").write_text(
        "[project]\ngame = \"Starfield\"\ntarget_lang = \"zh-cn\"\n",
        encoding="utf-8",
    )
    conn = open_memory_db(project_root)
    insert_units(
        conn,
        [
            TranslationUnit("A.esm", 1, 1, "WeaponA", "WEAP", "FULL", source="Ship"),
            TranslationUnit("A.esm", 2, 2, "WeaponB", "WEAP", "FULL", source="Ship"),
            TranslationUnit("A.esm", 3, 3, "MessageA", "MESG", "FULL", source="Ship"),
        ],
    )
    row_ids = [str(row[0]) for row in conn.execute("SELECT row_id FROM units ORDER BY formid").fetchall()]
    conn.close()

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    response = client.post(
        "/api/projects/queue-dupes/batch-queue",
        headers=headers,
        json={"row_ids": row_ids, "batch_size": 100},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["covered_count"] == 3
    assert data["queued_count"] == 2
    queue = json.loads(Path(data["queue_path"]).read_text(encoding="utf-8"))
    assert len(queue["row_ids"]) == 2
    assert [group["member_count"] for group in queue["source_groups"]] == [2, 1]
    assert data["batch_size"] == 100
    assert data["group_count"] == 1
    assert data["last_group_size"] == 2


def test_batch_queue_all_submits_all_matching_entries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.config.profiles import ProfilesConfig, ProviderProfile, save_profiles
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    save_profiles(
        ProfilesConfig(
            active="OpenRouter-Test",
            profiles={
                "OpenRouter-Test": ProviderProfile(
                    name="OpenRouter-Test",
                    sdk_kind="openai-compat",
                    base_url="https://openrouter.ai/api/v1",
                    model="anthropic/claude-opus-4.6",
                    api_key_env="OPENROUTER_API_KEY",
                    json_mode="json_object",
                )
            },
        )
    )
    project_root = paths.project_root("queue-all")
    project_root.mkdir(parents=True)
    (project_root / "project.toml").write_text(
        "[project]\ngame = \"Starfield\"\ntarget_lang = \"zh-cn\"\n",
        encoding="utf-8",
    )
    conn = open_memory_db(project_root)
    insert_units(
        conn,
        [
            TranslationUnit("A.esm", index, index, f"Q{index}", "QUST", "FULL", source=f"Objective {index}")
            for index in range(1, 504)
        ]
        + [TranslationUnit("A.esm", 900, 900, "SkipAlias", "QUST", "QMDP", source="<Alias=TargetLocation>")]
    )
    conn.close()

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    response = client.post(
        "/api/projects/queue-all/batch-queue/all",
        headers=headers,
        json={"sig": "QUST", "status": "untranslated", "batch_size": 100},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["all_matching"] is True
    assert data["matched_count"] == 503
    assert data["covered_count"] == 503
    assert data["queued_count"] == 503
    assert data["batch_size"] == 100
    assert data["group_count"] == 6
    assert data["last_group_size"] == 3


def test_project_import_api_rejects_duplicate_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Demo.esm"
    plugin.write_bytes(_minimal_tes4_plugin())
    existing = paths.project_root("demo-import")
    existing.mkdir(parents=True)
    (existing / "project.toml").write_text("[project]\nname='demo-import'\n", encoding="utf-8")

    client = TestClient(fastapi_app)
    response = client.post(
        "/api/projects/import",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
        json={"project_name": "demo-import", "plugin_path": str(plugin)},
    )

    assert response.status_code == 409
    assert "已存在" in response.text


def test_project_import_api_reports_localized_plugin_missing_strings(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Localized.esm"
    plugin.write_bytes(_minimal_tes4_plugin(localized=True))

    client = TestClient(fastapi_app)
    response = client.post(
        "/api/projects/import",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
        json={"project_name": "localized-import", "plugin_path": str(plugin)},
    )

    assert response.status_code == 400
    data = response.json()["detail"]
    assert data["code"] == "missing_strings"
    assert data["strings"]["missing"] == ["STRINGS", "DLSTRINGS", "ILSTRINGS"]
    assert not (tmp_path / "translator" / "projects" / "localized-import").exists()


def test_project_import_api_reads_localized_plugin_strings_from_ba2(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "Localized.esm"
    plugin.write_bytes(_localized_tes4_plugin_with_full_strid(1001))
    ba2 = tmp_path / "Localized - main.ba2"
    write_ba2_gnrl(
        ba2,
        {
            "strings/Localized_english.strings": _strings_bytes({1001: b"Archive Sword"}),
        },
    )

    client = TestClient(fastapi_app)
    response = client.post(
        "/api/projects/import",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
        json={"project_name": "localized-import", "plugin_path": str(plugin)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["strings"]["archives"] == {"STRINGS": str(ba2)}
    assert data["units_extracted"] == 1
    conn = sqlite3.connect(paths.project_root("localized-import") / "memory" / "memory.sqlite")
    try:
        row = conn.execute("SELECT source FROM units").fetchone()
    finally:
        conn.close()
    assert row == ("Archive Sword",)


def test_project_import_page_can_pick_plugin_with_windows_dialog(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "mods" / "Picked.esm"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(_minimal_tes4_plugin())
    monkeypatch.setattr(
        web_app,
        "_select_plugin_file",
        lambda current_path="": {"path": str(plugin), "canceled": False},
    )

    html = web_app._project_import_panel_html()
    assert 'data-marker="btn-import-browse-plugin"' in html
    assert "浏览文件" in html

    client = TestClient(web_app.fastapi_app)
    selected = client.post(
        "/api/projects/select-plugin-file",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
        json={"current_path": ""},
    )

    assert selected.status_code == 200, selected.text
    assert selected.json() == {"path": str(plugin), "canceled": False}


def test_entries_quick_translate_uses_in_page_confirmation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._entries_html(None) + web_app._entries_script(None)

    assert 'data-marker="dialog-entry-quick-confirm"' in html
    assert 'data-marker="btn-entry-quick-confirm"' in html
    assert "将使用当前 AI 账号快速翻译 1 条文本" in html
    assert "window.confirm('将使用当前 AI 账号快速翻译" not in html


def test_translation_budget_settings_api_persists_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config.settings import load_settings
    from bgs_translator.web.app import fastapi_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    response = client.post(
        "/api/settings/behavior/translation-budgets",
        headers=headers,
        json={
            "glossary_max_terms": 777,
            "glossary_max_prompt_chars": 123456,
            "glossary_candidate_source_terms": 500,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "glossary_max_terms": 777,
        "glossary_max_prompt_chars": 123456,
        "glossary_candidate_source_terms": 500,
    }
    settings = load_settings()
    assert settings.behavior.glossary_max_terms == 777
    assert settings.behavior.glossary_max_prompt_chars == 123456
    assert settings.behavior.glossary_candidate_source_terms == 500


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
            "glossary_evidence": [],
            "do_not_translate": ["RYOS"],
            "batch_index": None,
            "total_batches": None,
            "total_items": None,
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


def test_glossary_api_syncs_bundled_vanilla_kb_for_project(
    tmp_path: Path,
    monkeypatch,
    make_fixture_pack,
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("BGS_KB_USER_PACKS", str(tmp_path / "home" / "kb" / "user-packs"))

    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    bundled_db = make_fixture_pack(
        "bgs-l10n-starfield-zhhans",
        [
            {
                "record_id": "sf.new-atlantis",
                "source": "New Atlantis",
                "target": "新亚特兰蒂斯城",
                "scope": "vanilla",
                "games": ["Starfield"],
            }
        ],
    )
    bundled_pack = bundled_db.parent
    (bundled_pack / "manifest.json").write_text(
        json.dumps(
            {
                "games": ["Starfield"],
                "domains": ["translation", "localization", "glossary"],
                "recordCount": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app, "_bundled_kb_packs_root", lambda: bundled_pack.parent)

    project_root = paths.project_root("sf-demo")
    project_root.mkdir(parents=True)
    (project_root / "project.toml").write_text(
        """
schema_version = 1

[project]
name = "sf-demo"
game = "Starfield"
target_lang = "zh-cn"
source_plugin_path = "D:\\\\Starfield MO2\\\\mods\\\\demo\\\\demo.esm"
""".strip(),
        encoding="utf-8",
    )

    client = TestClient(web_app.fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    response = client.get(
        "/api/glossary?scope=vanilla&project=sf-demo&search=New%20Atlantis",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "已同步 Starfield 本体术语库" in data["message"]
    assert data["entries"][0]["source"] == "New Atlantis"
    assert (paths.kb_packs_root() / "bgs-l10n-starfield-zhhans" / "kb.sqlite").is_file()
