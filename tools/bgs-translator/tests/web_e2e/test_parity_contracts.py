"""Contract tests for web-GUI parity affordances."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient


def test_all_top_level_tabs_have_stable_markers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._shell_html("project")

    for marker in [
        "tab-project",
        "tab-entries",
        "tab-batches",
        "tab-prompt",
        "tab-profiles",
        "tab-glossary",
        "tab-logs",
    ]:
        assert f'data-marker="{marker}"' in html


def test_keyboard_shortcut_script_maps_ctrl_digits_and_escape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    script = web_app._settings_script()

    assert "tabPaths = ['/project', '/entries', '/batches', '/prompt', '/profiles', '/glossary', '/logs']" in script
    assert "event.key === 'Escape'" in script
    assert "xtl-glossary-editor" in script
    assert "window.location.assign(link.href)" in script
    assert "key === 'b'" in script
    assert "key === 'r'" in script


def test_logs_html_exposes_expected_markers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._logs_html(None)

    assert 'data-marker="panel-log-stream"' in html
    assert 'data-marker="panel-log-file-viewer"' in html
    assert 'data-marker="select-log-run"' in html
    assert 'id="xtl-log-viewer"' in html


def test_project_html_exposes_export_and_close_guard_markers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._project_html("ryos-zhcn")
    script = web_app._project_script("ryos-zhcn")

    for marker in [
        "panel-project-actions",
        "btn-export-project",
        "btn-open-exports",
        "status-project-export",
        "panel-close-guard",
    ]:
        assert f'data-marker="{marker}"' in html
    assert "beforeunload" in script
    assert "__xtlInternalNavigation" in script
    assert "summary.classList.contains('danger')" in script


def test_batches_script_exposes_phase11_perf_hooks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    script = web_app._batches_script("ryos-zhcn")

    assert "window.__xtlBatchMetrics" in script
    assert "wsMessages" in script
    assert "refreshes" in script
    assert "renderedEvents" in script
    assert "metrics.wsState = 'open'" in script


def test_page_routes_return_full_html_documents_with_browser_cookie(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import COOKIE_NAME

    client = TestClient(web_app.fastapi_app)
    response = client.get("/batches")

    assert response.status_code == 200
    assert response.text.startswith("<!doctype html>")
    assert '/assets/xtl-page.js?active=batches' in response.text
    assert 'http-equiv="refresh"' not in response.text
    assert "xtl-batches" in response.text
    assert COOKIE_NAME in response.cookies

    script = client.get("/assets/xtl-page.js?active=batches")
    assert script.status_code == 200
    assert script.headers["Cache-Control"] == "no-store, no-cache, max-age=0"
    assert "window.__xtlBatchMetrics" in script.text


def test_shell_status_summary_wraps_in_narrow_desktop_panes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._shell_html("batches")

    assert 'xtl-status-summary" id="xtl-status-summary"' in html
    assert 'data-marker="status-gui-alive"' in html
    assert 'class="xtl-status-separator">|' in html
    assert "本项目累计费用" not in html


def test_document_html_wraps_shell_in_scrollable_app_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app

    root = paths.project_root("ryos-zhcn")
    root.mkdir(parents=True)
    (root / "project.toml").write_text("[project]\ngame = \"Starfield\"\n", encoding="utf-8")

    html = web_app._document_html("entries", "ryos-zhcn")

    assert '<div class="xtl-app theme-' in html
    assert 'src="/assets/xtl-page.js?active=entries&amp;project=ryos-zhcn&amp;v=' in html
    assert 'href="/batches?project=ryos-zhcn"' in html


def test_project_sidebar_links_switch_selected_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app

    for name in ["ryos-zhcn", "ryos-live-render-evidence"]:
        root = paths.project_root(name)
        root.mkdir(parents=True)
        (root / "project.toml").write_text("[project]\ngame = \"Starfield\"\n", encoding="utf-8")

    html = web_app._shell_html("project", "ryos-live-render-evidence")

    assert 'href="/project?project=ryos-live-render-evidence"' in html
    assert 'row-project-ryos-live-render-evidence' in html
    assert "项目: <b>ryos-live-render-evidence</b>" in html


def test_glossary_html_exposes_phase7_markers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._glossary_html()

    for marker in [
        "tab-glossary-vanilla",
        "tab-glossary-mod",
        "tab-glossary-player",
        "tab-glossary-dnt",
        "panel-glossary-table",
        "dialog-add-glossary-entry",
        "field-glossary-source",
        "field-glossary-target",
        "panel-glossary-field-helpers",
    ]:
        assert f'data-marker="{marker}"' in html


def test_desktop_layout_css_keeps_tables_as_tables() -> None:
    css = (Path(__file__).parents[2] / "bgs_translator/web/themes/base.css").read_text(encoding="utf-8")

    assert "@media (max-width" not in css
    assert ".xtl-glossary-table tr {\n    display: block" not in css
    assert ".xtl-glossary-table td {\n    display: block" not in css
    assert "xtl-glossary-table td:not([colspan])::before" not in css
    assert "--xtl-sidebar-width: clamp" in css
    assert "grid-template-columns: var(--xtl-sidebar-width) minmax(0, 1fr)" in css
    assert "min-width: 64rem" not in css
    assert ".xtl-app {\n  height: 100vh;\n  min-width: 0;" in css
    assert ".xtl-statusbar {\n  min-height: var(--xtl-statusbar-height);" in css
    assert "flex-wrap: wrap;" in css
    assert ".xtl-statusbar > span {\n  min-width: 0;\n  max-width: 100%;" in css
    assert ".xtl-status-action {\n  display: inline-flex;" in css
    assert ".xtl-tabs {\n  display: flex;\n  align-items: stretch;\n  flex-wrap: wrap;" in css
    assert "overflow-x: auto;" not in css
    assert "\n  height: 36px;" not in css
    assert ".xtl-glossary-table {\n  table-layout: fixed;" in css
    assert ".xtl-entries-table {\n  table-layout: fixed;" in css
    assert ".xtl-entries-table th:nth-child(3),\n.xtl-entries-table td:nth-child(3) {\n  width: 14%;" in css
    assert ".xtl-entries-table th:nth-child(4),\n.xtl-entries-table td:nth-child(4) {\n  width: 55%;" in css
    assert ".xtl-batch-table {\n  table-layout: fixed;" in css
    assert ".xtl-workbench {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));" in css
    assert ".xtl-layout {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));" in css
    assert ".xtl-profiles-workbench {\n  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));" in css
    assert ".xtl-glossary-workbench {\n  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));" in css
    assert ".xtl-entries-workbench {\n  height: 100%;\n  min-height: 0;\n  overflow: hidden;\n  grid-template-columns: minmax(0, 58%) minmax(0, 42%);" in css
    assert "grid-template-columns: minmax(0, 1.2fr) minmax(16rem, .8fr);" not in css
    assert ".xtl-toolbar .xtl-select {\n  flex: 1 1 42%;\n  min-width: 0;" in css
    assert ".xtl-toolbar .xtl-priority-action {\n  flex: 0 1 auto;" in css
    assert ".xtl-progress {\n  position: relative;\n  height: 24px;\n  width: 100%;\n  min-width: 0;" in css
    assert ".xtl-entries-workbench {\n  height: 100%;" in css
    assert ".xtl-entries-workbench > .xtl-panel > .xtl-panel-body {\n  min-height: 0;\n  overflow: auto;" in css
    assert ".xtl-prompt-workbench {\n  min-height: 0;\n  overflow: auto;\n  grid-template-columns: minmax(0, 1fr) minmax(14rem, 22%);" in css
    assert ".xtl-prompt-aside {\n  align-self: start;" in css
    assert ".xtl-prompt-aside .xtl-panel-body {\n  padding: .45rem .55rem;\n  font-size: .78rem;" in css
    assert "background: #2b1900" not in css
    assert "background: #120900" not in css
    assert "rgba(255" not in css


def test_prompt_html_exposes_preview_markers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._prompt_html(None)

    for marker in [
        "field-prompt-body",
        "panel-glossary-subset",
        "panel-dnt-list",
        "select-history-batch",
        "btn-approve-batch",
        "btn-approve-all",
        "btn-discard-batch",
        "status-start-planned-run",
        "status-preview-response",
    ]:
        assert f'data-marker="{marker}"' in html
    assert 'id="xtl-approve" disabled' in html
    assert 'data-marker="prompt-scope-controls"' in html
    assert "xtl-prompt-workbench" in html
    assert "xtl-prompt-aside" in html
    assert "当前显示的是历史预览或示例提示词\uff0c不会发送给 AI；历史任务不能恢复" in html
    assert "历史任务只用于审计，不能恢复或重新启动" in html
    assert "启动这份计划并等待确认" not in html

    script = web_app._prompt_script("ryos-zhcn")
    assert "/plans/${encodeURIComponent(item.plan_id)}/run" not in script
    assert "startPlannedRun" not in script
    assert "setStartPlanStatus" in script


def test_profiles_html_has_ordinary_player_setup_guidance(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._profiles_html()

    assert "选择 AI 服务" in html
    assert "粘贴 API Key" in html
    assert "检查连接" in html
    assert "设为当前使用" in html
    assert "OpenRouter 用户通常选择" in html
    assert "API Key 的真实内容不会显示" in html
    assert 'data-marker="panel-profile-key"' in html
    assert 'data-marker="field-profile-key-value"' in html


def test_settings_api_rejects_invalid_theme_and_language(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    client = TestClient(web_app.fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}

    bad_theme = client.post("/api/theme", headers=headers, json={"theme": "purple"})
    bad_language = client.post("/api/language", headers=headers, json={"language": "jp"})

    assert bad_theme.status_code == 400
    assert bad_language.status_code == 400


def test_log_file_api_rejects_missing_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_run, open_memory_db
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_missing_log", "plan", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
    finally:
        conn.close()
    (project_root / "batches" / "rn_missing_log").mkdir(parents=True)

    client = TestClient(web_app.fastapi_app)
    response = client.get(
        "/api/projects/ryos-zhcn/runs/rn_missing_log/log-file/results.json",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 404


def test_event_reconcile_since_filters_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.event_queue import GuiEvent
    from bgs_translator.core.memory import insert_event, insert_run, open_memory_db
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_since", "plan", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
        first_id = insert_event(conn, GuiEvent(kind="run.start", run_id="rn_since", payload={}))
        insert_event(conn, GuiEvent(kind="run.complete", run_id="rn_since", payload={}))
    finally:
        conn.close()

    client = TestClient(web_app.fastapi_app)
    response = client.get(
        f"/api/projects/ryos-zhcn/runs/rn_since/events?since={first_id}",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    assert [event["kind"] for event in response.json()] == ["run.complete"]


def test_planned_batch_labels_are_player_readable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app

    plan_dir = paths.project_root("ryos-zhcn") / "batches" / "plan-readable"
    plan_dir.mkdir(parents=True)
    (paths.project_root("ryos-zhcn") / "project.toml").write_text(
        "[project]\nsource_plugin_path = \"D:/mods/adwryos.esm\"\n",
        encoding="utf-8",
    )
    (plan_dir / "plan.json").write_text(
        """
        {
          "plan_id": "51be614a-06f1-43d5-bf03-863edff61050",
          "sample_system_prompt": "RYOS prompt",
          "batches": [
            {
              "batch_id": "4acd4605-0000-4000-8000-000000000000",
              "items": [{"id": "I1"}, {"id": "I2"}]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    planned = web_app._planned_batches("ryos-zhcn")

    assert planned[0]["label"].startswith("历史第 1 批")
    assert "2 条待翻译" in planned[0]["label"]
    assert "ryos-zhcn / adwryos.esm / 历史第 1 批：2 条" in planned[0]["audit_label"]
    assert "计划 51be614a" not in planned[0]["label"]
    assert "批次 4acd4605" not in planned[0]["label"]
    assert planned[0]["item_count"] == 2


def test_start_planned_run_api_rejects_historical_restarts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True)
    (project_root / "project.toml").write_text("[project]\ngame = \"Starfield\"\n", encoding="utf-8")
    plan_dir = paths.project_root("ryos-zhcn") / "batches" / "plan-start"
    plan_dir.mkdir(parents=True)
    plan_id = "51be614a-06f1-43d5-bf03-863edff61050"
    (plan_dir / "plan.json").write_text(
        json.dumps({"plan_id": plan_id, "sample_system_prompt": "RYOS prompt", "batches": []}),
        encoding="utf-8",
    )
    client = TestClient(web_app.fastapi_app)
    response = client.post(
        f"/api/projects/ryos-zhcn/plans/{plan_id}/run",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 410
    assert "历史任务只用于审计" in response.json()["detail"]


def test_planned_batch_keeps_glossary_evidence_for_prompt_explanation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app

    plan_dir = paths.project_root("ryos-zhcn") / "batches" / "plan-evidence"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.json").write_text(
        json.dumps(
            {
                "plan_id": "plan-evidence",
                "sample_system_prompt": "RYOS prompt",
                "batches": [
                    {
                        "batch_id": "batch-1",
                        "items": [{"id": "I1"}],
                        "glossary_evidence": [
                            {
                                "source": "UC",
                                "target": "联殖",
                                "scope": "player",
                                "matched_by": "player_rule",
                                "matched_text": "UC",
                                "included": True,
                                "excluded_reason": None,
                            },
                            {
                                "source": "United Colonies",
                                "target": "联合殖民地",
                                "scope": "vanilla",
                                "matched_by": "source_exact",
                                "matched_text": "United Colonies",
                                "included": False,
                                "excluded_reason": "dedupe_source:player-uc",
                            },
                            {
                                "source": "New Atlantis Terrormorph",
                                "target": "新亚特兰蒂斯城骇变兽",
                                "scope": "vanilla",
                                "matched_by": "rag",
                                "matched_text": "new atlantis",
                                "included": False,
                                "excluded_reason": "budget_cap",
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    planned = web_app._planned_batches("ryos-zhcn")
    html = web_app._format_glossary_panel_html(planned[0]["glossary_evidence"], [])

    assert planned[0]["glossary_evidence"][0]["source"] == "UC"
    assert "已注入提示词（1）" in html
    assert "被去重或覆盖（1）" in html
    assert "因预算省略（1）" in html
    assert "因为这是你设置的固定翻译偏好" in html
    assert "提示词空间有限" in html


def test_prompt_live_preview_label_is_not_raw_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    script = web_app._prompt_script("ryos-zhcn")

    assert "当前第 ${index}/${totalBatches} 组" in script
    assert "本次任务共 ${totalItems} 条" in script
    assert "当前没有等待确认的批次" in script
    assert "这是历史预览" in script
    assert "不会发送给 AI" in script
    assert "setPreviewControls(false)" in script
    assert "setPreviewControls(true)" in script
    assert "本次任务后续批次自动发送给 AI" in script
    assert "可能继续产生费用" not in script
    assert "msg.run_id} / ${msg.batch_id" not in script
    assert "select.dataset.runId" in script
    assert "确认失败" in script
    assert "已发送确认" in script
    assert "msg.glossary_evidence" in script
    assert "已注入提示词" in script
    assert "被去重或覆盖" in script
    assert "因预算省略" in script


def test_prompt_preview_label_shows_batch_and_total_counts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    label = web_app._preview_select_label(
        web_app.PreviewRequest(
            project="du_overtime",
            run_id="rn_demo",
            batch_id="batch-1",
            system_prompt="prompt",
            items=[{"id": f"I{index}"} for index in range(20)],
            batch_index=1,
            total_batches=18,
            total_items=500,
        )
    )

    assert label == "当前第 1/18 组：本组 20 条，本次任务共 500 条，等待确认"


def test_shell_status_warns_about_running_tasks_and_uses_player_labels(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_run, open_memory_db
    from bgs_translator.web import app as web_app

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_running", "plan", datetime.now(UTC).isoformat(), 3, project="ryos-zhcn")
    finally:
        conn.close()

    html = web_app._shell_html("project")

    assert "有 1 个任务运行中" in html
    assert "已发送请求可能仍在服务商侧处理" in html
    assert 'data-marker="link-running-tasks"' in html
    assert "查看/停止运行中任务" in html
    assert "BGS 汉化助手 / bgs-translator" in html
    assert "AI 服务账号" in html
    assert "游戏本体术语" in html
    assert "我的翻译偏好" in html


def test_stale_running_rows_are_labeled_orphaned_not_active_cost_risk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_run, open_memory_db
    from bgs_translator.web import app as web_app

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_stale", "plan", "2026-06-08T00:00:00+00:00", 8, project="ryos-zhcn")
        rows = web_app._annotate_run_rows(
            "ryos-zhcn",
            conn,
            [{"run_id": "rn_stale", "status": "running", "started_at": "2026-06-08T00:00:00+00:00"}],
        )
    finally:
        conn.close()

    assert rows[0]["status"] == "orphaned"
    html = web_app._shell_html("batches", "ryos-zhcn")
    assert "历史任务未正常收尾" in html
    assert "可能继续计费" not in html
    assert 'data-marker="link-running-tasks"' not in html


def test_entries_html_uses_player_facing_filter_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._entries_html(None)
    script = web_app._entries_script("ryos-zhcn")

    assert "文本类型" in html
    assert "xtl-entries-page" in html
    assert "xtl-entries-workbench" in html
    assert "菜单/消息" in html
    assert "MESG" in html
    assert "名称文本" in html
    assert "FULL" in html
    assert "搜索原文、译文或条目编号" in html
    assert "全选当前列表" in html
    assert "全部清空" in html
    assert "批量标记已翻译" in html
    assert "批量退回未翻译" in html
    assert "每组条数" in html
    assert "field-entries-batch-size" in html
    assert 'id="xtl-entries-batch-size" type="number" min="1" step="1" value="100"' in html
    assert 'id="xtl-entries-batch-size" type="number" min="1" max="500"' not in html
    assert "btn-entries-bulk-translated" in html
    assert "btn-entries-bulk-untranslated" in html
    assert "btn-entries-submit-all-queue" in html
    assert "疯狂模式：提交当前筛选全部" in html
    assert 'data-marker="panel-entry-context"' in html
    assert "xtl-selection-status" in html
    assert "条目编号" in script
    assert "lastSelectionAnchorRowId" in script
    assert "function setSelectionRange" in script
    assert "event.shiftKey" in script
    assert "function selectAllVisibleRows" in script
    assert "function clearSelectedRows" in script
    assert "function bulkUpdateStatus" in script
    assert "function submitAllMatchingBatchQueue" in script
    assert "function entryBatchSize" in script
    assert "/batch-queue/all" in script
    assert "Math.min(500" not in script
    assert "entries.map(entry => entry.row_id)" in script
    assert "entry.status === 'untranslated'" in script
    assert "batch_size: batchSize" in script
    assert "已选择 ${selectedCount} / 当前列表 ${total} 个显示组" in script
    assert "内部 ID" not in html
    assert "内部 ID" not in script
    assert "这会让该文本保持原文" in script
    assert "标记为不需要翻译" in script
    assert "这会清空当前译文" in script
    assert "不会修改原始 MOD 文件" in script


def test_entries_html_builds_signature_filters_from_project_memory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web import app as web_app

    project_root = paths.project_root("dynamic-filters")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [
                TranslationUnit(
                    "Example.esm",
                    0x01000001,
                    0x01000001,
                    "GameplayOption",
                    "GPOF",
                    "DNAM",
                    source="Determines a gameplay option.",
                ),
                TranslationUnit(
                    "Example.esm",
                    0x01000002,
                    0x01000002,
                    "LoadScreen",
                    "LSCR",
                    "DESC",
                    source="Loading tip",
                ),
                TranslationUnit(
                    "Example.esm",
                    0x01000003,
                    0x01000003,
                    "PlacedRef",
                    "REFR",
                    "FULL",
                    source="Placed marker",
                ),
            ],
        )
    finally:
        conn.close()

    html = web_app._entries_html("dynamic-filters")

    assert 'value="GPOF"' in html
    assert "游戏设置选项 (GPOF)" in html
    assert 'value="LSCR"' in html
    assert "载入画面提示 (LSCR)" in html
    assert 'value="REFR"' in html
    assert "放置对象、地点标记或引用名称 (REFR)" in html
    assert 'value="DNAM"' in html
    assert "说明/显示文本 (DNAM)" in html
    assert "已选择 0 / 当前列表 0 个显示组" in html
    assert "按住 Shift 点击复选框" in html
    assert "提交队列只会接收未翻译条目" in html


def test_entries_bulk_status_api_updates_partial_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.sst.status import SStrParam
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text("[project]\ngame = \"Starfield\"\n", encoding="utf-8")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [
                TranslationUnit("A.esm", 1, 1, "needsReviewA", "BOOK", "DESC", source="Needs review A"),
                TranslationUnit("A.esm", 2, 2, "needsReviewB", "BOOK", "DESC", source="Needs review B"),
            ],
        )
        conn.execute("UPDATE units SET status = 'partial', sparams = ?, dest = '复查 A' WHERE edid = 'needsReviewA'", (int(SStrParam.INCOMPLETE_TRANS),))
        conn.execute("UPDATE units SET status = 'partial', sparams = ?, dest = '复查 B' WHERE edid = 'needsReviewB'", (int(SStrParam.INCOMPLETE_TRANS),))
        row_ids = [str(row[0]) for row in conn.execute("SELECT row_id FROM units ORDER BY formid").fetchall()]
        conn.commit()
    finally:
        conn.close()

    client = TestClient(web_app.fastapi_app)
    headers = {"Authorization": f"Bearer {ensure_shared_secret()}"}
    translated = client.post(
        "/api/projects/ryos-zhcn/entries/bulk-status",
        json={"row_ids": row_ids, "status": "translated"},
        headers=headers,
    )
    assert translated.status_code == 200
    assert translated.json()["updated_count"] == 2
    conn = open_memory_db(project_root)
    try:
        rows = conn.execute("SELECT status, sparams, dest FROM units ORDER BY formid").fetchall()
    finally:
        conn.close()
    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("translated", int(SStrParam.TRANSLATED), "复查 A"),
        ("translated", int(SStrParam.TRANSLATED), "复查 B"),
    ]

    untranslated = client.post(
        "/api/projects/ryos-zhcn/entries/bulk-status",
        json={"row_ids": row_ids, "status": "untranslated"},
        headers=headers,
    )
    assert untranslated.status_code == 200
    assert untranslated.json()["updated_count"] == 2
    conn = open_memory_db(project_root)
    try:
        rows = conn.execute("SELECT status, sparams, dest FROM units ORDER BY formid").fetchall()
    finally:
        conn.close()
    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("untranslated", int(SStrParam.NONE), None),
        ("untranslated", int(SStrParam.NONE), None),
    ]


def test_batches_script_translates_run_and_event_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    script = web_app._batches_script("ryos-zhcn")

    assert "最近一次任务" in script
    assert "function preferredRunId()" in script
    assert "run.status === 'running'" in script
    assert "'run.complete': '全部完成'" in script
    assert "'run.abandoned': '已中断，仅审计'" in script
    assert "'prompt.preview_request': '等待你确认提示词'" in script
    assert "'batch.request_sent': '已发送给模型'" in script
    assert "'batch.response_received': '模型已返回'" in script
    assert "'batch.abandoned': '已中断，仅审计'" in script
    assert "'batch.waiting_preview': '已中断，仅审计'" in script
    assert "title=\"${esc(event.kind)}${esc(titleBatch)}\"" in script
    assert "第 ${index + 1} 组" in script
    assert "cancelRun()" in script
    assert "discardRunTranslations()" in script
    assert "discard-translations" in script
    assert "discarded: '已抛弃'" in script
    assert "确认抛弃" in script
    assert "runSelectInteracting" in script
    assert "runOptionsSignature" in script
    assert "currentBatches" in script
    assert "applyRealtimeEvent(msg)" in script
    assert "function updateBatchFromRealtimeEvent" in script
    assert "skipped: 'run-select-open'" in script
    assert "pauseAutoRefreshForRunSelect()" in script
    assert "resumeAutoRefreshForRunSelect" in script
    assert "refreshAll({force: true})" in script
    assert "refreshAll({keepSince: true})" not in script
    assert "pollEvents" not in script
    assert "window.setInterval(refreshActiveRunIfNeeded, 5000)" in script
    assert "function scheduleRealtimeRefresh" in script
    assert "method: 'POST'" in script


def test_batches_html_exposes_cancel_and_discard_controls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._batches_html(None)

    assert 'data-marker="btn-cancel-run"' in html
    assert 'data-marker="status-cancel-run"' in html
    assert 'data-marker="btn-discard-run-translations"' in html
    assert 'data-marker="status-discard-run"' in html
    assert "AI 翻译任务" in html
    assert "请求停止会让当前选中的运行中任务在安全检查点结束" in html
    assert "抛弃这次翻译" in html
    assert "只清除当前历史任务写入项目记忆库的译文" in html


def test_batches_html_prefers_running_run_and_disables_finished_cancel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    monkeypatch.setattr(
        web_app,
        "_run_rows",
        lambda _project: [
            {"run_id": "rn_done", "status": "complete", "batches_total": 2, "cost_total_usd": 0.0013},
            {"run_id": "rn_live", "status": "running", "batches_total": 8, "cost_total_usd": 0.14},
        ],
    )

    html = web_app._batches_html("ryos-zhcn")

    assert '<option value="rn_live" title="rn_live" selected>' in html
    assert '<button class="xtl-btn danger xtl-priority-action" data-marker="btn-cancel-run" id="xtl-cancel-run" disabled>' not in html
    assert '<button class="xtl-btn danger" data-marker="btn-discard-run-translations" id="xtl-discard-run-translations" disabled>' in html

    monkeypatch.setattr(
        web_app,
        "_run_rows",
        lambda _project: [
            {"run_id": "rn_done", "status": "complete", "batches_total": 2, "cost_total_usd": 0.0013},
        ],
    )

    html = web_app._batches_html("ryos-zhcn")

    assert '<option value="rn_done" title="rn_done" selected>' in html
    assert '<button class="xtl-btn danger xtl-priority-action" data-marker="btn-cancel-run" id="xtl-cancel-run" disabled>' in html
    assert '<button class="xtl-btn danger" data-marker="btn-discard-run-translations" id="xtl-discard-run-translations" disabled>' not in html


def test_cancel_run_api_writes_cli_compatible_marker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_run, open_memory_db
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_cancel_web", "plan", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
    finally:
        conn.close()
    run_dir = project_root / "batches" / "rn_cancel_web"
    run_dir.mkdir(parents=True)

    client = TestClient(web_app.fastapi_app)
    response = client.post(
        "/api/projects/ryos-zhcn/runs/rn_cancel_web/cancel",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True
    assert (run_dir / "cancel.requested").read_text(encoding="utf-8") == "cancel requested\n"


def test_discard_run_translations_api_clears_only_selected_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import (
        insert_run,
        insert_units,
        open_memory_db,
        update_unit_translation,
    )
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [
                TranslationUnit("A.esm", 1, 1, "A", "QUST", "FULL", source="Quest A"),
                TranslationUnit("A.esm", 2, 2, "B", "QUST", "NNAM", source="Quest B"),
            ],
        )
        row_ids = [str(row[0]) for row in conn.execute("SELECT row_id FROM units ORDER BY formid").fetchall()]
        insert_run(conn, "rn_done", "plan", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
        conn.execute("UPDATE runs SET status = 'complete' WHERE run_id = 'rn_done'")
        update_unit_translation(
            conn,
            row_id=row_ids[0],
            dest="任务 A",
            status="translated",
            sparams=0,
            via_llm=True,
            profile_used="profile",
            sdk_via="synthetic",
            cost_estimate_usd=0.01,
            cost_exact=True,
            retry_count=0,
            last_batch_id="batch-a",
            last_run_id="rn_done",
        )
        update_unit_translation(
            conn,
            row_id=row_ids[1],
            dest="任务 B",
            status="translated",
            sparams=0,
            via_llm=True,
            profile_used="profile",
            sdk_via="synthetic",
            cost_estimate_usd=0.01,
            cost_exact=True,
            retry_count=0,
            last_batch_id="batch-b",
            last_run_id="rn_other",
        )
    finally:
        conn.close()

    client = TestClient(web_app.fastapi_app)
    response = client.post(
        "/api/projects/ryos-zhcn/runs/rn_done/discard-translations",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    assert response.json()["discarded_count"] == 1
    conn = open_memory_db(project_root)
    try:
        rows = conn.execute(
            "SELECT dest, status, via_llm, last_run_id FROM units ORDER BY formid"
        ).fetchall()
        run_status = conn.execute("SELECT status FROM runs WHERE run_id = 'rn_done'").fetchone()[0]
    finally:
        conn.close()
    assert rows[0] == (None, "untranslated", 0, None)
    assert rows[1] == ("任务 B", "translated", 1, "rn_other")
    assert run_status == "discarded"


def test_project_close_summary_counts_manual_edits_after_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text("[project]\ngame = 'Starfield'\n", encoding="utf-8")
    exports = project_root / "exports"
    exports.mkdir(parents=True)
    exported = exports / "old.sst"
    exported.write_text("old", encoding="utf-8")
    conn = open_memory_db(project_root)
    try:
        insert_units(conn, [TranslationUnit("adwryos.esm", 1, 1, "adwStart", "MESG", "FULL", "New Beginnings")])
        row_id = str(conn.execute("SELECT row_id FROM units").fetchone()[0])
        conn.execute(
            """
            UPDATE units
            SET dest = '新的手工译文', via_llm = 0, updated_at = '9999-01-01T00:00:00+00:00'
            WHERE row_id = ?
            """,
            (row_id,),
        )
        conn.commit()
    finally:
        conn.close()

    client = TestClient(web_app.fastapi_app)
    response = client.get(
        "/api/projects/ryos-zhcn/close-summary",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["unsaved_manual_edits"] == 1
    assert data["in_flight_count"] == 0
    assert data["files"][0]["name"] == "old.sst"


def test_project_export_api_runs_cli_and_returns_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from subprocess import CompletedProcess

    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text("[project]\ngame = 'Starfield'\n", encoding="utf-8")

    def fake_run(cmd: list[str], **kwargs: object) -> CompletedProcess[str]:
        assert cmd[:3] == [sys.executable, "-m", "bgs_translator"]
        assert cmd[-3:] == ["project", "export", "ryos-zhcn"]
        assert kwargs["timeout"] == 120
        exports = project_root / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        (exports / "adwryos_zh-cn.sst").write_text("sst", encoding="utf-8")
        return CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(web_app.subprocess, "run", fake_run)
    client = TestClient(web_app.fastapi_app)
    response = client.post(
        "/api/projects/ryos-zhcn/export",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["files"][0]["name"] == "adwryos_zh-cn.sst"
    assert data["close_summary"]["unsaved_manual_edits"] == 0


def test_open_exports_api_warns_when_no_sst_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text("[project]\ngame = 'Starfield'\n", encoding="utf-8")

    client = TestClient(web_app.fastapi_app)
    response = client.post(
        "/api/projects/ryos-zhcn/open-exports",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "没有 SST 文件" in data["message"]


def test_logs_html_uses_player_facing_event_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.event_queue import GuiEvent
    from bgs_translator.core.memory import insert_event, insert_run, open_memory_db
    from bgs_translator.web import app as web_app

    project_root = paths.project_root("ryos-zhcn")
    conn = open_memory_db(project_root)
    try:
        insert_run(conn, "rn_logs_labels", "plan", "2026-06-08T00:00:00+00:00", 1, project="ryos-zhcn")
        insert_event(conn, GuiEvent(kind="run.complete", run_id="rn_logs_labels", payload={}))
    finally:
        conn.close()

    html = web_app._logs_html("ryos-zhcn")

    assert "翻译记录摘要" in html
    assert "全部完成" in html
    assert "complete / failed / manual_review" not in html


def test_logs_script_uses_player_facing_file_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    script = web_app._logs_script("ryos-zhcn")

    assert "'status.toml': '运行状态'" in script
    assert "'validator-failures.jsonl': '需要复查的失败项'" in script
    assert "'system-prompt.md': '完整 AI 提示词'" in script


def test_profiles_advanced_settings_are_visible_not_collapsed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._profiles_html()

    assert 'data-marker="panel-profile-advanced"' in html
    assert "<details" not in html
    assert "高级设置" in html
    assert "不懂可以不改" in html
    assert "服务地址" in html
    assert "通常自动填写" in html


def test_profiles_provider_labels_are_plain_language(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._profiles_html()

    assert "OpenRouter" in html
    assert "推荐" in html
    assert "DeepSeek / 其他兼容服务" in html
    assert "结构化返回" in html
    assert "使用推荐参数" in html


def test_glossary_html_explains_terms_for_ai_in_plain_language(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    html = web_app._glossary_html()
    script = web_app._glossary_script()

    assert "这些词表会交给 AI" in html
    assert "统一译名" in html
    assert "避免把缩写乱翻" in html
    assert "glossaryIntro" in script
    assert "data.message ? `${glossaryIntro}${data.message}`" in script
    assert "activeProject" in script
    assert "params.set('project', activeProject)" in script


def test_project_html_explains_sst_and_reload_safely(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    import hashlib

    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app

    plugin = tmp_path / "mods" / "adwryos.esm"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(b"not a real plugin, enough for source identity display")
    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text(
        "\n".join(
            [
                "[project]",
                'game = "Starfield"',
                'source_lang = "en"',
                'target_lang = "zh-cn"',
                f'source_plugin_path = "{str(plugin).replace(chr(92), chr(92) * 2)}"',
                f'source_plugin_sha256 = "{hashlib.sha256(plugin.read_bytes()).hexdigest()}"',
                'parser_version = "0.9.0-rc1"',
            ]
        ),
        encoding="utf-8",
    )

    html = web_app._project_html("ryos-zhcn")

    assert "重新读取项目状态" in html
    assert "adwryos.esm" in html
    assert "源文件路径" in html
    assert "已加载条目来自" in html
    assert "不会修改原始 MOD 文件" in html
    assert "SST 是给 xTranslator 导入的翻译文件" in html
    assert "不是 MOD 本体" in html
    assert "导入新的 MOD 文件" in html
    assert "field-import-plugin-path" in html
    prompt_html = web_app._prompt_html("ryos-zhcn")
    assert 'data-marker="panel-project-translation-budgets"' not in html
    assert 'data-marker="panel-prompt-translation-budgets"' in prompt_html
    assert 'data-marker="field-budget-glossary-max-terms"' in prompt_html
    assert 'data-marker="field-budget-glossary-max-prompt-chars"' in prompt_html
    assert 'data-marker="field-budget-glossary-candidate-source-terms"' in prompt_html
    assert 'id="xtl-budget-glossary-max-terms" data-marker="field-budget-glossary-max-terms" type="number" min="1" max=' not in prompt_html
    assert 'id="xtl-budget-glossary-max-prompt-chars" data-marker="field-budget-glossary-max-prompt-chars" type="number" min="1000" max=' not in prompt_html
    assert 'id="xtl-budget-glossary-candidate-source-terms" data-marker="field-budget-glossary-candidate-source-terms" type="number" min="1" max=' not in prompt_html
    assert 'data-marker="btn-save-translation-budgets"' in prompt_html
    script = web_app._project_script("ryos-zhcn")
    assert "导出命令完成\uff0c但没有生成 SST 文件" in script
    assert "正在重新读取项目状态" in script
    assert "/reload" in script
    assert "文件指纹匹配" in script
    assert "/api/projects/import" in script
    assert "missing_strings" in script
    assert "ambiguous_game" in script


def test_project_home_shows_signature_status_statistics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.config import paths
    from bgs_translator.core.memory import insert_units, open_memory_db
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.web import app as web_app

    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text("[project]\ngame = \"Starfield\"\n", encoding="utf-8")
    conn = open_memory_db(project_root)
    try:
        insert_units(
            conn,
            [
                TranslationUnit("A.esm", 1, 1, "menuDone", "MESG", "FULL", source="Done"),
                TranslationUnit("A.esm", 2, 2, "menuTodo", "MESG", "FULL", source="Todo"),
                TranslationUnit("A.esm", 3, 3, "bookReview", "BOOK", "DESC", source="Review"),
                TranslationUnit("A.esm", 4, 4, "bookLocked", "BOOK", "DESC", source="Locked"),
            ],
        )
        conn.execute("UPDATE units SET status = 'translated', dest = '完成' WHERE edid = 'menuDone'")
        conn.execute("UPDATE units SET status = 'partial', dest = '复查' WHERE edid = 'bookReview'")
        conn.execute("UPDATE units SET status = 'locked', dest = source WHERE edid = 'bookLocked'")
        conn.commit()
    finally:
        conn.close()

    summary = web_app._project_summary("ryos-zhcn")
    stats = {row["signature"]: row for row in summary["signature_status"]}
    assert stats["MESG"]["total"] == 2
    assert stats["MESG"]["translated"] == 1
    assert stats["MESG"]["pending_ai"] == 1
    assert stats["BOOK"]["partial"] == 1
    assert stats["BOOK"]["locked"] == 1

    html = web_app._project_html("ryos-zhcn")
    assert 'data-marker="panel-project-signature-stats"' in html
    assert "Record Signature 统计" in html
    assert "菜单/消息、提示文本、开始选项" in html
    assert "<b>MESG</b>" in html
    assert "<b>BOOK</b>" in html


def test_project_reload_api_reads_source_plugin_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    import hashlib

    from bgs_translator.config import paths
    from bgs_translator.web import app as web_app
    from bgs_translator.web.security import ensure_shared_secret

    plugin = tmp_path / "mods" / "ReloadMe.esm"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(b"reload identity bytes")
    project_root = paths.project_root("ryos-zhcn")
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "project.toml").write_text(
        "\n".join(
            [
                "[project]",
                'game = "Starfield"',
                'source_lang = "en"',
                'target_lang = "zh-cn"',
                f'source_plugin_path = "{str(plugin).replace(chr(92), chr(92) * 2)}"',
                f'source_plugin_sha256 = "{hashlib.sha256(plugin.read_bytes()).hexdigest()}"',
                'parser_version = "0.9.0-rc1"',
            ]
        ),
        encoding="utf-8",
    )

    client = TestClient(web_app.fastapi_app)
    response = client.post(
        "/api/projects/ryos-zhcn/reload",
        headers={"Authorization": f"Bearer {ensure_shared_secret()}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"]["plugin_name"] == "ReloadMe.esm"
    assert data["source"]["exists"] is True
    assert data["source"]["sha_status"] == "match"
    assert "不会修改原始 MOD 文件" in data["message"]


def test_run_option_label_hides_technical_id_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    label = web_app._run_option_label(
        {"run_id": "rn_621df4022857", "status": "complete", "batches_total": 3, "cost_total_usd": 0.0029},
        1,
    )

    assert label.startswith("已完成\uff1a最近一次任务")
    assert "3 组文本" in label
    assert "$0.0029" not in label
    assert "ID rn_621df" not in label


def test_run_option_label_marks_abandoned_runs_as_audit_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    label = web_app._run_option_label(
        {"run_id": "rn_abandoned", "status": "abandoned", "batches_total": 18, "cost_total_usd": 0.0},
        1,
    )

    assert label.startswith("已中断，仅审计\uff1a最近一次任务")
    assert "18 组文本" in label


def test_run_option_label_translates_discarded_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    label = web_app._run_option_label(
        {"run_id": "rn_discarded", "status": "discarded", "batches_total": 1, "cost_total_usd": 0.0},
        1,
    )

    assert label.startswith("已抛弃\uff1a最近一次任务")
    assert "1 组文本" in label


def test_event_kind_label_translates_common_internal_names(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.web import app as web_app

    assert web_app._event_kind_label("batch.progress") == "批次进度更新"
    assert web_app._event_kind_label("batch.request_sent") == "已发送给模型"
    assert web_app._event_kind_label("batch.response_received") == "模型已返回"
    assert web_app._event_kind_label("batch.abandoned") == "已中断，仅审计"
    assert web_app._event_kind_label("batch.waiting_preview") == "已中断，仅审计"
    assert web_app._event_kind_label("run.abandoned") == "已中断，仅审计"
    assert web_app._event_kind_label("prompt.preview_request") == "等待你确认提示词"
    assert web_app._event_kind_label("unknown.internal") == "unknown.internal"
