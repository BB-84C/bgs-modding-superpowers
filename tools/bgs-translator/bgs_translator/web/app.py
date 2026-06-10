"""NiceGUI server entry point for the browser control panel."""

# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tomllib
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import Depends, HTTPException, Query, Request, Response, WebSocket, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ValidationError

from bgs_translator.cli.project import _sha256, _write_cache, _write_project_toml
from bgs_translator.config import paths
from bgs_translator.config.profiles import (
    ProfileMissingKeyError,
    ProfilesConfig,
    ProfileValidationError,
    ProviderProfile,
    get_active_profile,
    load_profiles,
    normalize_base_url,
    resolve_api_key,
    save_profiles,
    write_env_var,
)
from bgs_translator.config.settings import load_settings, update_setting
from bgs_translator.core.memory import (
    discard_run_translations,
    fetch_events_for_run,
    get_unit_by_row_id,
    insert_units,
    list_recent_runs,
    open_memory_db,
    select_units_filtered,
    update_unit_translation,
)
from bgs_translator.core.runtime_pid import remove_gui_pid, write_gui_pid
from bgs_translator.kb._schema import apply_stub_schema
from bgs_translator.kb.models import GlossaryEntry
from bgs_translator.kb.reader import KBGlossaryReader
from bgs_translator.parsers.extractor import extract_translation_units
from bgs_translator.parsers.form_versions import detect_game_from_header
from bgs_translator.parsers.schemas import get_schema_for_game
from bgs_translator.parsers.strings_io import find_strings_sources
from bgs_translator.parsers.tes4_family import TES4FamilyWalker, TES4Header
from bgs_translator.sst.status import SStrParam
from bgs_translator.web.events import broadcast_ws, connect_ws
from bgs_translator.web.security import (
    ensure_shared_secret,
    issue_browser_cookie,
    remove_shared_secret,
    require_shared_secret,
)

try:
    from nicegui import app as fastapi_app
    from nicegui import ui
except ModuleNotFoundError as exc:  # pragma: no cover - import guard for CLI help paths
    raise RuntimeError(
        "NiceGUI is required for the web GUI. Install with: pip install -e .[dev]"
    ) from exc

_APP_TITLE = "bgs-translator control panel"
_PENDING_PREVIEWS: dict[tuple[str, str], tuple[PreviewRequest, asyncio.Future[dict[str, Any]]]] = {}
_APPROVE_ALL_RUNS: set[str] = set()
_INJECTED_THEME_CSS: set[str] = set()
_ACTIVE_RUN_WINDOW = timedelta(minutes=15)
_PAGE_ROUTES = {
    "/project": "project",
    "/entries": "entries",
    "/batches": "batches",
    "/prompt": "prompt",
    "/profiles": "profiles",
    "/glossary": "glossary",
    "/logs": "logs",
}


@fastapi_app.middleware("http")
async def html_page_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Serve control-panel pages as ordinary HTML so inline page scripts execute."""

    active = _PAGE_ROUTES.get(request.url.path)
    if request.method == "GET" and active is not None:
        project = _selected_project_name(request.query_params.get("project"))
        response = HTMLResponse(_document_html(active, project))
        issue_browser_cookie(response)
        return response
    return await call_next(request)


@fastapi_app.get("/assets/xtl-page.js")
def page_script_asset(active: str = Query(...), project: str | None = Query(None)) -> Response:
    """Serve page behavior as an external script for stricter browser surfaces."""

    if active not in set(_PAGE_ROUTES.values()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown page script")
    return Response(
        _document_script(active, _selected_project_name(project)),
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, max-age=0",
            "Pragma": "no-cache",
        },
    )


class PreviewRequest(BaseModel):
    """Prompt preview request sent by the CLI worker."""

    batch_id: str
    run_id: str
    project: str = ""
    system_prompt: str
    items: list[dict[str, Any]] = []
    glossary_subset: list[dict[str, Any]] = []
    glossary_evidence: list[dict[str, Any]] = []
    do_not_translate: list[str] = []
    batch_index: int | None = None
    total_batches: int | None = None
    total_items: int | None = None
    timeout_seconds: float = 300.0


class PreviewResponse(BaseModel):
    """Prompt preview response returned to the CLI worker."""

    op: str
    prompt: str = ""


class EventPush(BaseModel):
    """Best-effort event notification from the CLI worker."""

    event_id: int | None = None
    project: str
    kind: str
    run_id: str | None = None
    batch_id: str | None = None
    payload: dict[str, Any] = {}
    emitted_at: str | None = None


class EntryUpdate(BaseModel):
    """Manual edit payload for one extracted translation unit."""

    dest: str | None = None
    status: str = "translated"
    reason: str = "Web Entries tab edit"


class EntryQuickTranslateRequest(BaseModel):
    """Provider-backed quick translation request for one entry."""

    apply: bool = True


class EntryBatchQueueRequest(BaseModel):
    """Selected entry ids to hand off to CLI batch planning."""

    row_ids: list[str]
    batch_size: int | None = None


class EntryBatchQueueAllRequest(BaseModel):
    """Filter payload for submitting all matching entries to batch planning."""

    sig: str | None = None
    field: str | None = None
    status: str | None = None
    search: str | None = None
    batch_size: int | None = None


class EntryBulkStatusRequest(BaseModel):
    """Selected entry ids to mark with one XTL/xTranslator status."""

    row_ids: list[str]
    status: str
    reason: str = "Web Entries tab bulk status update"


class TranslationBudgetSave(BaseModel):
    """Advanced translation-planning budget settings."""

    glossary_max_terms: int
    glossary_max_prompt_chars: int
    glossary_candidate_source_terms: int


class ProfileSave(BaseModel):
    """Browser profile editor payload. Secret values are never accepted here."""

    name: str
    original_name: str | None = None
    sdk_kind: str
    base_url: str
    model: str
    api_key_env: str
    max_concurrency: int = 4
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    cost_cap_usd: float | None = None
    notes: str = ""
    prompt_caching: bool = False
    json_mode: str | None = None
    require_parameters: bool = False


class ProfileKeyUpdate(BaseModel):
    """Write-only API key payload for profiles/.env."""

    api_key: str


class GlossarySave(BaseModel):
    """Writable player / do-not-translate glossary entry payload."""

    record_id: str | None = None
    scope: str = "player"
    source: str
    target: str = ""
    source_lang: str = "en"
    target_lang: str = "zh-cn"
    category: str = "lore_term"
    confidence: str = "preferred"
    source_aliases: list[str] = []
    target_aliases: list[str] = []
    notes: str = ""


class ThemeSave(BaseModel):
    """Persisted web theme payload."""

    theme: str


class ProjectImportRequest(BaseModel):
    """Create a project from a local ESP/ESM/ESL plugin path."""

    project_name: str
    plugin_path: str
    game: str | None = None
    source_lang: str = "en"
    target_lang: str = "zh-cn"


class ProjectPluginFilePickRequest(BaseModel):
    """Open a native file picker for a local ESP/ESM/ESL plugin."""

    current_path: str = ""


class LanguageSave(BaseModel):
    """Persisted web language payload."""

    language: str


@fastapi_app.middleware("http")
async def _session_cookie_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith(
        ("/project", "/entries", "/batches", "/prompt", "/profiles", "/glossary", "/logs")
    ):
        issue_browser_cookie(response)
    return response


@fastapi_app.get("/healthz")
def healthz() -> dict[str, str]:
    """Return process health for launch fixtures."""

    return {"status": "ok"}


@fastapi_app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Browser event channel."""

    await connect_ws(ws)


@fastapi_app.post("/api/preview/request")
async def request_preview(
    payload: PreviewRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Block the CLI worker until the browser approves, discards, or times out."""

    if payload.run_id in _APPROVE_ALL_RUNS:
        return {"op": "approve_all", "prompt": payload.system_prompt}
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    key = (payload.run_id, payload.batch_id)
    _PENDING_PREVIEWS[key] = (payload, future)
    await broadcast_ws({"kind": "preview.opened", **payload.model_dump()})
    try:
        return await asyncio.wait_for(future, timeout=payload.timeout_seconds)
    except TimeoutError:
        _PENDING_PREVIEWS.pop(key, None)
        await broadcast_ws({"kind": "preview.timeout", "run_id": payload.run_id, "batch_id": payload.batch_id})
        return {"op": "timeout"}


@fastapi_app.post("/api/preview/respond/{run_id}/{batch_id}")
async def respond_preview(
    run_id: str,
    batch_id: str,
    payload: PreviewResponse,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, bool]:
    """Resolve one pending preview. Composite key avoids batch-id collisions."""

    key = (run_id, batch_id)
    pending = _PENDING_PREVIEWS.pop(key, None)
    if pending is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no pending preview")
    request, future = pending
    if payload.op == "approve_all":
        _APPROVE_ALL_RUNS.add(request.run_id)
    future.set_result(payload.model_dump())
    await broadcast_ws({"kind": "preview.closed", "run_id": run_id, "batch_id": batch_id, "op": payload.op})
    return {"ok": True}


@fastapi_app.get("/api/preview/pending")
def pending_previews(_auth: None = Depends(require_shared_secret)) -> list[dict[str, Any]]:
    """Return currently unresolved preview requests for missed-WS recovery."""

    return [request.model_dump() for request, _future in _PENDING_PREVIEWS.values()]


@fastapi_app.post("/api/projects/{project}/plans/{plan_id}/run")
def api_start_plan_run(
    project: str,
    plan_id: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Historical plans are audit-only; they are not restartable from the GUI."""

    del project, plan_id
    raise HTTPException(
        status.HTTP_410_GONE,
        "历史任务只用于审计，不能从这里恢复或重新启动。请从条目页重新选择文本并提交新的批量翻译队列。",
    )


@fastapi_app.post("/internal/events")
async def push_event(
    event: EventPush,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, bool]:
    """Forward best-effort CLI event notifications to browser tabs."""

    await broadcast_ws({"kind": "event", **event.model_dump()})
    return {"ok": True}


@fastapi_app.get("/api/projects")
def api_projects(_auth: None = Depends(require_shared_secret)) -> list[dict[str, Any]]:
    """List translator projects."""

    return _list_projects()


@fastapi_app.post("/api/projects/import")
def api_project_import(
    payload: ProjectImportRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Create a project from a local plugin path."""

    return _import_project_from_plugin(payload)


@fastapi_app.post("/api/projects/select-plugin-file")
def api_project_select_plugin_file(
    payload: ProjectPluginFilePickRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Open the Windows file picker and return a local plugin path."""

    return _select_plugin_file(payload.current_path)


@fastapi_app.get("/api/projects/{project}")
def api_project(project: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Return one project summary."""

    return _project_summary(project)


@fastapi_app.post("/api/projects/{project}/reload")
def api_project_reload(project: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Re-read project metadata, source-plugin status, parser cache, and sqlite-derived counts."""

    project_root = paths.project_root(project)
    if not (project_root / "project.toml").exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project not found: {project}")
    data = _project_toml_data(project_root)
    project_data = data.get("project") if isinstance(data.get("project"), dict) else {}
    plugin_path = Path(str(project_data.get("source_plugin_path") or ""))
    game = str(project_data.get("game") or "")
    inserted = 0
    parse_error = ""
    if plugin_path.is_file() and game:
        try:
            schema = get_schema_for_game(game)
            units = list(extract_translation_units(plugin_path, game, schema=schema))
            plugin_sha = _sha256(plugin_path)
            _write_cache(project_root, plugin_path, units, plugin_sha, schema)
            conn = open_memory_db(project_root)
            try:
                inserted = insert_units(conn, units)
            finally:
                conn.close()
        except KeyError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"暂不支持这个游戏：{game}") from exc
        except Exception as exc:
            parse_error = str(exc)
    summary = _project_summary(project)
    source = _project_source_details(project, verify_sha=True)
    return {
        "ok": True,
        "project": project,
        "summary": summary,
        "source": source,
        "inserted_units": inserted,
        "parse_error": parse_error,
        "message": (
            f"已重新解析源插件并补入 {inserted} 条新文本；不会修改原始 MOD 文件。"
            if not parse_error
            else f"已重新读取项目状态，但源插件暂时无法解析：{parse_error}。不会修改原始 MOD 文件。"
        ),
    }


@fastapi_app.get("/api/projects/{project}/entries")
def api_project_entries(
    project: str,
    sig: str | None = None,
    field: str | None = None,
    entry_status: str | None = Query(None, alias="status"),
    search: str | None = None,
    limit: int = 500,
    _auth: None = Depends(require_shared_secret),
) -> list[dict[str, Any]]:
    """Return filtered translation entries for the browser Entries tab."""

    bounded_limit = max(1, min(limit, 500))
    return _entry_rows(
        project,
        limit=bounded_limit,
        sig=None if _all_filter(sig) else sig,
        field=None if _all_filter(field) else field,
        entry_status=None if _all_filter(entry_status) else entry_status,
        search=search,
    )


@fastapi_app.post("/api/projects/{project}/entries/bulk-status")
def api_bulk_update_project_entries_status(
    project: str,
    payload: EntryBulkStatusRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Persist a manual status update for selected entries."""

    return _bulk_update_entries_status(project, payload.row_ids, payload.status, reason=payload.reason)


@fastapi_app.get("/api/projects/{project}/entries/{row_id}")
def api_project_entry(project: str, row_id: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Return one translation entry by row id."""

    conn = _open_project_db(project)
    try:
        entry = get_unit_by_row_id(conn, row_id)
    finally:
        conn.close()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"entry not found: {row_id}")
    return entry


@fastapi_app.post("/api/projects/{project}/entries/{row_id}")
def api_update_project_entry(
    project: str,
    row_id: str,
    payload: EntryUpdate,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Persist one manual translation edit and write the existing audit trail."""

    allowed_statuses = {"untranslated", "translated", "partial", "locked"}
    new_status = payload.status.strip().lower()
    if new_status not in allowed_statuses:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"status must be one of {sorted(allowed_statuses)}")

    from bgs_translator.cli.edit import _append_audit, _apply_edit, _get_unit

    project_root = paths.project_root(project)
    conn = open_memory_db(project_root)
    try:
        before = _get_unit(conn, row_id)
        if before is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"entry not found: {row_id}")
        conn.execute("BEGIN")
        after = _apply_edit(conn, row_id, dest=payload.dest, status=new_status)
        conn.commit()
        _append_audit(project_root, row_id=row_id, before=before, after=after, reason=payload.reason)
    except sqlite3.Error as exc:
        conn.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    finally:
        conn.close()
    return {"ok": True, "entry": after}


@fastapi_app.post("/api/projects/{project}/entries/{row_id}/quick-translate")
async def api_quick_translate_project_entry(
    project: str,
    row_id: str,
    payload: EntryQuickTranslateRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Translate one entry through the active provider and persist it."""

    del payload
    try:
        result = await _quick_translate_entry(project, row_id)
    except ProfileMissingKeyError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"当前账号缺少 API Key：{exc.api_key_env}。请先到账号页填写密钥。",
        ) from exc
    except ProfileValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"还没有可用的 AI 账号：{exc}") from exc
    return result


@fastapi_app.post("/api/projects/{project}/batch-queue")
def api_create_project_batch_queue(
    project: str,
    payload: EntryBatchQueueRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Create a GUI-selected batch queue request for later CLI planning."""

    return _create_batch_queue(project, payload.row_ids, batch_size=payload.batch_size)


@fastapi_app.post("/api/projects/{project}/batch-queue/all")
def api_create_project_batch_queue_all(
    project: str,
    payload: EntryBatchQueueAllRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Create a batch queue request for every entry matching current filters."""

    row_ids = _filtered_entry_row_ids(
        project,
        sig=None if _all_filter(payload.sig) else payload.sig,
        field=None if _all_filter(payload.field) else payload.field,
        entry_status=None if _all_filter(payload.status) else payload.status,
        search=payload.search,
    )
    if not row_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前筛选条件下没有可提交的条目。")
    result = _create_batch_queue(project, row_ids, batch_size=payload.batch_size, max_selected=None)
    result["all_matching"] = True
    result["matched_count"] = len(row_ids)
    return result


@fastapi_app.get("/api/projects/{project}/close-summary")
def api_project_close_summary(
    project: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Return close/export risk summary for browser close parity."""

    return _project_close_summary(project)


@fastapi_app.post("/api/projects/{project}/export")
def api_project_export(
    project: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Run the existing CLI SST export for one project."""

    project_root = paths.project_root(project)
    if not (project_root / "project.toml").exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project not found: {project}")
    cmd = [sys.executable, "-m", "bgs_translator", "project", "export", project]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "xtl project export failed")[-2000:]
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail)
    return {
        "ok": True,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exports_dir": str(project_root / "exports"),
        "files": _export_file_rows(project),
        "close_summary": _project_close_summary(project),
    }


@fastapi_app.post("/api/projects/{project}/open-exports")
def api_project_open_exports(
    project: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Open the local exports folder for the active project."""

    project_root = paths.project_root(project)
    if not (project_root / "project.toml").exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project not found: {project}")
    exports = project_root / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    files = _export_file_rows(project)
    if not files:
        return {
            "ok": False,
            "exports_dir": str(exports),
            "files": [],
            "message": "导出目录目前没有 SST 文件。请先点击“导出 xTranslator 文件”。",
        }
    try:
        if sys.platform == "win32":
            os.startfile(str(exports))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(exports)])
        else:
            subprocess.Popen(["xdg-open", str(exports)])
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    return {"ok": True, "exports_dir": str(exports), "files": files}


@fastapi_app.get("/api/projects/{project}/runs")
def api_project_runs(project: str, _auth: None = Depends(require_shared_secret)) -> list[dict[str, Any]]:
    """Return recent runs for one project."""

    conn = _open_project_db(project)
    try:
        return _annotate_run_rows(project, conn, [_sqlite_row_dict(row) for row in list_recent_runs(conn, limit=30)])
    finally:
        conn.close()


@fastapi_app.get("/api/projects/{project}/runs/{run_id}/batches")
def api_project_run_batches(
    project: str,
    run_id: str,
    _auth: None = Depends(require_shared_secret),
) -> list[dict[str, Any]]:
    """Return batch lifecycle rows for one run."""

    return _batch_rows(project, run_id)


@fastapi_app.get("/api/projects/{project}/runs/{run_id}/events")
def api_project_events(
    project: str,
    run_id: str,
    since: int = 0,
    _auth: None = Depends(require_shared_secret),
) -> list[dict[str, Any]]:
    """Reconcile events for one project/run from sqlite."""

    conn = _open_project_db(project)
    try:
        return fetch_events_for_run(conn, run_id, since)
    finally:
        conn.close()


@fastapi_app.post("/api/projects/{project}/runs/{run_id}/cancel")
def api_cancel_project_run(
    project: str,
    run_id: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Request cancellation for one run by writing the CLI-compatible marker."""

    run_dir = _run_dir(project, run_id)
    marker = run_dir / "cancel.requested"
    marker.write_text("cancel requested\n", encoding="utf-8")
    return {"ok": True, "run_id": run_id, "cancel_requested": True}


@fastapi_app.post("/api/projects/{project}/runs/{run_id}/discard-translations")
def api_discard_run_translations(
    project: str,
    run_id: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Discard translations written by one historical run."""

    conn = _open_project_db(project)
    try:
        run = conn.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"run not found: {run_id}")
        status_value = str(run[0] or "")
        if status_value in {"running", "queued"} or any(payload.run_id == run_id for payload in _pending_previews(project)):
            raise HTTPException(status.HTTP_409_CONFLICT, "这个任务还在运行或等待确认，请先停止任务。")
        discarded_count = discard_run_translations(conn, run_id)
    finally:
        conn.close()
    return {
        "ok": True,
        "run_id": run_id,
        "discarded_count": discarded_count,
        "message": f"已抛弃这次运行写入的 {discarded_count} 条译文。",
    }


@fastapi_app.get("/api/projects/{project}/runs/{run_id}/logs")
def api_project_run_logs(
    project: str,
    run_id: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Return the user-relevant run log summary files."""

    run_dir = _run_dir(project, run_id)
    status_text = _read_run_file(run_dir, "status.toml")
    validator_text = _read_run_file(run_dir, "validator-failures.jsonl")
    return {
        "run_id": run_id,
        "status_toml": status_text,
        "validator_failures": validator_text,
        "files": _log_file_rows(run_dir),
    }


@fastapi_app.get("/api/projects/{project}/runs/{run_id}/log-files")
def api_project_run_log_files(
    project: str,
    run_id: str,
    _auth: None = Depends(require_shared_secret),
) -> list[dict[str, Any]]:
    """List inspectable files for one run."""

    return _log_file_rows(_run_dir(project, run_id))


@fastapi_app.get("/api/projects/{project}/runs/{run_id}/log-file/{name}")
def api_project_run_log_file(
    project: str,
    run_id: str,
    name: str,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, str]:
    """Return one safe root-level run log file."""

    safe_name = _safe_log_file_name(name)
    run_dir = _run_dir(project, run_id)
    text = _read_run_file(run_dir, safe_name)
    if text is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"log file not found: {safe_name}")
    return {"name": safe_name, "content": text}


@fastapi_app.get("/api/profiles")
def api_profiles(_auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """List provider profiles without exposing API key values."""

    cfg = _load_profiles_for_api()
    return {
        "active": cfg.active,
        "profiles": [_profile_payload(profile, active=name == cfg.active) for name, profile in sorted(cfg.profiles.items())],
    }


@fastapi_app.post("/api/profiles")
def api_save_profile(payload: ProfileSave, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Add or edit a provider profile from the browser form."""

    cfg = _load_profiles_for_api()
    profile, stripped_suffix = _profile_from_payload(payload, cfg)
    original_name = (payload.original_name or payload.name).strip()
    if original_name and original_name != profile.name:
        cfg.profiles.pop(original_name, None)
        if cfg.active == original_name:
            cfg.active = profile.name
    cfg.profiles[profile.name] = profile
    save_profiles(cfg)
    return {
        "ok": True,
        "profile": _profile_payload(profile, active=profile.name == cfg.active),
        "stripped_suffix": stripped_suffix,
    }


@fastapi_app.delete("/api/profiles/{name}")
def api_delete_profile(name: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Delete a profile record without deleting its .env API key value."""

    cfg = _load_profiles_for_api()
    if name not in cfg.profiles:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"profile not found: {name}")
    cfg.profiles.pop(name, None)
    if cfg.active == name:
        cfg.active = None
    save_profiles(cfg)
    return {"ok": True, "removed": name, "active": cfg.active}


@fastapi_app.post("/api/profiles/{name}/activate")
def api_activate_profile(name: str, _auth: None = Depends(require_shared_secret)) -> dict[str, str]:
    """Set the active provider profile."""

    cfg = _load_profiles_for_api()
    if name not in cfg.profiles:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"profile not found: {name}")
    cfg.active = name
    save_profiles(cfg)
    return {"active": name}


@fastapi_app.post("/api/profiles/{name}/key")
def api_set_profile_key(
    name: str,
    payload: ProfileKeyUpdate,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Write an API key value to profiles/.env using the profile's fixed env var."""

    cfg = _load_profiles_for_api()
    profile = cfg.profiles.get(name)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"profile not found: {name}")
    try:
        write_env_var(paths.profiles_env_path(), profile.api_key_env, payload.api_key)
    except (OSError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"ok": True, "api_key_env": profile.api_key_env}


@fastapi_app.post("/api/profiles/{name}/probe")
async def api_probe_profile(name: str, _auth: None = Depends(require_shared_secret)) -> Any:
    """Probe a profile and hard-fail before provider dispatch when its key is missing."""

    cfg = _load_profiles_for_api()
    profile = cfg.profiles.get(name)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"profile not found: {name}")
    try:
        resolve_api_key(profile)
    except ProfileMissingKeyError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "missing_api_key", "message": str(exc), "api_key_env": profile.api_key_env},
        )
    try:
        from bgs_translator.cli.profile import _probe_provider

        await _probe_provider(profile)
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"code": "probe_failed", "message": str(exc), "profile": profile.name},
        )
    return {"ok": True, "profile": profile.name, "model": profile.model}


@fastapi_app.get("/api/glossary")
def api_glossary(
    scope: str = "player",
    search: str | None = None,
    project: str | None = None,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Return glossary entries for one scope."""

    normalized_scope = _normalize_glossary_scope(scope)
    project_context = _glossary_project_context(project)
    sync_notes = _sync_bundled_game_kb(project_context["game"]) if project_context["game"] else []
    entries = [
        _glossary_payload(entry)
        for entry in _glossary_entries(
            scope=normalized_scope,
            search=search,
            game=project_context["game"],
            target_lang=project_context["target_lang"],
            mod_slug=project_context["mod_slug"],
            limit=501,
        )
    ]
    limited = entries[:500]
    message = _glossary_scope_message(normalized_scope)
    if sync_notes:
        message = f"{message} {' '.join(sync_notes)}"
    if len(entries) > len(limited):
        message = f"{message} 当前列表只显示前 {len(limited)} 条，请用搜索框查具体术语。"
    return {
        "scope": normalized_scope,
        "writable": normalized_scope in _GLOSSARY_WRITABLE_SCOPES,
        "message": message,
        "project": project_context,
        "total": len(entries),
        "shown": len(limited),
        "entries": limited,
    }


@fastapi_app.post("/api/glossary")
def api_add_glossary(payload: GlossarySave, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Add a writable player / do-not-translate glossary entry."""

    entry = _save_glossary_entry(payload)
    return {"ok": True, "entry": _glossary_payload(entry)}


@fastapi_app.post("/api/glossary/{record_id}")
def api_edit_glossary(
    record_id: str,
    payload: GlossarySave,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Edit a writable glossary entry."""

    payload.record_id = record_id
    entry = _save_glossary_entry(payload)
    return {"ok": True, "entry": _glossary_payload(entry)}


@fastapi_app.delete("/api/glossary/{record_id}")
def api_delete_glossary(record_id: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Remove a writable glossary entry from the user override pack."""

    if not _delete_user_glossary_entry(record_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"writable glossary entry not found: {record_id}")
    return {"ok": True, "removed": record_id}


@fastapi_app.post("/api/settings/behavior/prompt_preview_required")
def api_preview_required(value: bool, _auth: None = Depends(require_shared_secret)) -> dict[str, bool]:
    """Persist prompt preview requirement."""

    settings = update_setting("behavior.prompt_preview_required", value)
    return {"prompt_preview_required": settings.behavior.prompt_preview_required}


@fastapi_app.post("/api/settings/behavior/translation-budgets")
def api_translation_budgets(
    payload: TranslationBudgetSave,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, int]:
    """Persist advanced translation-planning budget settings."""

    try:
        settings = update_setting("behavior.glossary_max_terms", payload.glossary_max_terms)
        settings = update_setting(
            "behavior.glossary_max_prompt_chars",
            payload.glossary_max_prompt_chars,
        )
        settings = update_setting(
            "behavior.glossary_candidate_source_terms",
            payload.glossary_candidate_source_terms,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "glossary_max_terms": settings.behavior.glossary_max_terms,
        "glossary_max_prompt_chars": settings.behavior.glossary_max_prompt_chars,
        "glossary_candidate_source_terms": settings.behavior.glossary_candidate_source_terms,
    }


@fastapi_app.post("/api/theme")
def api_theme(payload: ThemeSave, _auth: None = Depends(require_shared_secret)) -> dict[str, str]:
    """Persist theme selection."""

    try:
        settings = update_setting("ui.theme", payload.theme)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"theme": settings.ui.theme}


@fastapi_app.post("/api/language")
def api_language(payload: LanguageSave, _auth: None = Depends(require_shared_secret)) -> dict[str, str]:
    """Persist UI language selection."""

    try:
        settings = update_setting("ui.language", payload.language)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"language": settings.ui.language}


def setup_theme(theme_name: str | None = None) -> None:
    """Inject inherited TUI/Pip-Boy style CSS."""

    del theme_name
    for name in ("base.css", "amber.css", "green.css", "mono.css"):
        if name not in _INJECTED_THEME_CSS:
            ui.add_css(_theme_file(name), shared=True)
            _INJECTED_THEME_CSS.add(name)
    ui.colors(primary="#ff9900")


@ui.page("/", markdown=False)
def index() -> None:
    _render_page("project")


@ui.page("/project", markdown=False)
def page_project() -> None:
    _render_page("project")


@ui.page("/entries", markdown=False)
def page_entries() -> None:
    _render_page("entries")


@ui.page("/batches", markdown=False)
def page_batches() -> None:
    _render_page("batches")


@ui.page("/prompt", markdown=False)
def page_prompt() -> None:
    _render_page("prompt")


@ui.page("/profiles", markdown=False)
def page_profiles() -> None:
    _render_page("profiles")


@ui.page("/glossary", markdown=False)
def page_glossary() -> None:
    _render_page("glossary")


@ui.page("/logs", markdown=False)
def page_logs() -> None:
    _render_page("logs")


def launch_web(
    *,
    theme: str | None = None,
    language: str | None = None,
    port: int | None = None,
    no_open: bool = False,
    native: bool = False,
) -> None:
    """Launch the web control panel in the foreground."""

    del language
    actual_port = _pick_port(port)
    ensure_shared_secret()
    _write_port(actual_port)
    write_gui_pid()
    if theme is not None:
        update_setting("ui.theme", theme)
    try:
        ui.run(
            host="127.0.0.1",
            port=actual_port,
            reload=False,
            show=not no_open,
            native=native,
            title=_APP_TITLE,
            storage_secret=ensure_shared_secret(),
        )
    finally:
        _remove_port()
        remove_gui_pid()
        remove_shared_secret()


def _render_page(active: str) -> None:
    setup_theme()
    settings = load_settings()
    ui.html(_shell_html(active), sanitize=False).classes(f"xtl-app theme-{settings.ui.theme}")
    _run_page_script(_settings_script())
    if active == "project":
        _run_page_script(_project_script(_default_project_name()))
    if active == "entries":
        _run_page_script(_entries_script(_default_project_name()))
    if active == "prompt":
        _run_page_script(_prompt_script(_default_project_name()))
    if active == "batches":
        _run_page_script(_batches_script(_default_project_name()))
    if active == "profiles":
        _run_page_script(_profiles_script())
    if active == "glossary":
        _run_page_script(_glossary_script())
    if active == "logs":
        _run_page_script(_logs_script(_default_project_name()))


def _document_html(active: str, project: str | None = None) -> str:
    settings = load_settings()
    css = "\n".join(_theme_file(name) for name in ("base.css", "amber.css", "green.css", "mono.css"))
    escaped_active = html.escape(active, quote=True)
    query = {"active": active}
    if project:
        query["project"] = project
    query["v"] = str(Path(__file__).stat().st_mtime_ns)
    script_query = html.escape(urlencode(query), quote=True)
    return f"""<!doctype html>
<html lang="{html.escape(settings.ui.language, quote=True)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_APP_TITLE}</title>
  <style>{css}</style>
</head>
<body class="xtl-document theme-{html.escape(settings.ui.theme, quote=True)}">
<div class="xtl-app theme-{html.escape(settings.ui.theme, quote=True)}">
{_shell_html(active, project)}
</div>
<script src="/assets/xtl-page.js?{script_query}" data-active="{escaped_active}"></script>
</body>
</html>
"""


def _document_script(active: str, project: str | None = None) -> str:
    project = _selected_project_name(project)
    scripts = [_script_body(_settings_script())]
    if active == "project":
        scripts.append(_script_body(_project_script(project)))
    if active == "entries":
        scripts.append(_script_body(_entries_script(project)))
    if active == "prompt":
        scripts.append(_script_body(_prompt_script(project)))
    if active == "batches":
        scripts.append(_script_body(_batches_script(project)))
    if active == "profiles":
        scripts.append(_script_body(_profiles_script()))
    if active == "glossary":
        scripts.append(_script_body(_glossary_script()))
    if active == "logs":
        scripts.append(_script_body(_logs_script(project)))
    return "\n;\n".join(scripts)


def _run_page_script(script_html: str) -> None:
    """Execute a page script even when NiceGUI-inserted script tags are inert."""

    ui.html(_script_bootstrap_html(_script_body(script_html)), sanitize=False)


def _script_body(script_html: str) -> str:
    script = script_html.strip()
    if script.startswith("<script>"):
        script = script.removeprefix("<script>").removesuffix("</script>")
    return script.strip()


def _script_bootstrap_html(script: str) -> str:
    script_id = f"xtl-route-script-{abs(hash(script))}"
    escaped_script = html.escape(script, quote=False)
    escaped_id = html.escape(script_id, quote=True)
    return f"""
    <div class="xtl-script-bootstrap" hidden>
      <template id="{escaped_id}">{escaped_script}</template>
      <svg width="0" height="0" aria-hidden="true"
        onload="(function(id, el){{var s=document.getElementById(id);if(s&&!s.dataset.ran){{s.dataset.ran='1';(0,eval)(s.textContent);}}if(el)el.remove();}})('{escaped_id}', this)">
      </svg>
    </div>
    """


def _shell_html(active: str, project: str | None = None) -> str:
    settings = load_settings()
    labels = _ui_labels(settings.ui.language)
    project = _selected_project_name(project)
    profile = _active_profile_label()
    status_text, status_tone = _top_status(project)
    status_kind = "orphaned" if "历史任务未正常收尾" in status_text else status_tone
    theme_options = "".join(
        f'<option value="{name}" {"selected" if settings.ui.theme == name else ""}>{label}</option>'
        for name, label in [("amber", "琥珀 Amber"), ("green", "废土绿 Green"), ("mono", "黑白 Mono")]
    )
    status_action = (
        f'<a class="xtl-status-action danger" data-marker="link-running-tasks" href="{_page_href("batches", project)}">'
        "查看/停止运行中任务</a>"
        if status_tone == "danger"
        else ""
    )
    if status_kind == "orphaned" and project:
        status_action = (
            f'<button class="xtl-status-action" data-marker="btn-ack-orphaned-status" '
            f'id="xtl-ack-orphaned-status" data-project="{_esc(project)}">我已知晓</button>'
        )
    language_options = "".join(
        f'<option value="{code}" {"selected" if settings.ui.language == code else ""}>{label}</option>'
        for code, label in [("zh-cn", "简体中文"), ("en", "English")]
    )
    return f"""
    <div class="xtl-titlebar">
      <div>▌ BGS 汉化助手 / bgs-translator</div>
      <div class="xtl-window-buttons"><span>─</span><span>□</span><span>×</span></div>
    </div>
    <div class="xtl-statusbar">
      <span>项目: <b>{_esc(project or "未选择")}</b></span>
      <span class="xtl-status-separator">|</span>
      <span>AI: <b>{_esc(profile)}</b></span>
      <span class="xtl-status-separator">|</span>
      <label class="xtl-status-control"><span>{labels["language"]}:</span><select class="xtl-status-select" data-marker="select-language" id="xtl-language-select">{language_options}</select></label>
      <span class="xtl-status-separator">|</span>
      <label class="xtl-status-control"><span>{labels["theme"]}:</span><select class="xtl-status-select" data-marker="select-theme" id="xtl-theme-select">{theme_options}</select></label>
      <span class="xtl-status-separator">|</span>
      <span class="xtl-status-{status_tone} xtl-status-summary" id="xtl-status-summary" data-status-kind="{_esc(status_kind)}" data-project="{_esc(project or '')}">状态: <b data-marker="status-gui-alive">{_esc(status_text)}</b>{status_action}</span>
    </div>
    <div class="xtl-shell">
      {_sidebar_html(active, project)}
      <main class="xtl-main">
        {_tabs_html(active, project)}
        <section class="xtl-content" data-marker="page-{active}">
          {_content_html(active, project)}
        </section>
      </main>
    </div>
    """


def _sidebar_html(active: str, project: str | None) -> str:
    projects = _list_projects()
    project_links = "\n".join(
        f'<a class="xtl-tree-link {"active" if item["name"] == project and active == "project" else ""}" '
        f'href="{_page_href("project", str(item["name"]))}" data-marker="row-project-{_esc(item["name"])}">{_esc(item["name"])}</a>'
        for item in projects[:20]
    )
    if not project_links:
        project_links = '<div class="xtl-tree-link">尚无项目</div>'
    return f"""
    <aside class="xtl-sidebar">
      <div class="xtl-tree">
        <div class="xtl-tree-group">
          <div class="xtl-tree-heading">翻译项目</div>
          {project_links}
        </div>
        <div class="xtl-tree-group">
          <div class="xtl-tree-heading">AI 设置</div>
          <a class="xtl-tree-link {"active" if active == "profiles" else ""}" href="{_page_href("profiles", project)}">AI 服务账号</a>
        </div>
        <div class="xtl-tree-group">
          <div class="xtl-tree-heading">专有名词</div>
          <a class="xtl-tree-link" href="{_page_href("glossary", project)}">游戏本体术语</a>
          <a class="xtl-tree-link" href="{_page_href("glossary", project)}">当前 MOD 术语</a>
          <a class="xtl-tree-link" href="{_page_href("glossary", project)}">我的翻译偏好</a>
          <a class="xtl-tree-link" href="{_page_href("glossary", project)}">不要翻译的词</a>
        </div>
        <div class="xtl-tree-group">
          <div class="xtl-tree-heading">翻译记录</div>
          <a class="xtl-tree-link {"active" if active == "logs" else ""}" href="{_page_href("logs", project)}">最近记录</a>
        </div>
      </div>
    </aside>
    """


def _tabs_html(active: str, project: str | None) -> str:
    labels = _ui_labels(load_settings().ui.language)
    tabs = [
        ("project", labels["project"]),
        ("entries", labels["entries"]),
        ("batches", labels["batches"]),
        ("prompt", labels["prompt"]),
        ("profiles", labels["profiles"]),
        ("glossary", labels["glossary"]),
        ("logs", labels["logs"]),
    ]
    return '<nav class="xtl-tabs">' + "".join(
        f'<a class="xtl-tab {"active" if key == active else ""}" href="{_page_href(key, project)}" data-marker="tab-{key}">{label}</a>'
        for key, label in tabs
    ) + "</nav>"


def _ui_labels(language: str) -> dict[str, str]:
    zh = {
        "project": "项目",
        "entries": "条目",
        "batches": "进度",
        "prompt": "提示词",
        "profiles": "AI 设置",
        "glossary": "专有名词",
        "logs": "记录",
        "language": "语言",
        "theme": "主题",
    }
    en = {
        "project": "Project",
        "entries": "Entries",
        "batches": "Batches",
        "prompt": "Prompt",
        "profiles": "AI Settings",
        "glossary": "Glossary",
        "logs": "Logs",
        "language": "Language",
        "theme": "Theme",
    }
    return en if language == "en" else zh


def _content_html(active: str, project: str | None) -> str:
    if active == "project":
        return _project_html(project)
    if active == "entries":
        return _entries_html(project)
    if active == "batches":
        return _batches_html(project)
    if active == "prompt":
        return _prompt_html(project)
    if active == "profiles":
        return _profiles_html()
    if active == "glossary":
        return _glossary_html()
    if active == "logs":
        return _logs_html(project)
    return ""


def _project_html(project: str | None) -> str:
    if project is None:
        return f"""
        <div class="xtl-workbench">
          {_project_import_panel_html()}
          <div class="xtl-empty">还没有项目。可以在左侧导入 ESP/ESM/ESL 来创建翻译项目。</div>
        </div>
        """
    settings = load_settings()
    summary = _project_summary(project)
    source = summary["source"]
    plugins = source["memory_plugins"] or []
    memory_plugins = "，".join(f'{item["name"]}（{item["count"]} 条）' for item in plugins) or "尚未读取到插件条目"
    source_status = "源文件存在" if source["exists"] else "源文件不存在"
    if source["sha_status"] == "match":
        source_status += "，指纹匹配"
    elif source["sha_status"] == "mismatch":
        source_status += "，指纹与建项时不同"
    signature_stats = _project_signature_stats_html(summary["signature_status"])
    return f"""
    <div class="xtl-workbench">
      <div class="xtl-panel" data-marker="panel-project-detail">
        <div class="xtl-panel-title">当前项目</div>
        <div class="xtl-panel-body">
          <div class="xtl-metric-grid">
            <div class="xtl-metric"><div class="xtl-metric-label">项目</div><div class="xtl-metric-value">{_esc(project)}</div></div>
            <div class="xtl-metric"><div class="xtl-metric-label">游戏</div><div class="xtl-metric-value">{_esc(summary["game"])}</div></div>
            <div class="xtl-metric"><div class="xtl-metric-label">文本</div><div class="xtl-metric-value">{summary["units_total"]}</div></div>
            <div class="xtl-metric"><div class="xtl-metric-label">已译</div><div class="xtl-metric-value">{summary["units_translated"]}</div></div>
            <div class="xtl-metric"><div class="xtl-metric-label">需 AI</div><div class="xtl-metric-value">{summary["units_pending_ai"]}</div></div>
          </div>
          <table class="xtl-table">
            <tr><th>项目名</th><td>{_esc(project)}</td></tr>
            <tr><th>游戏</th><td>{_esc(summary["game"])}</td></tr>
            <tr><th>源插件</th><td>{_esc(source["plugin_name"] or "未记录源插件")}</td></tr>
            <tr><th>插件类型</th><td>{_esc(source["plugin_type"] or "未知")}</td></tr>
            <tr><th>源文件路径</th><td class="xtl-path-cell">{_esc(source["path"] or "project.toml 没有记录 source_plugin_path")}</td></tr>
            <tr><th>源文件状态</th><td>{_esc(source_status)}</td></tr>
            <tr><th>已加载条目来自</th><td>{_esc(memory_plugins)}</td></tr>
            <tr><th>文本总数</th><td>{summary["units_total"]}</td></tr>
            <tr><th>已翻译</th><td>{summary["units_translated"]}</td></tr>
            <tr><th>需 AI 翻译</th><td>{summary["units_pending_ai"]}</td></tr>
            <tr><th>语言方向</th><td>{_esc(source["source_lang"])} → {_esc(source["target_lang"])}</td></tr>
            <tr><th>解析版本</th><td>{_esc(source["parser_version"] or "未知")}</td></tr>
          </table>
          <p class="xtl-help">普通玩家主要看“源插件”和“已加载条目来自”：这里应该是你想汉化的 ESP/ESM/ESL 文件。技术条目会在“条目”页按可读文本展示。</p>
        </div>
      </div>
      <div class="xtl-panel" data-marker="panel-project-signature-stats">
        <div class="xtl-panel-title">Record Signature 统计</div>
        <div class="xtl-panel-body">
          <div class="xtl-help">这里按文本来源类型统计翻译进度。普通玩家不用理解内部缩写，只需要看哪类文本还剩多少“待翻译”或“需复查”。</div>
          {signature_stats}
        </div>
      </div>
      <div class="xtl-stack">
        {_project_import_panel_html()}
        <div class="xtl-panel">
          <div class="xtl-panel-title">工作流</div>
          <div class="xtl-panel-body">
            <p>1. 到“提示词”检查 AI 会收到的说明。</p>
            <p>2. 到“批次”观察翻译进度、模型请求状态和返回情况。</p>
            <p>3. 完成后导出给 xTranslator 使用的翻译文件，再完成最终打包。</p>
            <div class="xtl-toolbar" data-marker="panel-project-actions">
              <button class="xtl-btn" data-marker="btn-reload-project" id="xtl-project-reload">重新读取项目状态</button>
              <a class="xtl-btn danger" data-marker="btn-project-stop-runs" href="{_page_href("batches", project)}">查看并停止运行中的任务</a>
              <button class="xtl-btn primary" data-marker="btn-export-project" id="xtl-project-export">导出 xTranslator 文件</button>
              <button class="xtl-btn" data-marker="btn-open-exports" id="xtl-project-open-exports">打开导出目录</button>
            </div>
            <div class="xtl-help" data-marker="status-project-export" id="xtl-project-export-status">导出会生成给 xTranslator 导入的 SST 文件，不会修改原始 MOD 文件。</div>
            <p class="xtl-help">重新读取会检查 project.toml、源插件是否还在、文件指纹是否改变，以及本项目记忆库统计；不会重新导入新 ESP/ESM/ESL，也不会修改原始 MOD 文件。SST 是给 xTranslator 导入的翻译文件，不是 MOD 本体。</p>
          </div>
        </div>
        <div class="xtl-panel" data-marker="panel-close-guard">
          <div class="xtl-panel-title">关闭前检查</div>
          <div class="xtl-panel-body">
            <div class="xtl-help" id="xtl-close-summary">正在检查是否有运行中的批次或未导出的手工修改...</div>
            <p class="xtl-help">检测到可能仍在运行的 AI 翻译任务时，关闭页面不一定能停止已发出的请求。请先到“进度”页点“请求停止”。</p>
          </div>
        </div>
        <div class="xtl-panel">
          <div class="xtl-panel-title">新手说明</div>
          <div class="xtl-panel-body xtl-help">
            你不需要理解 ESM/ESP/ESL 的内部结构。这里把插件里的可翻译文本抽成“条目”，再分批送给 AI，最后输出 xTranslator 能读取的翻译文件。
          </div>
        </div>
      </div>
    </div>
    """


def _project_import_panel_html() -> str:
    return """
    <div class="xtl-panel" data-marker="panel-project-import">
      <div class="xtl-panel-title">导入新的 MOD 文件</div>
      <div class="xtl-panel-body">
        <div class="xtl-form-grid compact">
          <label><span>项目名</span><input class="xtl-input" id="xtl-import-project-name" data-marker="field-import-project-name" placeholder="例如 my-starfield-mod-zhcn"></label>
          <label class="wide"><span>ESP/ESM/ESL 文件</span><span class="xtl-path-picker"><input class="xtl-input" id="xtl-import-plugin-path" data-marker="field-import-plugin-path" placeholder="点击“浏览文件”选择 .esm/.esp/.esl"><button type="button" class="xtl-btn" id="xtl-import-browse-plugin" data-marker="btn-import-browse-plugin">浏览文件</button></span></label>
          <label><span>游戏</span><select class="xtl-select" id="xtl-import-game" data-marker="field-import-game"><option value="">自动检测</option><option value="Starfield">Starfield</option><option value="Fallout4">Fallout 4</option><option value="Fallout76">Fallout 76</option><option value="SkyrimSE">Skyrim SE/AE</option><option value="SkyrimLE">Skyrim LE</option><option value="FalloutNV">Fallout New Vegas</option><option value="Fallout3">Fallout 3</option></select></label>
          <label><span>目标语言</span><input class="xtl-input" id="xtl-import-target-lang" value="zh-cn"></label>
        </div>
        <div class="xtl-toolbar" style="margin-top: 10px">
          <button class="xtl-btn primary" id="xtl-import-project" data-marker="btn-import-project">导入并创建项目</button>
          <span class="xtl-help" id="xtl-import-status" data-marker="status-import-project">导入只会读取插件并创建翻译项目，不会修改原始 MOD 文件。</span>
        </div>
        <p class="xtl-help">如果插件使用 Strings 本地化文件，请保持 ESP/ESM/ESL 和旁边的 Strings 文件夹在同一个 MOD 目录中。</p>
      </div>
    </div>
    """


def _project_signature_stats_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="xtl-empty">这个项目还没有可统计的条目。</div>'
    lines = []
    for row in rows:
        signature = str(row.get("signature") or "未知")
        lines.append(
            "<tr>"
            f"<td><b>{_esc(signature)}</b><div class=\"xtl-help\">{_esc(_signature_label(signature))}</div></td>"
            f"<td>{int(row.get('total') or 0)}</td>"
            f"<td>{int(row.get('translated') or 0)}</td>"
            f"<td>{int(row.get('pending_ai') or 0)}</td>"
            f"<td>{int(row.get('partial') or 0)}</td>"
            f"<td>{int(row.get('locked') or 0)}</td>"
            "</tr>"
        )
    return (
        '<table class="xtl-table xtl-signature-stat-table">'
        "<thead><tr><th>类型</th><th>总数</th><th>已翻译</th><th>待翻译</th><th>需复查</th><th>锁定/不翻译</th></tr></thead>"
        f"<tbody>{''.join(lines)}</tbody></table>"
    )


def _project_script(project: str | None) -> str:
    project_json = _json_for_script(project or "")
    script = r"""
    <script>
    (() => {
      const project = __PROJECT__;
      const byId = id => document.getElementById(id);
      async function api(path, options = {}) {
        const res = await fetch(path, {credentials: 'same-origin', ...options});
        const text = await res.text();
        const data = text ? JSON.parse(text) : null;
        if (!res.ok) {
          const err = new Error((data && (typeof data.detail === 'string' ? data.detail : data.message)) || `${path} -> ${res.status}`);
          err.data = data;
          err.status = res.status;
          throw err;
        }
        return data;
      }
      function setStatus(text, tone = '') {
        const el = byId('xtl-project-export-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function setImportStatus(text, tone = '') {
        const el = byId('xtl-import-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function projectNameFromPath(value) {
        const fileName = String(value || '').split(/[\\/]/).pop() || '';
        const stem = fileName.replace(/\.(esp|esm|esl)$/i, '');
        return stem.toLowerCase().replace(/[^a-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 56);
      }
      function setPluginPath(value) {
        const input = byId('xtl-import-plugin-path');
        if (input) input.value = value || '';
        const name = byId('xtl-import-project-name');
        if (name && !name.value.trim()) name.value = projectNameFromPath(value);
      }
      function importErrorText(err) {
        const detail = err && err.data ? err.data.detail : null;
        if (detail && detail.code === 'ambiguous_game') {
          const choices = Array.isArray(detail.candidates) && detail.candidates.length ? `可选：${detail.candidates.join('、')}` : '请手动选择游戏';
          return `${detail.message} 文件头版本：${detail.form_version}。${choices}。`;
        }
        if (detail && detail.code === 'missing_strings') {
          const missing = detail.strings && Array.isArray(detail.strings.missing) ? detail.strings.missing.join('、') : 'Strings 文件';
          return `${detail.message} 缺少：${missing}。通常需要保留 MOD 文件夹里的 Strings 子文件夹，不要只单独复制 .esm/.esp 文件。`;
        }
        if (typeof detail === 'string') return detail;
        return err && err.message ? err.message : '导入失败。';
      }
      async function importProject() {
        const name = (byId('xtl-import-project-name')?.value || '').trim();
        const pluginPath = (byId('xtl-import-plugin-path')?.value || '').trim();
        const game = (byId('xtl-import-game')?.value || '').trim();
        const targetLang = (byId('xtl-import-target-lang')?.value || 'zh-cn').trim() || 'zh-cn';
        if (!name || !pluginPath) {
          setImportStatus('请填写项目名和 ESP/ESM/ESL 文件路径。', 'danger');
          return;
        }
        setImportStatus('正在读取 MOD 文件并创建项目...');
        try {
          const result = await api('/api/projects/import', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({project_name: name, plugin_path: pluginPath, game: game || null, target_lang: targetLang}),
          });
          const localized = result.is_localized ? '使用 Strings 本地化文件' : '文本直接在插件中';
          const esl = result.is_esl ? 'ESL/light 插件' : `${result.plugin_type || '插件'}`;
          setImportStatus(`导入完成：${result.game}，${esl}，${localized}，抽取 ${result.units_extracted} 条文本。正在打开新项目...`, 'good');
          window.location.href = `/project?project=${encodeURIComponent(result.project)}`;
        } catch (err) {
          setImportStatus(importErrorText(err), 'danger');
          console.warn('project import failed', err);
        }
      }
      async function browsePluginFile() {
        setImportStatus('正在打开 Windows 文件选择器...');
        try {
          const result = await api('/api/projects/select-plugin-file', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({current_path: byId('xtl-import-plugin-path')?.value || ''}),
          });
          if (!result || result.canceled || !result.path) {
            setImportStatus('已取消选择，没有导入文件。');
            return;
          }
          setPluginPath(result.path);
          setImportStatus('已选择 MOD 文件。确认项目名后点击“导入并创建项目”。', 'good');
        } catch (err) {
          setImportStatus(`无法打开文件选择器：${err.message || err}`, 'danger');
        }
      }
      function showReloadResultIfNeeded() {
        const url = new URL(window.location.href);
        if (!url.searchParams.has('reload')) return;
        setStatus('项目页面已重新读取。', 'good');
        url.searchParams.delete('reload');
        window.history.replaceState({}, '', url.toString());
      }
      function renderCloseSummary(summary) {
        const el = byId('xtl-close-summary');
        if (!el) return;
        if (!summary) {
          el.textContent = '无法读取关闭前检查。';
          el.className = 'xtl-help danger';
          window.__xtlCloseRisk = false;
          return;
        }
        const running = Number(summary.in_flight_count || 0);
        const unsaved = Number(summary.unsaved_manual_edits || 0);
        window.__xtlCloseRisk = running > 0 || unsaved > 0;
        const pieces = [];
        pieces.push(running ? `${running} 个翻译任务可能仍在运行` : '没有检测到运行中的翻译任务');
        if (Number(summary.orphaned_run_count || 0)) pieces.push(`${summary.orphaned_run_count} 个历史任务未正常收尾`);
        pieces.push(unsaved ? `${unsaved} 条手工修改还没有重新导出` : '没有检测到未导出的手工修改');
        if (summary.latest_export) pieces.push(`最近导出：${summary.latest_export}`);
        el.textContent = pieces.join('；');
        el.className = window.__xtlCloseRisk ? 'xtl-help danger' : 'xtl-help good';
      }
      async function refreshCloseSummary() {
        if (!project) return;
        try {
          renderCloseSummary(await api(`/api/projects/${encodeURIComponent(project)}/close-summary`));
        } catch (err) {
          renderCloseSummary(null);
          console.warn('close summary failed', err);
        }
      }
      function renderReloadResult(result) {
        const source = result && result.source ? result.source : {};
        const pieces = [result && result.message ? result.message : '已重新读取项目状态。'];
        if (source.plugin_name) pieces.push(`源插件：${source.plugin_name}`);
        if (source.plugin_type) pieces.push(`类型：${source.plugin_type}`);
        if (source.exists === false) pieces.push('源文件不存在');
        if (source.sha_status === 'match') pieces.push('文件指纹匹配');
        if (source.sha_status === 'mismatch') pieces.push('文件指纹和建项时不同，请确认是否换过 MOD 文件');
        setStatus(pieces.join('；'), source.exists === false || source.sha_status === 'mismatch' ? 'danger' : 'good');
      }
      async function exportProject() {
        if (!project) return;
        if (!window.confirm('会生成给 xTranslator 导入的翻译文件。这个操作不会修改原始 MOD 文件，确定导出吗？')) return;
        setStatus('正在导出，请稍等...');
        try {
          const result = await api(`/api/projects/${encodeURIComponent(project)}/export`, {method: 'POST'});
          const count = Array.isArray(result.files) ? result.files.length : 0;
          setStatus(
            count ? `导出完成：${count} 个文件已写入导出目录。` : '导出命令完成，但没有生成 SST 文件。请确认项目里已有译文，或查看记录页的技术日志。',
            count ? 'good' : 'danger'
          );
          renderCloseSummary(result.close_summary);
        } catch (err) {
          setStatus(`导出失败：${err.message}`, 'danger');
        }
      }
      async function openExports() {
        if (!project) return;
        setStatus('正在打开导出目录...');
        try {
          const result = await api(`/api/projects/${encodeURIComponent(project)}/open-exports`, {method: 'POST'});
          if (result && result.ok === false) {
            setStatus(result.message || '导出目录目前没有 SST 文件。请先点击“导出 xTranslator 文件”。', 'danger');
            return;
          }
          setStatus(`已打开导出目录：${result.exports_dir}`, 'good');
        } catch (err) {
          setStatus(`打开目录失败：${err.message}`, 'danger');
        }
      }
      function hasCloseRisk() {
        const summary = byId('xtl-close-summary');
        return Boolean(window.__xtlCloseRisk || (summary && summary.classList.contains('danger')));
      }
      async function reloadProject() {
        if (!project) return;
        setStatus('正在重新读取项目状态...');
        try {
          const result = await api(`/api/projects/${encodeURIComponent(project)}/reload`, {method: 'POST'});
          renderReloadResult(result);
        } catch (err) {
          setStatus(`重新读取失败：${err.message}`, 'danger');
        }
      }
      function setBudgetStatus(text, tone = '') {
        const el = byId('xtl-budget-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function budgetNumber(id, fallback) {
        const input = byId(id);
        const value = Number(input?.value || fallback);
        const min = Number(input?.min || Number.NEGATIVE_INFINITY);
        const max = Number(input?.max || Number.POSITIVE_INFINITY);
        const rounded = Number.isFinite(value) ? Math.round(value) : fallback;
        return Math.min(max, Math.max(min, rounded));
      }
      async function saveTranslationBudgets() {
        const payload = {
          glossary_max_terms: budgetNumber('xtl-budget-glossary-max-terms', 500),
          glossary_max_prompt_chars: budgetNumber('xtl-budget-glossary-max-prompt-chars', 80000),
          glossary_candidate_source_terms: budgetNumber('xtl-budget-glossary-candidate-source-terms', 32),
        };
        setBudgetStatus('正在保存高级预算...');
        try {
          const saved = await api('/api/settings/behavior/translation-budgets', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
          });
          if (byId('xtl-budget-glossary-max-terms')) byId('xtl-budget-glossary-max-terms').value = saved.glossary_max_terms;
          if (byId('xtl-budget-glossary-max-prompt-chars')) byId('xtl-budget-glossary-max-prompt-chars').value = saved.glossary_max_prompt_chars;
          if (byId('xtl-budget-glossary-candidate-source-terms')) byId('xtl-budget-glossary-candidate-source-terms').value = saved.glossary_candidate_source_terms;
          setBudgetStatus('已保存。下一次生成提示词会使用这些预算；当前运行中的任务不会被改写。', 'good');
        } catch (err) {
          setBudgetStatus(`保存失败：${err.message || err}`, 'danger');
        }
      }
      document.addEventListener('click', event => {
        if (event.target && event.target.id === 'xtl-project-export') exportProject();
        if (event.target && event.target.id === 'xtl-project-open-exports') openExports();
        if (event.target && event.target.id === 'xtl-project-reload') reloadProject();
        if (event.target && event.target.id === 'xtl-budget-save') saveTranslationBudgets();
        if (event.target && event.target.id === 'xtl-import-project') importProject();
        if (event.target && event.target.id === 'xtl-import-browse-plugin') browsePluginFile();
      });
      document.addEventListener('input', event => {
        if (event.target && event.target.id === 'xtl-import-plugin-path') {
          setPluginPath(event.target.value);
        }
      });
      if (!window.__xtlCloseGuardBound) {
        window.__xtlCloseGuardBound = true;
        window.addEventListener('beforeunload', event => {
          if (!hasCloseRisk() || window.__xtlInternalNavigation) return;
          event.preventDefault();
          event.returnValue = '还有运行中的任务或未导出的修改。';
        });
      }
      refreshCloseSummary();
      showReloadResultIfNeeded();
      window.setInterval(refreshCloseSummary, 10000);
    })();
    </script>
    """
    return script.replace("__PROJECT__", project_json)


def _entries_html(project: str | None) -> str:
    rows = _entry_rows(project, limit=60)
    selected = rows[0] if rows else None
    source = _esc(str(selected["source"])) if selected else ""
    dest = _esc(str(selected["dest"] or "")) if selected else ""
    status_value = _esc(str(selected["status"])) if selected else "untranslated"
    return f"""
    <div class="xtl-page-grid xtl-entries-page">
    <div class="xtl-toolbar" data-marker="panel-entries-filter">
      <span class="xtl-label">文本类型</span><select class="xtl-select" data-marker="select-entries-sig" id="xtl-entries-sig"><option value="">全部</option><option value="MESG">菜单/消息（MESG）</option><option value="INFO">对话/信息（INFO）</option><option value="QUST">任务（QUST）</option><option value="BOOK">书籍/说明（BOOK）</option><option value="CELL">地点/区域（CELL）</option></select>
      <span class="xtl-label">文本字段</span><select class="xtl-select" data-marker="select-entries-field" id="xtl-entries-field"><option value="">全部</option><option value="FULL">名称文本（FULL）</option><option value="DESC">说明文本（DESC）</option></select>
      <span class="xtl-label">状态</span><select class="xtl-select" data-marker="select-entries-status" id="xtl-entries-status"><option value="">全部</option><option value="untranslated">未翻译</option><option value="translated">已翻译</option><option value="partial">需复查</option><option value="locked">锁定</option></select>
      <input class="xtl-input" data-marker="field-entries-search" id="xtl-entries-search" placeholder="搜索原文、译文或条目编号">
      <button class="xtl-btn" data-marker="btn-entries-select-all" id="xtl-entries-select-all">全选当前列表</button>
      <button class="xtl-btn" data-marker="btn-entries-clear-selection" id="xtl-entries-clear-selection">全部清空</button>
      <button class="xtl-btn" data-marker="btn-entries-bulk-translated" id="xtl-entries-bulk-translated">批量标记已翻译</button>
      <button class="xtl-btn danger" data-marker="btn-entries-bulk-untranslated" id="xtl-entries-bulk-untranslated">批量退回未翻译</button>
      <span class="xtl-label">每组条数</span><input class="xtl-input xtl-number-input" data-marker="field-entries-batch-size" id="xtl-entries-batch-size" type="number" min="1" max="500" step="1" value="100">
      <button class="xtl-btn" data-marker="btn-entries-submit-queue" id="xtl-entries-submit-queue">提交到批量翻译队列</button>
      <button class="xtl-btn danger" data-marker="btn-entries-submit-all-queue" id="xtl-entries-submit-all-queue">疯狂模式：提交当前筛选全部</button>
    </div>
    <div class="xtl-help xtl-selection-status" data-marker="status-entries-queue" id="xtl-entries-queue-status">已选择 0 / 当前列表 0 个显示组，覆盖 0 条记录。按住 Shift 点击复选框可以连续选择一段；提交队列只会接收未翻译条目。</div>
    <details class="xtl-help xtl-tech-details" id="xtl-entries-queue-tech" hidden><summary>技术详情</summary><code id="xtl-entries-queue-command"></code></details>
    <div class="xtl-workbench xtl-entries-workbench">
      <div class="xtl-panel" data-marker="panel-entries-table">
        <div class="xtl-panel-title">条目列表</div>
        <div class="xtl-panel-body">
          <table class="xtl-table xtl-entries-table" id="xtl-entries-table"><thead><tr><th>选择</th><th>状态</th><th>上下文</th><th>原文</th><th>译文</th></tr></thead><tbody><tr><td colspan="5">正在读取条目...</td></tr></tbody></table>
        </div>
      </div>
      <div class="xtl-panel" data-marker="panel-entry-detail">
        <div class="xtl-panel-title">源文 / 译文 <span class="xtl-detail-id" id="xtl-entry-id">{_esc(str(selected["row_id"])) if selected else "未选择"}</span></div>
        <div class="xtl-panel-body xtl-entry-split">
          <div>
            <div class="xtl-entry-context" data-marker="panel-entry-context" id="xtl-entry-context">选择左侧条目后，这里会显示 EDID、Record Signature、字段、FormID 和重复条目数量。</div>
            <div class="xtl-help">源文：只读，供核对。保存只会写入本项目记忆库，不会修改原始 MOD 文件。</div>
            <textarea class="xtl-entry-text" data-marker="field-entry-source" id="xtl-entry-source" readonly>{source}</textarea>
          </div>
          <div>
            <div class="xtl-help">译文：可以手动修正 AI 结果。普通玩家只需要改这里。</div>
            <textarea class="xtl-entry-text" data-marker="field-entry-dest" id="xtl-entry-dest">{dest}</textarea>
            <div class="xtl-help">快速翻译会真实调用当前 AI 账号；结果只写入本项目记忆库，不会修改原始 MOD。复杂术语建议走批量翻译并先预览提示词。</div>
            <div class="xtl-toolbar" style="margin-top: 10px">
              <span class="xtl-label">保存状态</span>
              <select class="xtl-select" id="xtl-entry-status">
                <option value="translated" {"selected" if status_value == "translated" else ""}>已翻译</option>
                <option value="partial" {"selected" if status_value == "partial" else ""}>需复查</option>
                <option value="locked" {"selected" if status_value == "locked" else ""}>锁定</option>
                <option value="untranslated" {"selected" if status_value == "untranslated" else ""}>未翻译</option>
              </select>
              <button class="xtl-btn primary" data-marker="btn-entry-save" id="xtl-entry-save">保存修正</button>
              <button class="xtl-btn" data-marker="btn-entry-quick-translate" id="xtl-entry-quick-translate">快速翻译当前条目</button>
              <button class="xtl-btn" data-marker="btn-entry-restore" id="xtl-entry-restore">恢复当前译文</button>
              <button class="xtl-btn" data-marker="btn-entry-lock" id="xtl-entry-lock">标记不翻译</button>
              <button class="xtl-btn danger" data-marker="btn-entry-orphan" id="xtl-entry-clear">清空译文</button>
            </div>
            <div class="xtl-help" data-marker="status-entry-save" id="xtl-entry-save-status">选择左侧条目后可以保存。</div>
            <div class="xtl-inline-confirm" id="xtl-entry-quick-confirm" data-marker="dialog-entry-quick-confirm" hidden>
              <div>将使用当前 AI 账号快速翻译 1 条文本。结果只写入本项目记忆库，不会修改原始 MOD。</div>
              <div class="xtl-toolbar compact">
                <button class="xtl-btn primary" data-marker="btn-entry-quick-confirm" id="xtl-entry-quick-confirm-ok">确认并调用 AI</button>
                <button class="xtl-btn" data-marker="btn-entry-quick-cancel" id="xtl-entry-quick-confirm-cancel">取消</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div>
    """


def _batches_html(project: str | None) -> str:
    rows = _run_rows(project)
    selected_run = _preferred_run_id(rows)
    selected_status = next((str(row.get("status") or "") for row in rows if str(row.get("run_id") or "") == selected_run), "")
    cancel_disabled = "disabled" if selected_status != "running" else ""
    discard_disabled = "disabled" if selected_status in {"", "running", "queued"} else ""
    options = "".join(
        f'<option value="{_esc(str(row["run_id"]))}" title="{_esc(str(row["run_id"]))}" {"selected" if str(row["run_id"]) == selected_run else ""}>'
        f'{_esc(_run_option_label(row, index))}</option>'
        for index, row in enumerate(rows, start=1)
    )
    if not options:
        options = '<option value="">尚无运行</option>'
    return f"""
    <div class="xtl-toolbar">
      <span class="xtl-label">AI 翻译任务</span>
      <button class="xtl-btn danger xtl-priority-action" data-marker="btn-cancel-run" id="xtl-cancel-run" {cancel_disabled}>请求停止</button>
      <select class="xtl-select" data-marker="select-run" id="xtl-run-select">{options}</select>
      <button class="xtl-btn" data-marker="btn-refresh-batches" id="xtl-refresh-batches">刷新</button>
      <button class="xtl-btn danger" data-marker="btn-discard-run-translations" id="xtl-discard-run-translations" {discard_disabled}>抛弃这次翻译</button>
      <span class="xtl-help">这里显示 AI 汉化任务的实时进度和模型请求状态；刷新不会修改 MOD 文件。请求停止会让当前选中的运行中任务在安全检查点结束，已经发给 AI 的请求可能仍在服务商侧处理。“抛弃这次翻译”只清除当前历史任务写入项目记忆库的译文，不会修改原始 MOD 文件。</span>
      <span class="xtl-help" data-marker="status-cancel-run" id="xtl-cancel-status"></span>
      <span class="xtl-help" data-marker="status-discard-run" id="xtl-discard-status"></span>
    </div>
    <div class="xtl-workbench">
      <div class="xtl-stack">
        <div class="xtl-metric-grid" data-marker="panel-run-summary">
          <div class="xtl-metric"><div class="xtl-metric-label">运行状态</div><div class="xtl-metric-value" id="xtl-run-status">等待</div></div>
          <div class="xtl-metric"><div class="xtl-metric-label">文本组数</div><div class="xtl-metric-value" id="xtl-run-batches">0</div></div>
          <div class="xtl-metric"><div class="xtl-metric-label">已完成</div><div class="xtl-metric-value" id="xtl-run-complete">0</div></div>
          <div class="xtl-metric"><div class="xtl-metric-label">账单</div><div class="xtl-metric-value" id="xtl-run-billing">看服务商后台</div></div>
        </div>
        <div class="xtl-panel" data-marker="panel-batches-table">
          <div class="xtl-panel-title">文本组进度</div>
          <div class="xtl-panel-body">
            <table class="xtl-table xtl-batch-table" id="xtl-batches">
              <thead><tr><th>文本组</th><th>状态</th><th>文本</th><th>进度</th></tr></thead>
              <tbody><tr><td colspan="4">正在读取批次...</td></tr></tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="xtl-panel">
        <div class="xtl-panel-title">实时记录</div>
        <div class="xtl-panel-body">
          <div class="xtl-help">普通玩家只需要看“完成/失败/需要人工复查”。下面的记录是给排查问题用的。</div>
          <div class="xtl-event-list" data-marker="panel-batch-events" id="xtl-batch-events">暂无事件。</div>
        </div>
      </div>
    </div>
    """


def _prompt_html(project: str | None) -> str:
    settings = load_settings()
    planned = _planned_batches(project)
    pending = _pending_previews(project)
    current_preview = pending[-1] if pending else None
    sample = current_preview.system_prompt if current_preview else (planned[0]["prompt"] if planned else _sample_prompt(project))
    first_label = _preview_select_label(current_preview) if current_preview else "当前没有等待确认的批次"
    select_disabled = "" if current_preview else "disabled"
    action_disabled = "" if current_preview else "disabled"
    preview_status = (
        "等待你确认。"
        if current_preview
        else "当前显示的是历史预览或示例提示词，不会发送给 AI；历史任务不能恢复。"
    )
    if planned:
        history_options = "".join(
            f'<option value="{index}" {"selected" if index == 0 else ""}>{_esc(str(item.get("audit_label") or item["label"]))}</option>'
            for index, item in enumerate(planned)
        )
    else:
        history_options = "<option>暂无历史预览</option>"
    options = f"<option>{_esc(first_label)}</option>"
    first_glossary = _format_glossary_panel_html(
        current_preview.glossary_evidence,
        current_preview.glossary_subset,
    ) if current_preview else (
        _format_glossary_panel_html(
            planned[0].get("glossary_evidence", []),
            planned[0]["glossary_subset"],
        ) if planned else "<div class=\"xtl-empty\">预览后，这里会显示本次用到的专有名词。</div>"
    )
    first_dnt = _format_dnt_panel(current_preview.do_not_translate) if current_preview else (
        _format_dnt_panel(planned[0]["do_not_translate"]) if planned else "这里会列出人名、地名、缩写等不应翻译的词。"
    )
    lines = "\n".join(str(i) for i in range(1, max(22, sample.count("\n") + 4)))
    checked = "checked" if settings.behavior.prompt_preview_required else ""
    return f"""
    <div class="xtl-page-grid xtl-prompt-page">
    <div class="xtl-toolbar">
      <span class="xtl-label">当前待确认内容</span>
      <select class="xtl-select" data-marker="select-batch" id="xtl-batch-select" {select_disabled}>{options}</select>
      <label class="xtl-checkline"><input type="checkbox" id="xtl-preview-required" data-marker="check-preview-required" {checked}>每次提交给模型前都先让我预览</label>
      <span class="xtl-checkline" data-marker="prompt-scope-controls">适用范围 <label><input type="radio" checked {action_disabled}>只用于这次</label><label><input type="radio" {action_disabled}>用于同类文本</label><label><input type="radio" {action_disabled}>用于整个项目</label></span>
    </div>
    <div class="xtl-workbench xtl-prompt-workbench">
      <div>
        <div class="xtl-editor">
          <div class="xtl-editor-lines">{lines}</div>
          <textarea class="xtl-prompt" data-marker="field-prompt-body" id="xtl-prompt-body">{_esc(sample)}</textarea>
        </div>
        <div class="xtl-toolbar" style="margin-top: 10px">
          <button class="xtl-btn primary" data-marker="btn-approve-batch" id="xtl-approve" {action_disabled}>确认并翻译当前文本组</button>
          <button class="xtl-btn" data-marker="btn-approve-all" id="xtl-approve-all" {action_disabled}>本次任务后续都自动确认</button>
          <button class="xtl-btn danger" data-marker="btn-discard-batch" id="xtl-discard" {action_disabled}>跳过这一段</button>
          <span class="xtl-help">只有上方显示“等待确认”时，按钮才会把内容发送给 AI。新手推荐只确认当前文本组；自动确认会继续发送后续文本组。</span>
          <span class="xtl-help" data-marker="status-preview-response" id="xtl-preview-status">{_esc(preview_status)}</span>
          <span class="xtl-help" data-marker="status-start-planned-run" id="xtl-start-plan-status">历史任务只用于审计，不能恢复或重新启动；要翻译这些文本，请回到条目页重新选择并提交新的批量队列。</span>
        </div>
        <details class="xtl-advanced xtl-history-preview">
          <summary>查看历史预览（不会发送给 AI）</summary>
          <div class="xtl-form-grid compact">
            <label class="wide"><span>历史批次</span><select class="xtl-select" data-marker="select-history-batch" id="xtl-history-batch-select">{history_options}</select></label>
          </div>
          <p class="xtl-help">这里用于审计过去计划过哪些文本和当时的提示词。历史任务不能恢复，也不会从这里发送给 AI。</p>
        </details>
        <div class="xtl-bottom-split">
          <div class="xtl-panel" data-marker="panel-glossary-subset"><div class="xtl-panel-title">本次用到的专有名词</div><div class="xtl-panel-body" id="xtl-glossary">{first_glossary}</div></div>
          <div class="xtl-panel" data-marker="panel-dnt-list"><div class="xtl-panel-title">不要翻译的词</div><div class="xtl-panel-body" id="xtl-dnt">{_esc(first_dnt)}</div></div>
        </div>
      </div>
      <div class="xtl-stack xtl-prompt-aside-stack">
        <div class="xtl-panel xtl-prompt-aside">
          <div class="xtl-panel-title">为什么要先预览？</div>
          <div class="xtl-panel-body xtl-help">
            <p>这一步不会修改原始 MOD 文件。</p>
            <p>AI 翻译前会先让你看到它收到的说明和文本。你可以检查里面有没有奇怪内容、错误术语或不该翻译的名字，再决定是否继续。</p>
            <p>不确定时，只确认当前内容，不要选择“用于整个项目”。</p>
          </div>
        </div>
        {_translation_budget_panel_html(settings)}
      </div>
    </div>
    </div>
    """


def _translation_budget_panel_html(settings: Any) -> str:
    candidate_source_terms = min(500, max(1, int(settings.behavior.glossary_candidate_source_terms)))
    return f"""
      <div class="xtl-panel" data-marker="panel-prompt-translation-budgets">
        <div class="xtl-panel-title">高级预算设置</div>
        <div class="xtl-panel-body">
          <div class="xtl-section-label">高级设置（不懂可以不改）：提示词术语数量、术语字符预算、候选召回范围</div>
          <div class="xtl-form-grid compact">
            <label><span>术语最多条数</span><input class="xtl-input" id="xtl-budget-glossary-max-terms" data-marker="field-budget-glossary-max-terms" type="number" min="1" max="2000" step="1" value="{settings.behavior.glossary_max_terms}"></label>
            <label><span>术语文本字符预算</span><input class="xtl-input" id="xtl-budget-glossary-max-prompt-chars" data-marker="field-budget-glossary-max-prompt-chars" type="number" min="1000" max="500000" step="1000" value="{settings.behavior.glossary_max_prompt_chars}"></label>
            <label><span>候选召回关键词数</span><input class="xtl-input" id="xtl-budget-glossary-candidate-source-terms" data-marker="field-budget-glossary-candidate-source-terms" type="number" min="1" max="500" step="1" value="{candidate_source_terms}"></label>
          </div>
          <div class="xtl-toolbar" style="margin-top: 10px">
            <button class="xtl-btn primary" data-marker="btn-save-translation-budgets" id="xtl-budget-save">保存高级预算</button>
            <span class="xtl-help" data-marker="status-translation-budgets" id="xtl-budget-status">这些设置会影响下一次生成提示词；不会改写已经在运行或已经完成的批次。</span>
          </div>
          <p class="xtl-help">调高这些值会让 AI 收到更多术语，也会增加输入 token 和等待时间；真实费用请以你使用的 AI 服务商后台为准，本工具不再估算费用。</p>
        </div>
      </div>
    """


def _format_glossary_panel_html(
    evidence: list[dict[str, Any]],
    fallback_items: list[dict[str, Any]],
) -> str:
    if not evidence:
        lines = [
            f"{_esc(item.get('source') or item.get('term') or '')} -&gt; {_esc(item.get('target') or '')}"
            for item in fallback_items
            if item.get("source") or item.get("term")
        ]
        return "<br>".join(lines) or '<div class="xtl-empty">本次没有命中的专有名词。</div>'

    included = [item for item in evidence if item.get("included")]
    deduped = [
        item
        for item in evidence
        if not item.get("included") and str(item.get("excluded_reason") or "").startswith("dedupe")
    ]
    omitted = [
        item
        for item in evidence
        if not item.get("included") and not str(item.get("excluded_reason") or "").startswith("dedupe")
    ]
    return "\n".join(
        [
            _evidence_section_html("已注入提示词", included, open_section=True),
            _evidence_section_html("被去重或覆盖", deduped),
            _evidence_section_html("因预算省略", omitted),
        ]
    )


def _evidence_section_html(title: str, items: list[dict[str, Any]], *, open_section: bool = False) -> str:
    open_attr = " open" if open_section else ""
    if not items:
        body = '<div class="xtl-empty">没有项目。</div>'
    else:
        rows = [
            (
                "<li>"
                f"<b>{_esc(item.get('source') or item.get('term') or '')}</b>"
                f" -&gt; {_esc(item.get('target') or '')}"
                f"<div class=\"xtl-help\">{_esc(_evidence_reason(item))}</div>"
                "</li>"
            )
            for item in items[:80]
        ]
        if len(items) > 80:
            rows.append(f'<li class="xtl-help">还有 {len(items) - 80} 条没有展开显示。</li>')
        body = f"<ul class=\"xtl-evidence-list\">{''.join(rows)}</ul>"
    return f"<details class=\"xtl-evidence-section\"{open_attr}><summary>{_esc(title)}（{len(items)}）</summary>{body}</details>"


def _evidence_reason(item: dict[str, Any]) -> str:
    matched_by = str(item.get("matched_by") or "")
    matched_text = str(item.get("matched_text") or item.get("source") or item.get("term") or "")
    scope = str(item.get("scope") or "")
    excluded = str(item.get("excluded_reason") or "")
    if excluded == "budget_cap":
        return "命中了，但本批提示词空间有限，所以暂时没有注入。"
    if excluded.startswith("dedupe"):
        return "命中了，但和更高优先级或重复的术语合并了。"
    if matched_by == "player_rule":
        return "因为这是你设置的固定翻译偏好。"
    if matched_by == "dnt_rule":
        return "因为这是你设置的固定不翻译词。"
    if matched_by == "alias_exact":
        return f"因为本批文本出现了别名：{matched_text}。"
    if matched_by == "normalized":
        return f"因为本批文本出现了同一术语的大小写、空格或标点变体：{matched_text}。"
    if matched_by == "rag":
        return "因为本体/MOD 术语库判断它和本批文本相关。"
    if scope == "do_not_translate":
        return f"因为本批文本出现了需要保留原文的词：{matched_text}。"
    return f"因为本批文本出现了：{matched_text}。"


def _format_dnt_panel(items: list[str]) -> str:
    return "\n".join(items) or "本次没有额外的“不要翻译”词。"


def _profiles_html() -> str:
    profile = _active_profile_label()
    return f"""
    <div class="xtl-toolbar">
      <span class="xtl-label">当前 AI 服务账号</span>
      <span class="xtl-status-pill complete" data-marker="status-active-profile" id="xtl-profile-active-label">{_esc(profile)}</span>
      <button class="xtl-btn primary" data-marker="btn-profile-new" id="xtl-profile-new">新增账号</button>
      <button class="xtl-btn" data-marker="btn-profile-refresh" id="xtl-profile-refresh">刷新</button>
      <span class="xtl-help">普通玩家只需要选好一个能付款/能调用模型的账号，再确认连接成功。</span>
      <span class="xtl-help">OpenRouter 用户通常选择“OpenRouter（推荐）/ DeepSeek / 其他兼容服务”，填模型名称，保存 Key 后点“检查连接”。</span>
    </div>
    <div class="xtl-profile-steps" data-marker="panel-profile-steps">
      <div><b>1</b><span>选择 AI 服务</span></div>
      <div><b>2</b><span>粘贴 API Key</span></div>
      <div><b>3</b><span>检查连接</span></div>
      <div><b>4</b><span>设为当前使用</span></div>
    </div>
    <div class="xtl-workbench xtl-profiles-workbench">
      <div class="xtl-panel" data-marker="nav-profiles-list">
        <div class="xtl-panel-title">AI 服务账号列表</div>
        <div class="xtl-panel-body">
          <table class="xtl-table xtl-profiles-table" id="xtl-profiles-table">
            <thead><tr><th>名称</th><th>模型</th><th>Key</th><th>状态</th></tr></thead>
            <tbody><tr><td colspan="4">正在读取账号...</td></tr></tbody>
          </table>
          <p class="xtl-help">这里的“账号”就是 OpenRouter、OpenAI、DeepSeek 等 AI 服务配置。API Key 的真实内容不会显示在页面上。</p>
        </div>
      </div>
      <div class="xtl-stack">
        <div class="xtl-panel" data-marker="panel-profile-editor">
          <div class="xtl-panel-title">账号设置 <span class="xtl-detail-id" id="xtl-profile-editor-title">未选择</span></div>
          <div class="xtl-panel-body">
            <div class="xtl-form-grid">
              <label><span>名称</span><input class="xtl-input" id="xtl-profile-name" data-marker="field-profile-name" placeholder="例如 openrouter"></label>
              <label><span>AI 服务类型</span><select class="xtl-select" id="xtl-profile-sdk" data-marker="select-profile-sdk"><option value="openai-compat">OpenRouter（推荐）/ DeepSeek / 其他兼容服务</option><option value="openai">OpenAI 官方账号</option><option value="anthropic">Claude 官方账号</option><option value="gemini">Gemini 官方账号</option></select></label>
              <label class="wide"><span>模型</span><input class="xtl-input" id="xtl-profile-model" data-marker="field-profile-model" placeholder="deepseek/deepseek-chat-v3-0324"></label>
            </div>
            <div class="xtl-advanced" data-marker="panel-profile-advanced">
              <div class="xtl-section-label">高级设置（不懂可以不改）：服务地址、同时处理数量、AI 返回格式</div>
              <div class="xtl-form-grid">
                <label class="wide"><span>服务地址（通常自动填写）</span><input class="xtl-input" id="xtl-profile-base-url" data-marker="field-profile-base-url" placeholder="https://openrouter.ai/api/v1"></label>
                <input type="hidden" id="xtl-profile-env" data-marker="field-profile-env" value="BGS_TRANSLATOR_KEY_OPENROUTER">
                <label><span>同时处理数量（不懂保持 4）</span><input class="xtl-input" id="xtl-profile-concurrency" data-marker="field-profile-concurrency" type="number" min="1" value="4"></label>
                <label><span>每分钟请求上限</span><input class="xtl-input" id="xtl-profile-rpm" data-marker="field-profile-rpm" type="number" min="1" placeholder="留空即可"></label>
                <label><span>AI 返回格式</span><select class="xtl-select" id="xtl-profile-json-mode" data-marker="select-profile-json-mode"><option value="json_schema">结构化返回（推荐）</option><option value="json_object">普通结构化返回</option><option value="">不强制</option></select></label>
                <label><span>模型参数</span><select class="xtl-select" id="xtl-profile-require-parameters" data-marker="select-profile-require-parameters"><option value="true">使用推荐参数</option><option value="false">不额外要求</option></select></label>
                <label class="wide"><span>备注</span><textarea class="xtl-input xtl-profile-notes" id="xtl-profile-notes" data-marker="field-profile-notes" placeholder="给自己看的说明，比如充值账号、推荐用途。"></textarea></label>
              </div>
              <div class="xtl-help" id="xtl-profile-url-warning">服务地址只填根地址；如果粘贴了 /chat/completions、/responses 等具体接口，保存时会自动去掉。</div>
            </div>
            <div class="xtl-toolbar" style="margin-top: 10px">
              <button class="xtl-btn primary" data-marker="btn-profile-save" id="xtl-profile-save">保存账号</button>
              <button class="xtl-btn" data-marker="btn-profile-probe" id="xtl-profile-probe">检查连接</button>
              <button class="xtl-btn" data-marker="btn-profile-activate" id="xtl-profile-activate">设为当前使用</button>
              <button class="xtl-btn danger" data-marker="btn-profile-delete" id="xtl-profile-delete">删除账号</button>
            </div>
            <div class="xtl-help" data-marker="status-profile-editor" id="xtl-profile-status">选择一个账号，或点击“新增账号”。</div>
          </div>
        </div>
        <div class="xtl-panel" data-marker="panel-profile-key">
          <div class="xtl-panel-title">API Key 本机保存</div>
          <div class="xtl-panel-body">
            <div class="xtl-help">API Key 类似 AI 服务的付款密码，只保存在这台电脑。页面不会显示旧 Key，也不会写进翻译文件或 MOD 文件。</div>
            <div class="xtl-form-grid compact">
              <label><span>本机保存位置</span><input class="xtl-input" id="xtl-profile-key-env" data-marker="field-profile-key-env" readonly></label>
              <label><span>新的 API Key</span><input class="xtl-input" id="xtl-profile-key-value" data-marker="field-profile-key-value" type="password" autocomplete="new-password" placeholder="粘贴后保存，页面不会回显"></label>
            </div>
            <div class="xtl-toolbar" style="margin-top: 10px">
              <button class="xtl-btn primary" data-marker="btn-profile-key-save" id="xtl-profile-key-save">保存 Key</button>
              <span class="xtl-help" id="xtl-profile-key-status">先选择账号。</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    """


def _glossary_html() -> str:
    return """
    <div class="xtl-toolbar">
      <button class="xtl-btn active" data-marker="tab-glossary-vanilla" data-scope="vanilla">游戏本体术语</button>
      <button class="xtl-btn" data-marker="tab-glossary-mod" data-scope="mod">当前 MOD 术语</button>
      <button class="xtl-btn" data-marker="tab-glossary-player" data-scope="player">我的翻译偏好</button>
      <button class="xtl-btn" data-marker="tab-glossary-dnt" data-scope="do_not_translate">不要翻译的词</button>
      <input class="xtl-input" data-marker="field-glossary-search" id="xtl-glossary-search" placeholder="搜索术语 / 译名 / 备注">
      <button class="xtl-btn" data-marker="btn-add-glossary-entry" id="xtl-glossary-add" disabled>添加术语</button>
    </div>
    <div class="xtl-workbench xtl-glossary-workbench">
      <div class="xtl-panel" data-marker="panel-glossary-table">
        <div class="xtl-panel-title">专有名词表 <span class="xtl-detail-id" id="xtl-glossary-scope-title">游戏本体术语</span></div>
        <div class="xtl-panel-body">
          <div class="xtl-help" data-marker="status-glossary-empty-vanilla" id="xtl-glossary-message">这些词表会交给 AI，用来统一译名、保留人名地名和避免把缩写乱翻。游戏本体术语通常由工具从知识库自动整理，生成提示词时会自动挑相关术语。</div>
          <table class="xtl-table xtl-glossary-table" id="xtl-glossary-table">
            <thead><tr><th>原文</th><th>译名/规则</th><th>类别</th><th>来源</th><th>操作</th></tr></thead>
            <tbody><tr><td colspan="5">正在读取术语...</td></tr></tbody>
          </table>
        </div>
      </div>
      <div class="xtl-panel" data-marker="dialog-add-glossary-entry" id="xtl-glossary-editor" hidden>
        <div class="xtl-panel-title">添加/编辑玩家术语 <span class="xtl-detail-id" id="xtl-glossary-editor-scope">我的翻译偏好</span></div>
        <div class="xtl-panel-body">
          <div class="xtl-help">这里只写你自己的偏好，不会修改原始 MOD 文件。保存后，下一次生成提示词时 AI 会看到这些规则。</div>
          <div class="xtl-form-grid">
            <label><span>原文词</span><input class="xtl-input" data-marker="field-glossary-source" id="xtl-glossary-source" placeholder="例如 Starborn"></label>
            <label><span>译名 / 保留原文</span><input class="xtl-input" data-marker="field-glossary-target" id="xtl-glossary-target" placeholder="例如 星生子"></label>
            <label><span>原文语言</span><input class="xtl-input" data-marker="field-glossary-source-lang" id="xtl-glossary-source-lang" value="en"></label>
            <label><span>目标语言</span><input class="xtl-input" data-marker="field-glossary-target-lang" id="xtl-glossary-target-lang" value="zh-cn"></label>
            <label><span>类别</span><select class="xtl-select" data-marker="field-glossary-category" id="xtl-glossary-category"><option value="lore_term">剧情/世界观词</option><option value="faction">派系</option><option value="character">角色</option><option value="place">地点</option><option value="item">物品</option><option value="ui_label">菜单/界面词</option><option value="brand">品牌/缩写</option><option value="generic">普通词</option></select></label>
            <label><span>可信度</span><select class="xtl-select" id="xtl-glossary-confidence"><option value="preferred">玩家偏好</option><option value="canonical">固定译名</option><option value="candidate">候选译名</option></select></label>
            <label class="wide"><span>原文别名</span><input class="xtl-input" data-marker="field-glossary-aliases" id="xtl-glossary-source-aliases" placeholder="可选，用逗号分隔，例如 Starborn Guardian"></label>
            <label class="wide"><span>备注</span><textarea class="xtl-input xtl-profile-notes" id="xtl-glossary-notes" placeholder="给 AI 和自己看的说明，例如：Starfield 语境中统一用这个译名。"></textarea></label>
          </div>
          <div class="xtl-glossary-helper-grid" data-marker="panel-glossary-field-helpers">
            <div>原文词：游戏或 MOD 里出现的英文。</div>
            <div>译名：你希望 AI 使用的中文；“不要翻译”层会自动保持原文。</div>
            <div>别名：同一个词的其它写法，AI 遇到也会套用这条规则。</div>
            <div>类别：帮助 AI 判断这是地点、角色、派系还是界面文字。</div>
          </div>
          <div class="xtl-toolbar" style="margin-top: 10px">
            <button class="xtl-btn primary" data-marker="btn-glossary-save" id="xtl-glossary-save">保存术语</button>
            <button class="xtl-btn" data-marker="btn-glossary-cancel" id="xtl-glossary-cancel">取消</button>
            <span class="xtl-help" id="xtl-glossary-save-status">填写后保存。</span>
          </div>
        </div>
      </div>
    </div>
    """


def _logs_html(project: str | None) -> str:
    runs = _run_rows(project)
    selected_run = str(runs[0]["run_id"]) if runs else ""
    events = _recent_event_rows(project)
    run_options = "".join(
        f'<option value="{_esc(str(run["run_id"]))}">{_esc(_run_option_label(run, index))}</option>'
        for index, run in enumerate(runs, start=1)
    )
    if not run_options:
        run_options = '<option value="">暂无运行</option>'
    lines = "".join(
        f"<tr><td>{_esc(str(event['event_id']))}</td><td>{_esc(_event_kind_label(str(event['kind'])))}</td><td>{_esc(_short_display_id(event['batch_id']))}</td></tr>"
        for event in events
    )
    if not lines:
        lines = '<tr><td colspan="3">暂无事件。</td></tr>'
    return f"""
    <div class="xtl-workbench xtl-logs-workbench" data-project="{_esc(project or '')}">
      <div class="xtl-panel" data-marker="panel-log-stream">
        <div class="xtl-panel-title">翻译记录摘要</div>
        <div class="xtl-panel-body">
          <div class="xtl-help">普通玩家先看这里：完成、失败、需要人工复查都会出现在这里。右侧文件区是排查问题时使用的技术日志。</div>
          <table class="xtl-table"><thead><tr><th>#</th><th>事件</th><th>批次</th></tr></thead><tbody id="xtl-log-events">{lines}</tbody></table>
        </div>
      </div>
      <div class="xtl-panel" data-marker="panel-log-file-viewer">
        <div class="xtl-panel-title">技术日志文件</div>
        <div class="xtl-panel-body">
          <div class="xtl-toolbar">
            <span class="xtl-label">运行</span>
            <select class="xtl-select" data-marker="select-log-run" id="xtl-log-run" data-current="{_esc(selected_run)}">{run_options}</select>
            <button class="xtl-btn" id="xtl-log-refresh">刷新</button>
          </div>
          <div class="xtl-help">这些文件用于排查失败批次：状态、校验失败、原始响应和最终结果。</div>
          <div class="xtl-log-file-list" id="xtl-log-files"><span class="xtl-help">选择一次运行后读取文件。</span></div>
          <pre class="xtl-log-viewer" id="xtl-log-viewer">尚未选择文件。</pre>
        </div>
      </div>
    </div>
    """


def _settings_script() -> str:
    return """
    <script>
    (() => {
      if (window.__xtlSettingsBound) return;
      window.__xtlSettingsBound = true;
      async function saveSetting(path, payload) {
        const res = await fetch(path, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `${path} -> ${res.status}`);
        }
      }
      function orphanAckKey(summary) {
        const project = summary ? (summary.dataset.project || '') : '';
        return `xtl.orphanedStatusAcknowledged.${project}`;
      }
      function applyAcknowledgedOrphanStatus() {
        const summary = document.getElementById('xtl-status-summary');
        if (!summary || summary.dataset.statusKind !== 'orphaned') return;
        if (window.localStorage.getItem(orphanAckKey(summary)) !== '1') return;
        const text = summary.querySelector('[data-marker="status-gui-alive"]');
        const action = document.getElementById('xtl-ack-orphaned-status');
        if (text) text.textContent = '历史任务提醒已知晓；当前没有检测到运行中的翻译任务';
        summary.classList.remove('xtl-status-warn');
        summary.classList.add('xtl-status-good');
        if (action) action.remove();
      }
      document.addEventListener('change', async event => {
        const target = event.target;
        if (!target) return;
        try {
          if (target.id === 'xtl-theme-select') {
            await saveSetting('/api/theme', {theme: target.value});
            window.location.reload();
          }
          if (target.id === 'xtl-language-select') {
            await saveSetting('/api/language', {language: target.value});
            window.location.reload();
          }
        } catch (err) {
          console.error('settings update failed', err);
        }
      });
      const tabPaths = ['/project', '/entries', '/batches', '/prompt', '/profiles', '/glossary', '/logs'];
      document.addEventListener('click', event => {
        const ackButton = event.target && event.target.closest ? event.target.closest('#xtl-ack-orphaned-status') : null;
        if (ackButton) {
          event.preventDefault();
          const summary = document.getElementById('xtl-status-summary');
          window.localStorage.setItem(orphanAckKey(summary), '1');
          applyAcknowledgedOrphanStatus();
          return;
        }
        const link = event.target && event.target.closest ? event.target.closest('a[href^="/"]') : null;
        if (!link) return;
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        window.__xtlInternalNavigation = true;
        window.setTimeout(() => { window.__xtlInternalNavigation = false; }, 2000);
        event.preventDefault();
        window.location.assign(link.href);
      }, true);
      function closeOpenPanel() {
        const panels = ['xtl-glossary-editor'];
        let closed = false;
        for (const id of panels) {
          const panel = document.getElementById(id);
          if (panel && !panel.hidden) {
            panel.hidden = true;
            closed = true;
          }
        }
        return closed;
      }
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          if (closeOpenPanel()) {
            event.preventDefault();
          }
          return;
        }
        if (!(event.ctrlKey || event.metaKey)) return;
        if (/^[1-7]$/.test(event.key)) {
          event.preventDefault();
          window.__xtlInternalNavigation = true;
          window.location.href = tabPaths[Number(event.key) - 1];
          return;
        }
        const key = String(event.key || '').toLowerCase();
        if (key === 'b') {
          event.preventDefault();
          window.__xtlInternalNavigation = true;
          window.location.href = '/batches';
          return;
        }
        if (key === 'r') {
          event.preventDefault();
          const refreshButton = document.querySelector('#xtl-refresh-batches, #xtl-log-refresh');
          if (refreshButton) {
            refreshButton.click();
          } else {
            window.location.reload();
          }
        }
      });
      applyAcknowledgedOrphanStatus();
    })();
    </script>
    """


def _logs_script(project: str | None) -> str:
    project_json = _json_for_script(project or "")
    script = r"""
    <script>
    (() => {
      const project = __PROJECT__;
      const byId = id => document.getElementById(id);
      const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      const fileLabels = {
        'status.toml': '运行状态',
        'validator-failures.jsonl': '需要复查的失败项',
        'results.json': '翻译结果',
        'system-prompt.md': '完整 AI 提示词',
        'plan.json': '批次计划',
      };
      function fileLabel(name) {
        return fileLabels[name] || name;
      }
      async function api(path) {
        const res = await fetch(path, {credentials: 'same-origin'});
        const text = await res.text();
        const data = text ? JSON.parse(text) : null;
        if (!res.ok) throw new Error((data && (data.detail || data.message)) || `${path} -> ${res.status}`);
        return data;
      }
      function selectedRun() {
        return byId('xtl-log-run')?.value || '';
      }
      function renderFiles(files) {
        const root = byId('xtl-log-files');
        if (!root) return;
        if (!files || !files.length) {
          root.innerHTML = '<span class="xtl-help">这次运行没有可查看的日志文件。</span>';
          return;
        }
        root.innerHTML = files.map(file => `<button class="xtl-btn" title="${esc(file.name)}" data-log-file="${esc(file.name)}">${esc(fileLabel(file.name))}</button>`).join('');
      }
      async function loadRun() {
        const runId = selectedRun();
        const viewer = byId('xtl-log-viewer');
        if (!project || !runId) {
          renderFiles([]);
          if (viewer) viewer.textContent = '尚无运行。';
          return;
        }
        const data = await api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(runId)}/logs`);
        renderFiles(data.files || []);
        if (viewer) {
          viewer.textContent = [
            '运行状态',
            data.status_toml || '(没有 status.toml)',
            '',
            '需要复查的失败项',
            data.validator_failures || '(没有校验失败记录)',
          ].join('\n');
        }
      }
      async function openFile(name) {
        const runId = selectedRun();
        if (!project || !runId || !name) return;
        const data = await api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(runId)}/log-file/${encodeURIComponent(name)}`);
        const viewer = byId('xtl-log-viewer');
        if (viewer) viewer.textContent = `${fileLabel(name)} (${name})\n\n${data.content || ''}`;
      }
      document.addEventListener('change', event => {
        if (event.target && event.target.id === 'xtl-log-run') loadRun();
      });
      document.addEventListener('click', event => {
        const target = event.target;
        if (!target) return;
        if (target.id === 'xtl-log-refresh') loadRun();
        if (target.dataset && target.dataset.logFile) openFile(target.dataset.logFile);
      });
      function startWhenReady() {
        if (byId('xtl-log-run')) {
          loadRun();
          return;
        }
        window.setTimeout(startWhenReady, 50);
      }
      startWhenReady();
    })();
    </script>
    """
    return script.replace("__PROJECT__", project_json)


def _glossary_script() -> str:
    return """
    <script>
    (() => {
      const scopes = {
        vanilla: '游戏本体术语',
        mod: '当前 MOD 术语',
        player: '我的翻译偏好',
        do_not_translate: '不要翻译的词',
      };
      const glossaryIntro = '这些词表会交给 AI，用来统一译名、保留人名地名和避免把缩写乱翻。游戏本体术语会在生成提示词时自动挑相关条目，不需要手动添加。';
      const writableScopes = new Set(['player', 'do_not_translate']);
      const activeProject = new URLSearchParams(window.location.search).get('project') || '';
      let currentScope = 'vanilla';
      let entries = [];
      let editingRecordId = null;
      let searchTimer = null;
      const byId = id => document.getElementById(id);
      const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      function api(path, options = {}) {
        return fetch(path, {credentials: 'same-origin', ...options}).then(async res => {
          const text = await res.text();
          const data = text ? JSON.parse(text) : {};
          if (!res.ok) {
            const err = new Error(data.message || data.detail || `${path} -> ${res.status}`);
            err.data = data;
            throw err;
          }
          return data;
        });
      }
      function categoryLabel(value) {
        return {
          lore_term: '世界观',
          faction: '派系',
          character: '角色',
          place: '地点',
          location: '地点',
          item: '物品',
          ui_label: '菜单/界面',
          brand: '品牌/缩写',
          generic: '普通词',
        }[value] || value || '-';
      }
      function packLabel(entry) {
        const pack = entry.pack_id || '';
        if (entry.scope === 'player' || pack.startsWith('translator-overrides')) return '玩家规则';
        if (entry.scope === 'do_not_translate') return '不要翻译';
        if (entry.scope === 'vanilla') return '本体知识库';
        if (entry.scope === 'mod') return 'MOD 知识库';
        return pack || '-';
      }
      function setScope(scope) {
        currentScope = scope;
        editingRecordId = null;
        byId('xtl-glossary-editor').hidden = true;
        document.querySelectorAll('[data-scope]').forEach(btn => btn.classList.toggle('active', btn.dataset.scope === scope));
        loadGlossary();
      }
      function renderTable() {
        const body = document.querySelector('#xtl-glossary-table tbody');
        if (!body) return;
        if (!entries.length) {
          const marker = `status-glossary-empty-${currentScope === 'do_not_translate' ? 'dnt' : currentScope}`;
          body.innerHTML = `<tr><td colspan="5"><div class="xtl-empty" data-marker="${marker}">${esc(byId('xtl-glossary-message')?.textContent || '暂无术语。')}</div></td></tr>`;
          return;
        }
        body.innerHTML = entries.map(entry => {
          const aliases = (entry.source_aliases || []).length ? `<div class="xtl-help">别名：${esc((entry.source_aliases || []).join(', '))}</div>` : '';
          const target = currentScope === 'do_not_translate' ? '保持原文，不翻译' : esc(entry.target || '');
          const actions = writableScopes.has(currentScope)
            ? `<button class="xtl-btn" data-action="edit" data-record-id="${esc(entry.record_id)}">编辑</button> <button class="xtl-btn danger" data-action="delete" data-record-id="${esc(entry.record_id)}">删除</button>`
            : '<span class="xtl-help">只读，由工具自动维护</span>';
          return `<tr data-marker="row-glossary-${esc(entry.record_id)}">
            <td><b>${esc(entry.source)}</b>${aliases}</td>
            <td>${target}</td>
            <td>${esc(categoryLabel(entry.category))}</td>
            <td>${esc(packLabel(entry))}</td>
            <td class="xtl-glossary-actions">${actions}</td>
          </tr>`;
        }).join('');
      }
      function renderScope(data) {
        entries = data.entries || [];
        byId('xtl-glossary-scope-title').textContent = scopes[currentScope] || currentScope;
        byId('xtl-glossary-message').textContent = data.message ? `${glossaryIntro}${data.message}` : glossaryIntro;
        byId('xtl-glossary-message').dataset.marker = `status-glossary-empty-${currentScope === 'do_not_translate' ? 'dnt' : currentScope}`;
        const add = byId('xtl-glossary-add');
        add.disabled = !data.writable;
        add.classList.toggle('primary', data.writable);
        if (!data.writable) {
          byId('xtl-glossary-editor').hidden = true;
        }
        renderTable();
      }
      async function loadGlossary() {
        const params = new URLSearchParams({scope: currentScope});
        if (activeProject) params.set('project', activeProject);
        const search = byId('xtl-glossary-search')?.value || '';
        if (search.trim()) params.set('search', search.trim());
        const data = await api(`/api/glossary?${params}`);
        renderScope(data);
      }
      function clearEditor() {
        editingRecordId = null;
        byId('xtl-glossary-source').value = '';
        byId('xtl-glossary-target').value = currentScope === 'do_not_translate' ? '保持原文' : '';
        byId('xtl-glossary-source-lang').value = 'en';
        byId('xtl-glossary-target-lang').value = 'zh-cn';
        byId('xtl-glossary-category').value = currentScope === 'do_not_translate' ? 'brand' : 'lore_term';
        byId('xtl-glossary-confidence').value = 'preferred';
        byId('xtl-glossary-source-aliases').value = '';
        byId('xtl-glossary-notes').value = '';
        byId('xtl-glossary-editor-scope').textContent = scopes[currentScope] || currentScope;
        byId('xtl-glossary-save-status').textContent = '填写后保存。';
      }
      function openEditor(entry = null) {
        if (!writableScopes.has(currentScope)) return;
        clearEditor();
        if (entry) {
          editingRecordId = entry.record_id;
          byId('xtl-glossary-source').value = entry.source || '';
          byId('xtl-glossary-target').value = currentScope === 'do_not_translate' ? (entry.source || '') : (entry.target || '');
          byId('xtl-glossary-source-lang').value = entry.source_lang || 'en';
          byId('xtl-glossary-target-lang').value = entry.target_lang || 'zh-cn';
          byId('xtl-glossary-category').value = entry.category || (currentScope === 'do_not_translate' ? 'brand' : 'lore_term');
          byId('xtl-glossary-confidence').value = entry.confidence || 'preferred';
          byId('xtl-glossary-source-aliases').value = (entry.source_aliases || []).join(', ');
          byId('xtl-glossary-notes').value = entry.notes || '';
        }
        byId('xtl-glossary-editor').hidden = false;
      }
      function payloadFromEditor() {
        const source = byId('xtl-glossary-source').value.trim();
        let target = byId('xtl-glossary-target').value.trim();
        if (currentScope === 'do_not_translate') target = source;
        return {
          record_id: editingRecordId,
          scope: currentScope,
          source,
          target,
          source_lang: byId('xtl-glossary-source-lang').value.trim() || 'en',
          target_lang: byId('xtl-glossary-target-lang').value.trim() || 'zh-cn',
          category: byId('xtl-glossary-category').value || 'lore_term',
          confidence: byId('xtl-glossary-confidence').value || 'preferred',
          source_aliases: byId('xtl-glossary-source-aliases').value.split(/[,;]/).map(x => x.trim()).filter(Boolean),
          target_aliases: [],
          notes: byId('xtl-glossary-notes').value,
        };
      }
      async function saveGlossary() {
        const payload = payloadFromEditor();
        if (!payload.source) {
          byId('xtl-glossary-save-status').textContent = '请先填写原文词。';
          byId('xtl-glossary-save-status').className = 'xtl-help danger';
          return;
        }
        if (!payload.target && currentScope !== 'do_not_translate') {
          byId('xtl-glossary-save-status').textContent = '请填写你希望 AI 使用的中文译名。';
          byId('xtl-glossary-save-status').className = 'xtl-help danger';
          return;
        }
        const path = editingRecordId ? `/api/glossary/${encodeURIComponent(editingRecordId)}` : '/api/glossary';
        const result = await api(path, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload),
        });
        editingRecordId = result.entry.record_id;
        byId('xtl-glossary-save-status').textContent = '已保存。下一次生成提示词时会使用这条规则。';
        byId('xtl-glossary-save-status').className = 'xtl-help good';
        await loadGlossary();
      }
      async function deleteGlossary(recordId) {
        if (!window.confirm('只删除这条玩家术语规则，不会修改原始 MOD 文件。确定删除吗？')) return;
        await api(`/api/glossary/${encodeURIComponent(recordId)}`, {method: 'DELETE'});
        await loadGlossary();
      }
      document.addEventListener('click', event => {
        const scopeButton = event.target && event.target.closest ? event.target.closest('[data-scope]') : null;
        if (scopeButton) setScope(scopeButton.dataset.scope);
        if (event.target && event.target.id === 'xtl-glossary-add') openEditor();
        if (event.target && event.target.id === 'xtl-glossary-cancel') byId('xtl-glossary-editor').hidden = true;
        if (event.target && event.target.id === 'xtl-glossary-save') saveGlossary();
        const action = event.target && event.target.dataset ? event.target.dataset.action : '';
        const recordId = event.target && event.target.dataset ? event.target.dataset.recordId : '';
        if (action === 'edit') {
          const entry = entries.find(item => item.record_id === recordId);
          if (entry) openEditor(entry);
        }
        if (action === 'delete' && recordId) deleteGlossary(recordId);
      });
      document.addEventListener('input', event => {
        if (event.target && event.target.id === 'xtl-glossary-search') {
          window.clearTimeout(searchTimer);
          searchTimer = window.setTimeout(() => loadGlossary(), 200);
        }
      });
      function startWhenReady() {
        if (byId('xtl-glossary-table')) {
          loadGlossary();
          return;
        }
        window.setTimeout(startWhenReady, 50);
      }
      startWhenReady();
    })();
    </script>
    """


def _profiles_script() -> str:
    return """
    <script>
    (() => {
      let profiles = [];
      let activeName = '';
      let selectedName = '';
      let originalName = '';
      const byId = id => document.getElementById(id);
      const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      const providerHelp = {
        'openai-compat': '适合 OpenRouter、DeepSeek 等兼容 OpenAI 的服务。大多数玩家用 OpenRouter 时选这个。',
        openai: '适合直接使用 OpenAI 官方账号。',
        anthropic: '适合直接使用 Anthropic Claude 官方账号。',
        gemini: '适合直接使用 Google Gemini 官方账号。',
      };
      const providerLabels = {
        'openai-compat': 'OpenRouter / DeepSeek 通用接口',
        openai: 'OpenAI 官方接口',
        anthropic: 'Claude 官方接口',
        gemini: 'Gemini 官方接口',
      };
      const providerDefaults = {
        'openai-compat': {base_url: 'https://openrouter.ai/api/v1', api_key_env: 'BGS_TRANSLATOR_KEY_OPENROUTER', json_mode: 'json_schema', require_parameters: 'true'},
        openai: {base_url: 'https://api.openai.com/v1', api_key_env: 'BGS_TRANSLATOR_KEY_OPENAI', json_mode: '', require_parameters: 'false'},
        anthropic: {base_url: 'https://api.anthropic.com/v1', api_key_env: 'BGS_TRANSLATOR_KEY_ANTHROPIC', json_mode: '', require_parameters: 'false'},
        gemini: {base_url: 'https://generativelanguage.googleapis.com', api_key_env: 'BGS_TRANSLATOR_KEY_GEMINI', json_mode: '', require_parameters: 'false'},
      };
      function api(path, options = {}) {
        return fetch(path, {credentials: 'same-origin', ...options}).then(async res => {
          const text = await res.text();
          const data = text ? JSON.parse(text) : {};
          if (!res.ok) {
            const err = new Error(data.message || data.detail || `${path} -> ${res.status}`);
            err.data = data;
            throw err;
          }
          return data;
        });
      }
      function setStatus(text, tone = '') {
        const el = byId('xtl-profile-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function setKeyStatus(text, tone = '') {
        const el = byId('xtl-profile-key-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function selectedProfile() {
        return profiles.find(profile => profile.name === selectedName) || null;
      }
      function providerLabel(value) {
        return providerLabels[value] || value || 'AI 服务';
      }
      function envNameFromProfileName(name, sdkKind) {
        const cleaned = String(name || '').toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
        if (cleaned) return `BGS_TRANSLATOR_KEY_${cleaned}`;
        const defaults = providerDefaults[sdkKind || 'openai-compat'];
        return defaults ? defaults.api_key_env : 'BGS_TRANSLATOR_KEY_OPENROUTER';
      }
      function keyLabel(profile) {
        return profile && profile.key_configured ? '已保存' : '未保存';
      }
      function renderTable() {
        const body = document.querySelector('#xtl-profiles-table tbody');
        if (!body) return;
        if (!profiles.length) {
          body.innerHTML = '<tr><td colspan="4">还没有 AI 服务账号。点击“新增账号”开始。</td></tr>';
          return;
        }
        body.innerHTML = profiles.map(profile => {
          const active = profile.name === selectedName ? ' class="active"' : '';
          const tone = profile.key_configured ? 'complete' : 'failed';
          return `<tr${active} data-profile-name="${esc(profile.name)}" data-marker="row-profile-${esc(profile.name)}">
            <td><b>${esc(profile.name)}</b><div class="xtl-help">${esc(providerLabel(profile.sdk_kind))}</div></td>
            <td>${esc(profile.model || '')}</td>
            <td><span class="xtl-status-pill ${tone}">${keyLabel(profile)}</span></td>
            <td>${profile.active ? '<span class="xtl-status-pill complete">当前使用</span>' : '<span class="xtl-status-pill">备用</span>'}</td>
          </tr>`;
        }).join('');
      }
      function clearForm() {
        selectedName = '';
        originalName = '';
        byId('xtl-profile-name').value = '';
        byId('xtl-profile-sdk').value = 'openai-compat';
        byId('xtl-profile-base-url').value = 'https://openrouter.ai/api/v1';
        byId('xtl-profile-model').value = '';
        byId('xtl-profile-env').value = 'BGS_TRANSLATOR_KEY_OPENROUTER';
        byId('xtl-profile-concurrency').value = '4';
        byId('xtl-profile-rpm').value = '';
        byId('xtl-profile-json-mode').value = 'json_schema';
        byId('xtl-profile-require-parameters').value = 'true';
        byId('xtl-profile-notes').value = '';
        byId('xtl-profile-key-env').value = '';
        byId('xtl-profile-key-value').value = '';
        byId('xtl-profile-editor-title').textContent = '新增';
        setStatus('填写 AI 服务账号后保存。OpenRouter 用户通常只需要名称、服务类型、模型和 Key。');
        setKeyStatus('保存账号后再写入 Key。');
        renderTable();
      }
      function fillForm(profile) {
        if (!profile) {
          clearForm();
          return;
        }
        selectedName = profile.name;
        originalName = profile.name;
        byId('xtl-profile-name').value = profile.name || '';
        byId('xtl-profile-sdk').value = profile.sdk_kind || 'openai-compat';
        byId('xtl-profile-base-url').value = profile.base_url || '';
        byId('xtl-profile-model').value = profile.model || '';
        byId('xtl-profile-env').value = profile.api_key_env || '';
        byId('xtl-profile-concurrency').value = profile.max_concurrency || 4;
        byId('xtl-profile-rpm').value = profile.rate_limit_rpm || '';
        byId('xtl-profile-json-mode').value = profile.json_mode || '';
        byId('xtl-profile-require-parameters').value = String(Boolean(profile.require_parameters));
        byId('xtl-profile-notes').value = profile.notes || '';
        byId('xtl-profile-key-env').value = profile.api_key_env || '';
        byId('xtl-profile-key-value').value = '';
        byId('xtl-profile-editor-title').textContent = profile.active ? `${profile.name} / 当前使用` : profile.name;
        setStatus(`${providerHelp[profile.sdk_kind] || '用于提交 AI 翻译请求。'} Key 状态：${keyLabel(profile)}。`);
        setKeyStatus(profile.key_configured ? '已有 Key。需要更换时粘贴新的 Key 后保存。' : '还没有保存 Key。粘贴 API Key 后点击保存。', profile.key_configured ? 'good' : 'danger');
        renderTable();
      }
      function payloadFromForm() {
        const optionalNumber = id => {
          const value = byId(id).value.trim();
          return value ? Number(value) : null;
        };
        return {
          name: byId('xtl-profile-name').value.trim(),
          original_name: originalName || null,
          sdk_kind: byId('xtl-profile-sdk').value,
          base_url: byId('xtl-profile-base-url').value.trim(),
          model: byId('xtl-profile-model').value.trim(),
          api_key_env: byId('xtl-profile-env').value.trim(),
          max_concurrency: Number(byId('xtl-profile-concurrency').value || 4),
          rate_limit_rpm: optionalNumber('xtl-profile-rpm'),
          cost_cap_usd: null,
          notes: byId('xtl-profile-notes').value,
          prompt_caching: false,
          json_mode: byId('xtl-profile-json-mode').value || null,
          require_parameters: byId('xtl-profile-require-parameters').value === 'true',
        };
      }
      async function loadProfiles(preferName = '') {
        const data = await api('/api/profiles');
        profiles = data.profiles || [];
        activeName = data.active || '';
        const activeLabel = byId('xtl-profile-active-label');
        if (activeLabel) activeLabel.textContent = activeName || '未配置';
        const nextName = preferName || selectedName || activeName || (profiles[0] && profiles[0].name) || '';
        const next = profiles.find(profile => profile.name === nextName) || profiles[0] || null;
        renderTable();
        if (next) fillForm(next);
        else clearForm();
      }
      async function saveProfile() {
        const payload = payloadFromForm();
        if (!payload.name || !payload.model || !payload.base_url || !payload.api_key_env) {
          setStatus('名称、API 地址、模型、Key 变量名都必须填写。', 'danger');
          return;
        }
        try {
          const result = await api('/api/profiles', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
          });
          const suffix = result.stripped_suffix ? ` 已自动去掉 ${result.stripped_suffix}。` : '';
          setStatus(`已保存 AI 服务账号。${suffix}`, 'good');
          await loadProfiles(result.profile.name);
        } catch (err) {
          setStatus(`保存失败：${err.message}`, 'danger');
        }
      }
      async function activateProfile() {
        const profile = selectedProfile();
        if (!profile) {
          setStatus('先选择一个账号。', 'danger');
          return;
        }
        await api(`/api/profiles/${encodeURIComponent(profile.name)}/activate`, {method: 'POST'});
        setStatus('已设为当前翻译使用的 AI 服务账号。', 'good');
        await loadProfiles(profile.name);
      }
      async function saveKey() {
        const profile = selectedProfile();
        const value = byId('xtl-profile-key-value').value;
        if (!profile) {
          setKeyStatus('先选择一个账号。', 'danger');
          return;
        }
        if (!value.trim()) {
          setKeyStatus('请粘贴新的 API Key。', 'danger');
          return;
        }
        await api(`/api/profiles/${encodeURIComponent(profile.name)}/key`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({api_key: value}),
        });
        byId('xtl-profile-key-value').value = '';
        setKeyStatus('Key 已保存到本机 profiles/.env，页面不会显示内容。', 'good');
        await loadProfiles(profile.name);
      }
      async function probeProfile() {
        const profile = selectedProfile();
        if (!profile) {
          setStatus('先选择一个账号。', 'danger');
          return;
        }
        setStatus('正在检查连接，会发送一次最小测试请求，可能消耗极少额度...', 'good');
        try {
          await api(`/api/profiles/${encodeURIComponent(profile.name)}/probe`, {method: 'POST'});
          setStatus('连接成功。这个账号可以用于 AI 汉化。', 'good');
        } catch (err) {
          if (err.data && err.data.code === 'missing_api_key') {
            setStatus(`缺少 API Key：请先在下方保存 ${err.data.api_key_env}。`, 'danger');
          } else {
            setStatus(`连接失败：${err.message}`, 'danger');
          }
        }
      }
      async function deleteProfile() {
        const profile = selectedProfile();
        if (!profile) {
          setStatus('先选择一个账号。', 'danger');
          return;
        }
        if (!window.confirm(`只删除账号配置“${profile.name}”，不会删除这台电脑里已保存的 API Key。确定删除吗？`)) {
          return;
        }
        await api(`/api/profiles/${encodeURIComponent(profile.name)}`, {method: 'DELETE'});
        setStatus('已删除账号配置；这台电脑里保存过的 Key 不会自动删除。');
        selectedName = '';
        originalName = '';
        await loadProfiles();
      }
      function applyProviderDefaults() {
        if (originalName) return;
        const defaults = providerDefaults[byId('xtl-profile-sdk').value];
        if (!defaults) return;
        byId('xtl-profile-base-url').value = defaults.base_url;
        const envName = envNameFromProfileName(byId('xtl-profile-name').value, byId('xtl-profile-sdk').value);
        byId('xtl-profile-env').value = envName;
        byId('xtl-profile-key-env').value = envName;
        byId('xtl-profile-json-mode').value = defaults.json_mode;
        byId('xtl-profile-require-parameters').value = defaults.require_parameters;
      }
      document.addEventListener('click', event => {
        const row = event.target && event.target.closest ? event.target.closest('#xtl-profiles-table tbody tr[data-profile-name]') : null;
        if (row) {
          const profile = profiles.find(item => item.name === row.getAttribute('data-profile-name'));
          if (profile) fillForm(profile);
        }
        if (event.target && event.target.id === 'xtl-profile-new') clearForm();
        if (event.target && event.target.id === 'xtl-profile-refresh') loadProfiles();
        if (event.target && event.target.id === 'xtl-profile-save') saveProfile();
        if (event.target && event.target.id === 'xtl-profile-activate') activateProfile();
        if (event.target && event.target.id === 'xtl-profile-key-save') saveKey();
        if (event.target && event.target.id === 'xtl-profile-probe') probeProfile();
        if (event.target && event.target.id === 'xtl-profile-delete') deleteProfile();
      });
      document.addEventListener('input', event => {
        if (event.target && event.target.id === 'xtl-profile-base-url') {
          const value = event.target.value.trim();
          const warning = byId('xtl-profile-url-warning');
          if (!warning) return;
          if (/\\/(chat\\/completions|responses|messages|generate_content|generateContent)\\/?$/i.test(value)) {
            warning.textContent = '检测到具体接口路径。保存时会自动去掉，只保留 API 根地址。';
            warning.className = 'xtl-help good';
          } else {
            warning.textContent = 'API 地址只填根地址；如果粘贴了 /chat/completions、/responses 等具体接口，保存时会自动去掉。';
            warning.className = 'xtl-help';
          }
        }
        if (event.target && event.target.id === 'xtl-profile-name' && !originalName) {
          const envName = envNameFromProfileName(event.target.value, byId('xtl-profile-sdk').value);
          byId('xtl-profile-env').value = envName;
          byId('xtl-profile-key-env').value = envName;
        }
      });
      document.addEventListener('change', event => {
        if (event.target && event.target.id === 'xtl-profile-sdk') applyProviderDefaults();
      });
      function startWhenReady() {
        if (byId('xtl-profile-key-value') && byId('xtl-profiles-table')) {
          loadProfiles();
          return;
        }
        window.setTimeout(startWhenReady, 50);
      }
      startWhenReady();
    })();
    </script>
    """


def _prompt_script(project: str | None) -> str:
    planned_json = _json_for_script(_planned_batches(project))
    project_json = _json_for_script(project or "")
    script = """
    <script>
    (() => {
      let current = null;
      const planned = __PLANNED__;
      const noLivePreviewLabel = '当前没有等待确认的批次';
      const promptBody = () => document.getElementById('xtl-prompt-body');
      const batchSelect = () => document.getElementById('xtl-batch-select');
      const historySelect = () => document.getElementById('xtl-history-batch-select');
      const statusLine = () => document.getElementById('xtl-preview-status');
      const startPlanStatus = () => document.getElementById('xtl-start-plan-status');
      function setPreviewStatus(text, tone = '') {
        const el = statusLine();
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function setStartPlanStatus(text, tone = '') {
        const el = startPlanStatus();
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function setBudgetStatus(text, tone = '') {
        const el = document.getElementById('xtl-budget-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function budgetNumber(id, fallback) {
        const input = document.getElementById(id);
        const value = Number(input?.value || fallback);
        const min = Number(input?.min || Number.NEGATIVE_INFINITY);
        const max = Number(input?.max || Number.POSITIVE_INFINITY);
        const rounded = Number.isFinite(value) ? Math.round(value) : fallback;
        return Math.min(max, Math.max(min, rounded));
      }
      async function saveTranslationBudgets() {
        const payload = {
          glossary_max_terms: budgetNumber('xtl-budget-glossary-max-terms', 500),
          glossary_max_prompt_chars: budgetNumber('xtl-budget-glossary-max-prompt-chars', 80000),
          glossary_candidate_source_terms: budgetNumber('xtl-budget-glossary-candidate-source-terms', 32),
        };
        setBudgetStatus('正在保存高级预算...');
        try {
          const res = await fetch('/api/settings/behavior/translation-budgets', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
          });
          const saved = await res.json();
          if (!res.ok) {
            const detail = typeof saved.detail === 'string' ? saved.detail : (saved.detail?.message || `保存失败：${res.status}`);
            throw new Error(detail);
          }
          if (document.getElementById('xtl-budget-glossary-max-terms')) document.getElementById('xtl-budget-glossary-max-terms').value = saved.glossary_max_terms;
          if (document.getElementById('xtl-budget-glossary-max-prompt-chars')) document.getElementById('xtl-budget-glossary-max-prompt-chars').value = saved.glossary_max_prompt_chars;
          if (document.getElementById('xtl-budget-glossary-candidate-source-terms')) document.getElementById('xtl-budget-glossary-candidate-source-terms').value = saved.glossary_candidate_source_terms;
          setBudgetStatus('已保存。下一次生成提示词会使用这些预算；当前运行中的任务不会被改写。', 'good');
        } catch (err) {
          setBudgetStatus(`保存失败：${err.message || err}`, 'danger');
        }
      }
      function shortId(value) {
        return String(value || '').slice(0, 8);
      }
      function previewLabel(msg) {
        const count = Array.isArray(msg.items) ? msg.items.length : 0;
        const batchText = count ? `${count} 条` : '若干条';
        const index = Number(msg.batch_index || 1);
        const totalBatches = Number(msg.total_batches || 0);
        const totalItems = Number(msg.total_items || 0);
        if (totalBatches && totalItems) return `当前第 ${index}/${totalBatches} 组：本组 ${batchText}，本次任务共 ${totalItems} 条，等待确认`;
        if (totalBatches) return `当前第 ${index}/${totalBatches} 组：本组 ${batchText}，等待确认`;
        return `当前第 ${index} 组文本：${batchText}，等待确认`;
      }
      function esc(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      }
      function evidenceReason(item) {
        const matchedBy = String(item.matched_by || '');
        const matchedText = String(item.matched_text || item.source || item.term || '');
        const scope = String(item.scope || '');
        const excluded = String(item.excluded_reason || '');
        if (excluded === 'budget_cap') return '命中了，但本批提示词空间有限，所以暂时没有注入。';
        if (excluded.startsWith('dedupe')) return '命中了，但和更高优先级或重复的术语合并了。';
        if (matchedBy === 'player_rule') return '因为这是你设置的固定翻译偏好。';
        if (matchedBy === 'dnt_rule') return '因为这是你设置的固定不翻译词。';
        if (matchedBy === 'alias_exact') return `因为本批文本出现了别名：${matchedText}。`;
        if (matchedBy === 'normalized') return `因为本批文本出现了同一术语的大小写、空格或标点变体：${matchedText}。`;
        if (matchedBy === 'rag') return '因为本体/MOD 术语库判断它和本批文本相关。';
        if (scope === 'do_not_translate') return `因为本批文本出现了需要保留原文的词：${matchedText}。`;
        return `因为本批文本出现了：${matchedText}。`;
      }
      function evidenceSection(title, items, open = false) {
        const rows = (items || []).slice(0, 80).map(item => `<li><b>${esc(item.source || item.term || '')}</b> → ${esc(item.target || '')}<div class="xtl-help">${esc(evidenceReason(item))}</div></li>`);
        if ((items || []).length > 80) rows.push(`<li class="xtl-help">还有 ${(items || []).length - 80} 条没有展开显示。</li>`);
        const body = rows.length ? `<ul class="xtl-evidence-list">${rows.join('')}</ul>` : '<div class="xtl-empty">没有项目。</div>';
        return `<details class="xtl-evidence-section"${open ? ' open' : ''}><summary>${esc(title)}（${(items || []).length}）</summary>${body}</details>`;
      }
      function renderGlossaryPanel(glossaryItems, evidenceItems) {
        const evidence = Array.isArray(evidenceItems) ? evidenceItems : [];
        if (evidence.length) {
          const included = evidence.filter(item => item.included);
          const deduped = evidence.filter(item => !item.included && String(item.excluded_reason || '').startsWith('dedupe'));
          const omitted = evidence.filter(item => !item.included && !String(item.excluded_reason || '').startsWith('dedupe'));
          return [
            evidenceSection('已注入提示词', included, true),
            evidenceSection('被去重或覆盖', deduped),
            evidenceSection('因预算省略', omitted),
          ].join('');
        }
        const lines = (glossaryItems || []).map(x => `${esc(x.source || x.term || '')} → ${esc(x.target || '')}`).filter(Boolean);
        return lines.length ? lines.join('<br>') : '<div class="xtl-empty">本次没有命中的专有名词。</div>';
      }
      function fillSidePanels(glossaryItems, dntItems, evidenceItems = []) {
        const glossary = document.getElementById('xtl-glossary');
        const dnt = document.getElementById('xtl-dnt');
        if (glossary) glossary.innerHTML = renderGlossaryPanel(glossaryItems || [], evidenceItems || []);
        if (dnt) dnt.textContent = (dntItems || []).join('\\n') || '本次没有额外的“不要翻译”词。';
      }
      function setPreviewControls(enabled) {
        for (const id of ['xtl-approve', 'xtl-approve-all', 'xtl-discard']) {
          const button = document.getElementById(id);
          if (button) button.disabled = !enabled;
        }
        document.querySelectorAll('[data-marker="prompt-scope-controls"] input').forEach(input => {
          input.disabled = !enabled;
        });
      }
      function renderPlanned(index) {
        const item = planned[index];
        if (!item) return;
        current = null;
        setPreviewControls(false);
        const select = batchSelect();
        if (select) {
          select.dataset.runId = '';
          select.dataset.batchId = '';
          select.innerHTML = `<option>${esc(noLivePreviewLabel)}</option>`;
          select.disabled = true;
        }
        setPreviewStatus('这是历史预览；不会发送给 AI。');
        setStartPlanStatus('历史任务只用于审计，不能恢复或重新启动。需要翻译时请回条目页重新提交新的批量队列。');
        if (promptBody()) promptBody().value = item.prompt || '';
        fillSidePanels(item.glossary_subset || [], item.do_not_translate || [], item.glossary_evidence || []);
      }
      function hydratePlannedSelect() {
        if (planned.length === 0) return;
        const select = historySelect();
        if (!select) {
          window.setTimeout(hydratePlannedSelect, 50);
          return;
        }
        if (select.options.length !== planned.length) {
          select.innerHTML = '';
          planned.forEach((item, index) => {
            const option = document.createElement('option');
            option.value = String(index);
            option.textContent = item.audit_label || item.label;
            select.appendChild(option);
          });
        }
        if (!current && !batchSelect()?.dataset.runId) renderPlanned(0);
      }
      function renderPreview(msg) {
        current = msg;
        setPreviewControls(true);
        setStartPlanStatus('已有当前待确认批次，请先处理上方内容。');
        const select = batchSelect();
        if (select) {
          select.innerHTML = `<option>${esc(previewLabel(msg))}</option>`;
          select.dataset.runId = msg.run_id || '';
          select.dataset.batchId = msg.batch_id || '';
          select.disabled = false;
        }
        setPreviewStatus('等待你确认。');
        if (promptBody()) promptBody().value = msg.system_prompt || '';
        fillSidePanels(msg.glossary_subset || [], msg.do_not_translate || [], msg.glossary_evidence || []);
      }
      async function reconcilePendingPreview() {
        try {
          const res = await fetch('/api/preview/pending', {credentials: 'same-origin'});
          if (!res.ok) return;
          const pending = await res.json();
          if (!Array.isArray(pending) || pending.length === 0) return;
          const next = pending[pending.length - 1];
          const currentKey = current ? `${current.run_id}/${current.batch_id}` : '';
          const nextKey = `${next.run_id}/${next.batch_id}`;
          if (nextKey !== currentKey) renderPreview(next);
        } catch (_err) {
          /* Polling is a fallback for missed websocket messages; ignore transient failures. */
        }
      }
      async function respond(op) {
        const select = batchSelect();
        const target = current || {
          run_id: select ? select.dataset.runId : '',
          batch_id: select ? select.dataset.batchId : '',
        };
        if (!target.run_id || !target.batch_id) {
          setPreviewStatus('当前没有等待确认的批次。', 'danger');
          return;
        }
        if (op === 'approve_all') {
          const count = current && Array.isArray(current.items) ? current.items.length : '当前';
          const ok = window.confirm(`这会让本次任务后续批次自动发送给 AI。当前显示 ${count} 条文本，仍然不会修改原始 MOD 文件。确定继续吗？`);
          if (!ok) {
            setPreviewStatus('已取消自动确认；你仍然可以只确认当前批次。');
            return;
          }
        }
        setPreviewStatus('正在发送确认...');
        const prompt = promptBody() ? promptBody().value : '';
        const res = await fetch(`/api/preview/respond/${encodeURIComponent(target.run_id)}/${encodeURIComponent(target.batch_id)}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({op, prompt})
        });
        if (!res.ok) {
          setPreviewStatus(`确认失败：${res.status}。请刷新页面后重试。`, 'danger');
          console.warn('preview respond failed', res.status);
          return;
        }
        current = null;
        setPreviewControls(false);
        if (select) {
          select.dataset.runId = '';
          select.dataset.batchId = '';
          select.innerHTML = `<option>${esc(noLivePreviewLabel)}</option>`;
          select.disabled = true;
        }
        setPreviewStatus(op === 'discarded' ? '已跳过这一段。' : '已发送确认，AI 正在继续翻译。', 'good');
      }
      document.addEventListener('click', (event) => {
        if (event.target && event.target.id === 'xtl-approve') respond('approved');
        if (event.target && event.target.id === 'xtl-approve-all') respond('approve_all');
        if (event.target && event.target.id === 'xtl-discard') respond('discarded');
        if (event.target && event.target.id === 'xtl-budget-save') saveTranslationBudgets();
      });
      document.addEventListener('change', (event) => {
        if (event.target && event.target.id === 'xtl-history-batch-select') renderPlanned(Number(event.target.value || 0));
      });
      const required = document.getElementById('xtl-preview-required');
      if (required) {
        required.addEventListener('change', () => {
          fetch(`/api/settings/behavior/prompt_preview_required?value=${required.checked}`, {method: 'POST', credentials: 'same-origin'});
        });
      }
      const ws = new WebSocket(`ws://${location.host}/ws`);
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.kind === 'preview.opened') renderPreview(msg);
        if (msg.kind === 'preview.closed' || msg.kind === 'preview.timeout') {
          current = null;
          setPreviewControls(false);
          const select = batchSelect();
          if (select) {
            select.dataset.runId = '';
            select.dataset.batchId = '';
            select.innerHTML = `<option>${esc(noLivePreviewLabel)}</option>`;
            select.disabled = true;
          }
          setPreviewStatus('当前没有等待确认的批次。页面只显示历史预览，不会发送给 AI。');
        }
      };
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', hydratePlannedSelect, {once: true});
      } else {
        hydratePlannedSelect();
      }
      window.setInterval(reconcilePendingPreview, 1000);
      reconcilePendingPreview();
    })();
    </script>
    """
    return script.replace("__PLANNED__", planned_json).replace("__PROJECT__", project_json)


def _batches_script(project: str | None) -> str:
    project_json = _json_for_script(project or "")
    script = """
    <script>
    (() => {
      const project = __PROJECT__;
      let currentRunId = '';
      let sinceEventId = 0;
      let userSelectedRun = false;
      let runSelectInteracting = false;
      let pendingRealtimeEvents = [];
      let runs = [];
      let currentBatches = [];
      let currentEvents = [];
      let runOptionsSignature = '';
      let realtimeRefreshTimer = 0;
      const metrics = window.__xtlBatchMetrics = {
        wsState: 'starting',
        wsMessages: [],
        refreshes: [],
        renderedEvents: [],
        lastRenderAt: 0,
      };
      const runSelect = () => document.getElementById('xtl-run-select');
      const batchBody = () => document.querySelector('#xtl-batches tbody');
      const eventsPanel = () => document.getElementById('xtl-batch-events');
      function pushMetric(name, value) {
        if (!metrics[name]) return;
        metrics[name].push(value);
        if (metrics[name].length > 80) metrics[name].shift();
      }
      const statusLabels = {
        running: '翻译中',
        queued: '排队中',
        orphaned: '未正常收尾',
        abandoned: '已中断，仅审计',
        paused: '已中断，仅审计',
        waiting_preview: '已中断，仅审计',
        complete: '已完成',
        failed: '有问题',
        cancelled: '已取消',
        discarded: '已抛弃',
        manual_review: '需人工复查',
      };
      const eventLabels = {
        'run.start': '开始翻译',
        'run.complete': '全部完成',
        'run.failed': '运行失败',
        'run.abandoned': '已中断，仅审计',
        'run.paused': '已中断，仅审计',
        'run.cancelled': '已取消',
        'batch.start': '批次开始',
        'batch.progress': '批次进度更新',
        'batch.request_sent': '已发送给模型',
        'batch.response_received': '模型已返回',
        'batch.complete': '批次完成',
        'batch.failed': '批次失败',
        'batch.abandoned': '已中断，仅审计',
        'batch.paused': '已中断，仅审计',
        'batch.waiting_preview': '已中断，仅审计',
        'batch.cancelled': '批次取消',
        'prompt.preview_request': '等待你确认提示词',
        'prompt.preview_response': '已确认提示词',
        'cost.update': '用量记录',
        manual_review: '需要人工复查',
      };
      function api(path, options = {}) {
        return fetch(path, {credentials: 'same-origin', ...options}).then(res => {
          if (!res.ok) throw new Error(`${path} -> ${res.status}`);
          return res.json();
        });
      }
      function shortId(value) {
        return String(value || '').slice(0, 8);
      }
      function esc(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      }
      function statusText(value) {
        return statusLabels[value] || value || '等待';
      }
      function eventText(value) {
        return eventLabels[value] || value || '记录';
      }
      function runLabel(run, index) {
        const state = run.status === 'running'
          ? '正在翻译'
          : (run.status === 'complete' ? '已完成' : statusText(run.status));
        const parts = [`${state}：${index === 0 ? '最近一次任务' : `第 ${index + 1} 次任务`}`];
        if (run.batches_total) parts.push(`${run.batches_total} 组文本`);
        return parts.join('，');
      }
      function preferredRunId() {
        const running = runs.find(run => run.status === 'running' || run.status === 'queued');
        return running ? running.run_id : (runs[0] ? runs[0].run_id : '');
      }
      function currentRun() {
        return runs.find(run => run.run_id === currentRunId) || null;
      }
      function isActiveRun(run) {
        return Boolean(run && (run.status === 'running' || run.status === 'queued'));
      }
      function isRunSelectInteracting() {
        const select = runSelect();
        return Boolean(select && (runSelectInteracting || document.activeElement === select));
      }
      function pauseAutoRefreshForRunSelect() {
        runSelectInteracting = true;
      }
      function resumeAutoRefreshForRunSelect() {
        runSelectInteracting = false;
        const pending = pendingRealtimeEvents;
        pendingRealtimeEvents = [];
        for (const msg of pending) applyRealtimeEvent(msg);
      }
      function updateCancelState(run) {
        const button = document.getElementById('xtl-cancel-run');
        const status = document.getElementById('xtl-cancel-status');
        if (!button) return;
        const canCancel = Boolean(run && run.status === 'running');
        button.disabled = !canCancel;
        button.title = canCancel ? '请求停止当前选中的运行中任务' : '当前选中的任务没有在运行';
        if (status && !canCancel && run) {
          status.textContent = run.status === 'orphaned'
            ? '这个历史任务没有正常收尾，但当前 GUI 没检测到它仍在运行。'
            : '当前选中的任务已结束，不需要停止。';
        }
      }
      function updateDiscardState(run) {
        const button = document.getElementById('xtl-discard-run-translations');
        const status = document.getElementById('xtl-discard-status');
        if (!button) return;
        const canDiscard = Boolean(run && run.status !== 'running' && run.status !== 'queued');
        button.disabled = !canDiscard;
        button.title = canDiscard
          ? '清除当前历史任务写入项目记忆库的译文'
          : '运行中或等待确认的任务不能抛弃翻译，请先停止或等待结束';
        if (status && !canDiscard && run) {
          status.textContent = run.status === 'running' || run.status === 'queued'
            ? '当前任务还在进行，不能抛弃已写入译文。'
            : '';
        }
      }
      function progressFromEvents(batch, events) {
        const total = Number(batch.item_count || 0);
        let done = batch.status === 'complete' ? total : 0;
        for (const event of events) {
          if (event.batch_id !== batch.batch_id) continue;
          const payload = event.payload || {};
          if (event.kind === 'batch.progress') done = Math.max(done, Number(payload.done || payload.items_done || 0));
          if (event.kind === 'batch.complete') done = total;
        }
        return {done, total};
      }
      function renderRuns() {
        const select = runSelect();
        if (!select) return;
        const previous = userSelectedRun ? (select.value || currentRunId) : (currentRunId || preferredRunId());
        const signature = JSON.stringify(runs.map(run => [
          run.run_id,
          run.status,
          run.batches_total,
        ]));
        if (signature !== runOptionsSignature) {
          select.innerHTML = runs.length
            ? runs.map((run, index) => `<option value="${esc(run.run_id)}" title="${esc(run.run_id)}">${esc(runLabel(run, index))}</option>`).join('')
            : '<option value="">尚无运行</option>';
          runOptionsSignature = signature;
        }
        currentRunId = runs.some(run => run.run_id === previous) ? previous : preferredRunId();
        select.value = currentRunId;
      }
      function renderSummary(run, batches) {
        const completed = batches.filter(batch => batch.status === 'complete').length;
        const set = (id, value) => {
          const el = document.getElementById(id);
          if (el) el.textContent = value;
        };
        set('xtl-run-status', statusText(run ? run.status : ''));
        set('xtl-run-batches', String(run ? run.batches_total : batches.length));
        set('xtl-run-complete', String(completed));
        set('xtl-run-billing', '看服务商后台');
        updateCancelState(run);
        updateDiscardState(run);
      }
      function renderBatches(batches, events) {
        const body = batchBody();
        if (!body) return;
        if (!batches.length) {
          body.innerHTML = '<tr><td colspan="4">这个运行还没有批次记录。</td></tr>';
          return;
        }
        body.innerHTML = batches.map((batch, index) => {
          const progress = progressFromEvents(batch, events);
          const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
          return `<tr data-marker="row-batches-${esc(batch.batch_id)}">
            <td title="${esc(batch.batch_id)}">第 ${index + 1} 组</td>
            <td><span class="xtl-status-pill ${batch.status || ''}">${statusText(batch.status)}</span></td>
            <td>${batch.item_count || 0}</td>
            <td><div class="xtl-progress" data-marker="status-batch-progress-${esc(batch.batch_id)}"><span style="width:${pct}%"></span><b>${progress.done}/${progress.total || batch.item_count || 0}</b></div></td>
          </tr>`;
        }).join('');
      }
      function batchLabel(batchId, batches) {
        const index = batches.findIndex(batch => batch.batch_id === batchId);
        return index >= 0 ? `第 ${index + 1} 组` : shortId(batchId);
      }
      function renderEvents(events, batches = []) {
        const panel = eventsPanel();
        if (!panel) return;
        const latest = events.slice(-60).reverse();
        panel.innerHTML = latest.length ? latest.map(event => {
          const batch = event.batch_id ? ` / ${batchLabel(event.batch_id, batches)}` : '';
          const titleBatch = event.batch_id ? ` / ${event.batch_id}` : '';
          return `<div class="xtl-event-line" data-event-id="${event.event_id}" title="${esc(event.kind)}${esc(titleBatch)}"><span>#${event.event_id}</span> ${eventText(event.kind)}${batch}</div>`;
        }).join('') : '暂无事件。';
        metrics.lastRenderAt = performance.now();
        pushMetric('renderedEvents', {
          at: metrics.lastRenderAt,
          latestEventId: latest.length ? latest[0].event_id : null,
          count: latest.length,
        });
      }
      async function refreshAll({keepSince = false, preferActive = false, force = false} = {}) {
        const started = performance.now();
        if (!project) return;
        if (!force && isRunSelectInteracting()) {
          pushMetric('refreshes', {
            started,
            ended: performance.now(),
            keepSince,
            preferActive,
            runId: currentRunId,
            skipped: 'run-select-open',
          });
          return;
        }
        try {
          runs = await api(`/api/projects/${encodeURIComponent(project)}/runs`);
          if (!userSelectedRun && preferActive) {
            const preferred = preferredRunId();
            if (preferred && currentRunId !== preferred) {
              currentRunId = preferred;
              sinceEventId = 0;
            }
          }
          renderRuns();
          if (!currentRunId) return;
          if (!keepSince) sinceEventId = 0;
          const currentRun = runs.find(run => run.run_id === currentRunId);
          const [batches, events] = await Promise.all([
            api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(currentRunId)}/batches`),
            api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(currentRunId)}/events?since=0`),
          ]);
          if (events.length) sinceEventId = Math.max(...events.map(event => Number(event.event_id || 0)));
          currentBatches = batches;
          currentEvents = events;
          renderSummary(currentRun, batches);
          renderBatches(batches, events);
          renderEvents(events, batches);
        } finally {
          pushMetric('refreshes', {
            started,
            ended: performance.now(),
            keepSince,
            preferActive,
            runId: currentRunId,
          });
        }
      }
      function rememberRealtimeEvent(msg) {
        if (!msg.event_id) return;
        if (currentEvents.some(event => Number(event.event_id || 0) === Number(msg.event_id))) return;
        currentEvents.push({
          event_id: msg.event_id,
          kind: msg.kind || '',
          run_id: msg.run_id || '',
          batch_id: msg.batch_id || '',
          payload: msg.payload || {},
          emitted_at: msg.emitted_at || '',
        });
        currentEvents = currentEvents.slice(-200);
        sinceEventId = Math.max(sinceEventId, Number(msg.event_id || 0));
      }
      function updateBatchFromRealtimeEvent(msg) {
        const batchId = msg.batch_id || (msg.payload && msg.payload.batch_id) || '';
        if (!batchId) return;
        let batch = currentBatches.find(item => item.batch_id === batchId);
        if (!batch && msg.kind === 'batch.start') {
          batch = {
            batch_id: batchId,
            run_id: msg.run_id || currentRunId,
            status: 'running',
            item_count: Number(msg.payload?.item_count || msg.payload?.total || 0),
            cost_usd: 0,
          };
          currentBatches.push(batch);
        }
        if (!batch) return;
        if (msg.kind === 'batch.start') {
          batch.status = 'running';
          batch.item_count = Number(msg.payload?.item_count || msg.payload?.total || batch.item_count || 0);
        }
        if (msg.kind === 'batch.request_sent') {
          batch.status = 'running';
          batch.item_count = Number(msg.payload?.total || batch.item_count || 0);
        }
        if (msg.kind === 'batch.response_received') {
          batch.status = 'running';
        }
        if (msg.kind === 'batch.complete') {
          batch.status = msg.payload?.status || 'complete';
        }
        if (msg.kind === 'batch.failed') batch.status = msg.payload?.status || 'failed';
        if (msg.kind === 'batch.cancelled') batch.status = 'cancelled';
      }
      function updateRunFromRealtimeEvent(msg) {
        const run = currentRun();
        if (!run) return;
        if (msg.kind === 'run.complete') run.status = 'complete';
        if (msg.kind === 'run.failed') run.status = 'failed';
        if (msg.kind === 'run.cancelled') run.status = 'cancelled';
      }
      function updateRunListFromRealtimeEvent(msg) {
        if (!msg.run_id) return;
        let run = runs.find(item => item.run_id === msg.run_id);
        if (!run && msg.kind === 'run.start') {
          run = {
            run_id: msg.run_id,
            status: 'running',
            batches_total: Number(msg.payload?.batches_total || 0),
          };
          runs = [run, ...runs];
          runOptionsSignature = '';
        }
        if (!run) return;
        if (msg.kind === 'run.start') run.status = 'running';
        if (msg.kind === 'run.complete') run.status = 'complete';
        if (msg.kind === 'run.failed') run.status = 'failed';
        if (msg.kind === 'run.cancelled') run.status = 'cancelled';
        if (msg.payload?.batches_total) run.batches_total = Number(msg.payload.batches_total);
      }
      function applyRealtimeEvent(msg) {
        if (!msg.run_id) return;
        if (isRunSelectInteracting()) {
          pendingRealtimeEvents.push(msg);
          return;
        }
        updateRunListFromRealtimeEvent(msg);
        if (!currentRunId && msg.kind === 'run.start') currentRunId = msg.run_id;
        if (!userSelectedRun && msg.kind === 'run.start') currentRunId = msg.run_id;
        if (msg.run_id !== currentRunId) {
          renderRuns();
          return;
        }
        rememberRealtimeEvent(msg);
        updateBatchFromRealtimeEvent(msg);
        updateRunFromRealtimeEvent(msg);
        renderRuns();
        renderSummary(currentRun(), currentBatches);
        renderBatches(currentBatches, currentEvents);
        renderEvents(currentEvents, currentBatches);
      }
      function scheduleRealtimeRefresh() {
        window.clearTimeout(realtimeRefreshTimer);
        realtimeRefreshTimer = window.setTimeout(() => {
          if (!isRunSelectInteracting()) refreshAll({preferActive: true, force: true});
        }, 250);
      }
      function refreshActiveRunIfNeeded() {
        if (!isActiveRun(currentRun())) return;
        refreshAll({preferActive: true});
      }
      async function cancelRun() {
        const status = document.getElementById('xtl-cancel-status');
        if (!project || !currentRunId) {
          if (status) status.textContent = '先选择一次运行。';
          return;
        }
        const run = currentRun();
        if (!run || run.status !== 'running') {
          if (status) status.textContent = '当前选中的任务已结束，不需要停止。';
          updateCancelState(run);
          return;
        }
        if (!window.confirm('会请求当前翻译任务尽快停止。已经发送给 AI 的请求可能仍在服务商侧处理，确定继续吗？')) return;
        if (status) status.textContent = '正在写入停止请求...';
        try {
          await api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(currentRunId)}/cancel`, {method: 'POST'});
          if (status) status.textContent = '已请求停止。任务会在安全检查点结束。';
          await refreshAll();
        } catch (err) {
          if (status) status.textContent = `停止请求失败：${err.message}`;
        }
      }
      function showDiscardConfirm(run) {
        const status = document.getElementById('xtl-discard-status');
        if (!status) return;
        const label = run ? runLabel(run, runs.findIndex(item => item.run_id === run.run_id)) : '当前任务';
        status.innerHTML = `<span class="xtl-inline-confirm">确认抛弃“${esc(label)}”写入的译文？这只会清空本项目记忆库里的译文，不会修改原始 MOD 文件。 <button type="button" class="xtl-btn danger" id="xtl-discard-confirm-ok">确认抛弃</button> <button type="button" class="xtl-btn" id="xtl-discard-confirm-cancel">取消</button></span>`;
      }
      function hideDiscardConfirm(message = '') {
        const status = document.getElementById('xtl-discard-status');
        if (status) status.textContent = message;
      }
      async function discardRunTranslations() {
        const run = currentRun();
        if (!project || !currentRunId) {
          hideDiscardConfirm('先选择一次历史任务。');
          return;
        }
        if (!run || run.status === 'running' || run.status === 'queued') {
          hideDiscardConfirm('这个任务还在运行或等待确认，请先停止任务。');
          updateDiscardState(run);
          return;
        }
        showDiscardConfirm(run);
      }
      async function confirmDiscardRunTranslations() {
        const status = document.getElementById('xtl-discard-status');
        const run = currentRun();
        if (!run || run.status === 'running' || run.status === 'queued') {
          hideDiscardConfirm('这个任务还在运行或等待确认，请先停止任务。');
          updateDiscardState(run);
          return;
        }
        const button = document.getElementById('xtl-discard-run-translations');
        if (button) button.disabled = true;
        if (status) status.textContent = '正在抛弃这次运行写入的译文...';
        try {
          const response = await api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(currentRunId)}/discard-translations`, {method: 'POST'});
          hideDiscardConfirm(response.message || `已抛弃 ${response.discarded_count || 0} 条译文。`);
          await refreshAll();
        } catch (err) {
          if (status) status.textContent = `抛弃失败：${err.message}`;
        } finally {
          updateDiscardState(currentRun());
        }
      }
      document.addEventListener('change', (event) => {
        if (event.target && event.target.id === 'xtl-run-select') {
          userSelectedRun = true;
          currentRunId = event.target.value || '';
          sinceEventId = 0;
          runSelectInteracting = false;
          hideDiscardConfirm('');
          refreshAll({force: true});
        }
      });
      document.addEventListener('focusin', (event) => {
        if (event.target && event.target.id === 'xtl-run-select') pauseAutoRefreshForRunSelect();
      });
      document.addEventListener('pointerdown', (event) => {
        if (event.target && event.target.id === 'xtl-run-select') pauseAutoRefreshForRunSelect();
      });
      document.addEventListener('focusout', (event) => {
        if (event.target && event.target.id === 'xtl-run-select') window.setTimeout(resumeAutoRefreshForRunSelect, 100);
      });
      document.addEventListener('click', (event) => {
        if (event.target && event.target.id === 'xtl-refresh-batches') refreshAll({force: true});
        if (event.target && event.target.id === 'xtl-cancel-run') cancelRun();
        if (event.target && event.target.id === 'xtl-discard-run-translations') discardRunTranslations();
        if (event.target && event.target.id === 'xtl-discard-confirm-ok') confirmDiscardRunTranslations();
        if (event.target && event.target.id === 'xtl-discard-confirm-cancel') hideDiscardConfirm('已取消抛弃。');
      });
      const ws = new WebSocket(`ws://${location.host}/ws`);
      ws.onopen = () => {
        metrics.wsState = 'open';
        metrics.wsOpenedAt = performance.now();
      };
      ws.onclose = () => {
        metrics.wsState = 'closed';
        metrics.wsClosedAt = performance.now();
      };
      ws.onerror = () => {
        metrics.wsState = 'error';
        metrics.wsErroredAt = performance.now();
      };
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        const actual = msg && msg.kind === 'event' && msg.event ? msg.event : msg;
        pushMetric('wsMessages', {
          at: performance.now(),
          kind: actual.kind || '',
          runId: actual.run_id || '',
          eventId: actual.event_id || null,
        });
        if (actual.event_id || actual.run_id) {
          applyRealtimeEvent(actual);
          scheduleRealtimeRefresh();
        }
      };
      refreshAll({preferActive: true});
      window.setInterval(refreshActiveRunIfNeeded, 5000);
    })();
    </script>
    """
    return script.replace("__PROJECT__", project_json)


def _entries_script(project: str | None) -> str:
    project_json = _json_for_script(project or "")
    script = """
    <script>
    (() => {
      const project = __PROJECT__;
      let entries = [];
      let selected = null;
      let checkedRows = new Set();
      let lastSelectionAnchorRowId = '';
      let savedDest = '';
      let savedStatus = 'untranslated';
      let searchTimer = null;
      const statusLabels = {
        untranslated: '未翻译',
        translated: '已翻译',
        partial: '需复查',
        locked: '锁定',
      };
      const signatureLabels = {
        MESG: '菜单/消息',
        INFO: '对话/信息',
        QUST: '任务',
        BOOK: '书籍/说明',
        CELL: '地点/区域',
      };
      const fieldLabels = {
        FULL: '名称',
        DESC: '说明',
      };
      const byId = id => document.getElementById(id);
      const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      function api(path, options = {}) {
        return fetch(path, {credentials: 'same-origin', ...options}).then(async res => {
          if (!res.ok) {
            let detail = `${path} -> ${res.status}`;
            try {
              const data = await res.json();
              detail = typeof data.detail === 'string' ? data.detail : (data.detail?.message || detail);
            } catch {}
            throw new Error(detail);
          }
          return res.json();
        });
      }
      function entryUrl() {
        const params = new URLSearchParams();
        const sig = byId('xtl-entries-sig')?.value || '';
        const field = byId('xtl-entries-field')?.value || '';
        const status = byId('xtl-entries-status')?.value || '';
        const search = byId('xtl-entries-search')?.value || '';
        if (sig) params.set('sig', sig);
        if (field) params.set('field', field);
        if (status) params.set('status', status);
        if (search.trim()) params.set('search', search.trim());
        params.set('limit', '500');
        return `/api/projects/${encodeURIComponent(project)}/entries?${params}`;
      }
      function currentEntryFilters() {
        return {
          sig: byId('xtl-entries-sig')?.value || '',
          field: byId('xtl-entries-field')?.value || '',
          status: byId('xtl-entries-status')?.value || '',
          search: byId('xtl-entries-search')?.value || '',
        };
      }
      function setSaveStatus(text, tone = '') {
        const el = byId('xtl-entry-save-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function setQueueStatus(text, tone = '') {
        const el = byId('xtl-entries-queue-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help xtl-selection-status ${tone}`;
      }
      function selectableRowIds() {
        return entries.map(entry => entry.row_id);
      }
      function rowIdsForEntry(entry) {
        const ids = Array.isArray(entry?.member_row_ids) && entry.member_row_ids.length
          ? entry.member_row_ids
          : [entry?.row_id].filter(Boolean);
        return ids.map(String);
      }
      function selectedEntries() {
        const selected = new Set(checkedRows);
        return entries.filter(entry => selected.has(entry.row_id));
      }
      function selectedMemberRowIds() {
        return [...new Set(selectedEntries().flatMap(entry => rowIdsForEntry(entry)))];
      }
      function queueableRowIds() {
        return entries.filter(entry => entry.status === 'untranslated').map(entry => entry.row_id);
      }
      function updateSelectionStatus(tone = '') {
        const total = selectableRowIds().length;
        const selectable = new Set(selectableRowIds());
        const queueable = new Set(queueableRowIds());
        const selectedVisible = [...checkedRows].filter(rowId => selectable.has(rowId));
        const selectedCount = selectedVisible.length;
        const selectedRecords = selectedMemberRowIds().length;
        const selectedQueueable = selectedVisible.filter(rowId => queueable.has(rowId)).length;
        const suffix = total
          ? `按住 Shift 点击复选框可以连续选择一段；其中 ${selectedQueueable} 个显示组可提交到 AI 队列，覆盖 ${selectedRecords} 条真实记录。`
          : '当前列表没有可加入队列的未翻译条目。';
        setQueueStatus(`已选择 ${selectedCount} / 当前列表 ${total} 个显示组，覆盖 ${selectedRecords} 条记录。${suffix}`, tone);
      }
      function setRowChecked(rowId, checked) {
        if (!selectableRowIds().includes(rowId)) return;
        if (checked) checkedRows.add(rowId);
        if (!checked) checkedRows.delete(rowId);
      }
      function setSelectionRange(rowId, checked) {
        const ids = selectableRowIds();
        const currentIndex = ids.indexOf(rowId);
        const anchorIndex = ids.indexOf(lastSelectionAnchorRowId);
        if (currentIndex < 0) return;
        if (anchorIndex < 0) {
          setRowChecked(rowId, checked);
          return;
        }
        const start = Math.min(anchorIndex, currentIndex);
        const end = Math.max(anchorIndex, currentIndex);
        ids.slice(start, end + 1).forEach(id => setRowChecked(id, checked));
      }
      function selectAllVisibleRows() {
        selectableRowIds().forEach(rowId => checkedRows.add(rowId));
        lastSelectionAnchorRowId = selectableRowIds()[0] || '';
        renderTable();
        updateSelectionStatus('good');
      }
      function clearSelectedRows() {
        checkedRows.clear();
        lastSelectionAnchorRowId = '';
        renderTable();
        updateSelectionStatus();
      }
      function renderTable() {
        const body = document.querySelector('#xtl-entries-table tbody');
        if (!body) return;
        if (!entries.length) {
          body.innerHTML = '<tr><td colspan="5">没有匹配的条目。换个筛选条件试试。</td></tr>';
          updateSelectionStatus();
          return;
        }
        body.innerHTML = entries.map(entry => {
          const active = selected && selected.row_id === entry.row_id ? ' class="active"' : '';
          const sigLabel = signatureLabels[entry.signature] ? `${signatureLabels[entry.signature]}（${entry.signature}）` : entry.signature;
          const fieldLabel = fieldLabels[entry.field] ? `${fieldLabels[entry.field]}（${entry.field}）` : entry.field;
          const checked = checkedRows.has(entry.row_id) ? ' checked' : '';
          const meta = `类型：${sigLabel}；字段：${fieldLabel}；条目编号：${entry.edid || entry.row_id}`;
          const memberCount = Number(entry.member_count || 1);
          const groupText = memberCount > 1 ? `${entry.signature}:${entry.field} · ${memberCount} 处` : `${entry.signature}:${entry.field}`;
          const contextWarning = entry.cross_signature_field_count > 1 ? ' · 同原文存在其他类型/字段，未跨上下文折叠' : '';
          const contextSamples = Array.isArray(entry.sample_contexts)
            ? entry.sample_contexts.slice(0, 3).map(item => item.edid || item.formid || item.row_id).filter(Boolean).join('；')
            : '';
          const shortEdid = String(entry.edid || entry.sample_contexts?.[0]?.edid || entry.row_id || '').slice(0, 32);
          return `<tr${active} data-row-id="${esc(entry.row_id)}" data-marker="row-entries-${esc(entry.row_id)}">
            <td><input type="checkbox" class="xtl-entry-check" data-row-id="${esc(entry.row_id)}"${checked} title="勾选后可批量改状态；未翻译条目也可提交到 AI 队列"></td>
            <td title="${esc(meta)}"><span class="xtl-status-pill ${esc(entry.status)}">${esc(statusLabels[entry.status] || entry.status)}</span></td>
            <td title="${esc(`${meta}${contextWarning}${contextSamples ? `；示例：${contextSamples}` : ''}`)}"><b class="xtl-entry-sigline">${esc(groupText)}</b><div class="xtl-entry-edidline">${esc(shortEdid)}</div></td>
            <td title="${esc(meta)}">${esc(entry.source)}</td>
            <td title="${esc(meta)}">${esc(entry.dest || '')}</td>
          </tr>`;
        }).join('');
      }
      function renderEntryContext(entry) {
        const panel = byId('xtl-entry-context');
        if (!panel) return;
        if (!entry) {
          panel.textContent = '选择左侧条目后，这里会显示 EDID、Record Signature、字段、FormID 和重复条目数量。';
          return;
        }
        const samples = Array.isArray(entry.sample_contexts) ? entry.sample_contexts : [];
        const first = samples[0] || {};
        const memberCount = Number(entry.member_count || 1);
        const lines = [
          `<div><b>Record Signature</b><span>${esc(entry.signature || '')}:${esc(entry.field || '')}</span></div>`,
          `<div><b>EDID</b><span>${esc(entry.edid || first.edid || '无 EDID')}</span></div>`,
          `<div><b>FormID</b><span>${esc(first.formid || entry.formid || '未知')}</span></div>`,
          `<div><b>重复组</b><span>${memberCount > 1 ? `同一原文 + 同一 signature:field 共 ${memberCount} 条` : '单条记录'}</span></div>`,
        ];
        if (entry.cross_signature_field_count > 1) {
          lines.push(`<div><b>折叠规则</b><span>同原文存在其他 signature:field，已保持分开。</span></div>`);
        }
        if (samples.length > 1) {
          const sampleText = samples.slice(0, 5).map(item => item.edid || item.formid || item.row_id).filter(Boolean).join('；');
          lines.push(`<div><b>组内示例</b><span>${esc(sampleText)}</span></div>`);
        }
        panel.innerHTML = lines.join('');
      }
      function renderDetail(entry) {
        selected = entry;
        savedDest = entry ? (entry.dest || '') : '';
        savedStatus = entry ? (entry.status || 'untranslated') : 'untranslated';
        if (byId('xtl-entry-id')) byId('xtl-entry-id').textContent = entry ? entry.row_id : '未选择';
        renderEntryContext(entry);
        if (byId('xtl-entry-source')) byId('xtl-entry-source').value = entry ? entry.source || '' : '';
        if (byId('xtl-entry-dest')) byId('xtl-entry-dest').value = savedDest;
        if (byId('xtl-entry-status')) byId('xtl-entry-status').value = savedStatus;
        setSaveStatus(entry ? '可以保存当前条目的手动修正。' : '选择左侧条目后可以保存。');
        renderTable();
      }
      async function loadEntries({keepSelection = false} = {}) {
        if (!project) return;
        entries = await api(entryUrl());
        const visibleIds = new Set(entries.map(entry => entry.row_id));
        checkedRows = new Set([...checkedRows].filter(rowId => visibleIds.has(rowId)));
        if (!visibleIds.has(lastSelectionAnchorRowId)) lastSelectionAnchorRowId = '';
        let next = null;
        if (keepSelection && selected) next = entries.find(entry => entry.row_id === selected.row_id) || null;
        renderTable();
        renderDetail(next || entries[0] || null);
        updateSelectionStatus();
      }
      async function selectRow(rowId) {
        const local = entries.find(entry => entry.row_id === rowId);
        if (local) {
          renderDetail(local);
          return;
        }
        const entry = await api(`/api/projects/${encodeURIComponent(project)}/entries/${encodeURIComponent(rowId)}`);
        renderDetail(entry);
      }
      async function saveEntry({dest, status, reason}) {
        if (!selected) {
          setSaveStatus('先选择一个条目。', 'danger');
          return;
        }
        const response = await api(`/api/projects/${encodeURIComponent(project)}/entries/${encodeURIComponent(selected.row_id)}`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({dest, status, reason}),
        });
        const updated = response.entry;
        selected = updated;
        const index = entries.findIndex(entry => entry.row_id === updated.row_id);
        if (index >= 0) entries[index] = updated;
        renderDetail(updated);
        setSaveStatus('已保存到本项目记忆库，并写入手动编辑记录。', 'good');
      }
      function showQuickTranslateConfirm() {
        if (!selected) {
          setSaveStatus('先选择一个条目。', 'danger');
          return;
        }
        const panel = byId('xtl-entry-quick-confirm');
        if (panel) {
          panel.hidden = false;
          panel.dataset.rowId = selected.row_id;
        }
        setSaveStatus('请在下方确认是否调用当前 AI 账号快速翻译。');
      }
      function hideQuickTranslateConfirm() {
        const panel = byId('xtl-entry-quick-confirm');
        if (panel) {
          panel.hidden = true;
          panel.dataset.rowId = '';
        }
      }
      async function quickTranslateEntry(rowId = '') {
        const targetRowId = rowId || (selected ? selected.row_id : '');
        if (!targetRowId) {
          setSaveStatus('先选择一个条目。', 'danger');
          return;
        }
        hideQuickTranslateConfirm();
        const button = byId('xtl-entry-quick-translate');
        if (button) button.disabled = true;
        setSaveStatus('正在使用当前 AI 账号快速翻译当前条目...', '');
        try {
          const response = await api(`/api/projects/${encodeURIComponent(project)}/entries/${encodeURIComponent(targetRowId)}/quick-translate`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({apply: true}),
          });
          const updated = response.entry;
          selected = updated;
          const index = entries.findIndex(entry => entry.row_id === updated.row_id);
          if (index >= 0) entries[index] = updated;
          renderDetail(updated);
          await loadEntries({keepSelection: true});
          const validation = response.validation && response.validation.failures && response.validation.failures.length ? ' 已标记为需复查。' : '';
          const updatedCount = Number(response.updated_count || 1);
          const fanout = updatedCount > 1 ? ` 同一类型/字段的 ${updatedCount} 条重复文本已同步写入。` : '';
          setSaveStatus(`快速翻译已写入本项目记忆库：${response.profile || '当前账号'}。${fanout}${validation}`, response.validation && response.validation.failures && response.validation.failures.length ? '' : 'good');
        } catch (error) {
          setSaveStatus(`快速翻译失败：${error.message || error} 请到“账号”页检查 API Key、模型和余额，或稍后重试。`, 'danger');
        } finally {
          if (button) button.disabled = false;
        }
      }
      async function submitBatchQueue() {
        const rowIds = selectedMemberRowIds();
        if (!rowIds.length) {
          setQueueStatus('请先在左侧列表勾选至少一个条目。提交队列只会接收其中未翻译、适合交给 AI 的条目。', 'danger');
          return;
        }
        const batchSize = Math.max(1, Math.min(500, Number(byId('xtl-entries-batch-size')?.value || 100)));
        const button = byId('xtl-entries-submit-queue');
        if (button) button.disabled = true;
        setQueueStatus('正在写入批量队列请求...', '');
        try {
          const response = await api(`/api/projects/${encodeURIComponent(project)}/batch-queue`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({row_ids: rowIds, batch_size: batchSize}),
          });
          checkedRows.clear();
          lastSelectionAnchorRowId = '';
          renderTable();
          const skipped = response.skipped_count ? `，跳过 ${response.skipped_count} 个非未翻译条目` : '';
          const llmSkipped = response.llm_skipped_count ? `；其中 ${response.llm_skipped_count} 条只有占位符/数字等内容，不会交给 AI` : '';
          const tech = byId('xtl-entries-queue-tech');
          const command = byId('xtl-entries-queue-command');
          if (tech && command) {
            command.textContent = response.command || '';
            tech.hidden = !response.command;
          }
          const groupSummary = response.group_count === 1
            ? `预计 1 组，实际 ${response.last_group_size || response.queued_count} 个独特文本`
            : `预计 ${response.group_count} 组，每组最多 ${response.batch_size} 个独特文本，最后一组 ${response.last_group_size} 个`;
          const covered = response.covered_count && response.covered_count !== response.queued_count
            ? `，覆盖 ${response.covered_count} 条真实记录`
            : '';
          setQueueStatus(`已加入待翻译清单 ${response.queued_count} 个独特文本${covered}，${groupSummary}${skipped}${llmSkipped}，还没有调用 AI。下一步请让翻译助手生成提示词；如果开启了预览，你会先在“提示词”页确认后才会开始批量翻译。`, 'good');
        } catch (error) {
          setQueueStatus(`提交失败：${error.message || error}`, 'danger');
        } finally {
          if (button) button.disabled = false;
        }
      }
      async function submitAllMatchingBatchQueue() {
        const batchSize = Math.max(1, Math.min(500, Number(byId('xtl-entries-batch-size')?.value || 100)));
        const button = byId('xtl-entries-submit-all-queue');
        if (button) button.disabled = true;
        setQueueStatus('疯狂模式正在按当前筛选收集所有可翻译条目...', '');
        try {
          const response = await api(`/api/projects/${encodeURIComponent(project)}/batch-queue/all`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({...currentEntryFilters(), batch_size: batchSize}),
          });
          const skipped = response.skipped_count ? `，跳过 ${response.skipped_count} 个非未翻译条目` : '';
          const llmSkipped = response.llm_skipped_count ? `；其中 ${response.llm_skipped_count} 条只有占位符/数字等内容，不会交给 AI` : '';
          const tech = byId('xtl-entries-queue-tech');
          const command = byId('xtl-entries-queue-command');
          if (tech && command) {
            command.textContent = response.command || '';
            tech.hidden = !response.command;
          }
          const covered = response.covered_count && response.covered_count !== response.queued_count
            ? `，覆盖 ${response.covered_count} 条真实记录`
            : '';
          setQueueStatus(`疯狂模式已提交当前筛选命中的 ${response.matched_count || response.covered_count || 0} 条记录：实际 ${response.queued_count} 个独特文本${covered}，每组最多 ${response.batch_size} 个，预计 ${response.group_count} 组${skipped}${llmSkipped}。下一步请让翻译助手生成提示词并预览。`, 'good');
        } catch (error) {
          setQueueStatus(`疯狂模式提交失败：${error.message || error}`, 'danger');
        } finally {
          if (button) button.disabled = false;
        }
      }
      async function bulkUpdateStatus(newStatus) {
        const rowIds = selectedMemberRowIds();
        if (!rowIds.length) {
          setQueueStatus('请先在左侧列表勾选至少一个条目。', 'danger');
          return;
        }
        const label = statusLabels[newStatus] || newStatus;
        const buttons = [
          byId('xtl-entries-bulk-translated'),
          byId('xtl-entries-bulk-untranslated'),
        ].filter(Boolean);
        buttons.forEach(button => { button.disabled = true; });
        setQueueStatus(`正在批量标记为${label}...`);
        try {
          const response = await api(`/api/projects/${encodeURIComponent(project)}/entries/bulk-status`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              row_ids: rowIds,
              status: newStatus,
              reason: `Web Entries tab bulk mark ${newStatus}`,
            }),
          });
          checkedRows.clear();
          lastSelectionAnchorRowId = '';
          await loadEntries({keepSelection: true});
          const skipped = response.skipped_count ? `，跳过 ${response.skipped_count} 条：${(response.skipped || []).slice(0, 3).map(item => item.reason).join('；')}` : '';
          setQueueStatus(`已批量标记 ${response.updated_count || 0} 条为${label}${skipped}。`, response.updated_count ? 'good' : 'danger');
        } catch (error) {
          setQueueStatus(`批量标记失败：${error.message || error}`, 'danger');
        } finally {
          buttons.forEach(button => { button.disabled = false; });
        }
      }
      document.addEventListener('click', event => {
        if (event.target && event.target.classList && event.target.classList.contains('xtl-entry-check')) {
          const rowId = event.target.getAttribute('data-row-id');
          if (rowId && event.shiftKey) {
            setSelectionRange(rowId, event.target.checked);
            renderTable();
          } else if (rowId) {
            setRowChecked(rowId, event.target.checked);
          }
          if (rowId) lastSelectionAnchorRowId = rowId;
          updateSelectionStatus();
          event.stopPropagation();
          return;
        }
        const row = event.target && event.target.closest ? event.target.closest('#xtl-entries-table tbody tr[data-row-id]') : null;
        if (row) selectRow(row.getAttribute('data-row-id'));
        if (event.target && event.target.id === 'xtl-entries-select-all') {
          selectAllVisibleRows();
        }
        if (event.target && event.target.id === 'xtl-entries-clear-selection') {
          clearSelectedRows();
        }
        if (event.target && event.target.id === 'xtl-entries-submit-queue') {
          submitBatchQueue();
        }
        if (event.target && event.target.id === 'xtl-entries-submit-all-queue') {
          submitAllMatchingBatchQueue();
        }
        if (event.target && event.target.id === 'xtl-entries-bulk-translated') {
          bulkUpdateStatus('translated');
        }
        if (event.target && event.target.id === 'xtl-entries-bulk-untranslated') {
          bulkUpdateStatus('untranslated');
        }
        if (event.target && event.target.id === 'xtl-entry-save') {
          saveEntry({
            dest: byId('xtl-entry-dest')?.value || '',
            status: byId('xtl-entry-status')?.value || 'translated',
            reason: 'Web Entries tab edit',
          });
        }
        if (event.target && event.target.id === 'xtl-entry-restore') {
          if (byId('xtl-entry-dest')) byId('xtl-entry-dest').value = savedDest;
          if (byId('xtl-entry-status')) byId('xtl-entry-status').value = savedStatus;
          setSaveStatus('已恢复为当前保存的译文，还没有再次写入。');
        }
        if (event.target && event.target.id === 'xtl-entry-quick-translate') {
          showQuickTranslateConfirm();
        }
        if (event.target && event.target.id === 'xtl-entry-quick-confirm-ok') {
          const panel = byId('xtl-entry-quick-confirm');
          quickTranslateEntry(panel?.dataset?.rowId || '');
        }
        if (event.target && event.target.id === 'xtl-entry-quick-confirm-cancel') {
          hideQuickTranslateConfirm();
          setSaveStatus('已取消快速翻译，没有调用 AI。');
        }
        if (event.target && event.target.id === 'xtl-entry-lock' && selected) {
          if (!window.confirm('这会让该文本保持原文，并标记为不需要翻译。不会修改原始 MOD 文件。确定吗？')) return;
          saveEntry({dest: selected.source || '', status: 'locked', reason: 'Web Entries tab lock original text'});
        }
        if (event.target && event.target.id === 'xtl-entry-clear') {
          if (!window.confirm('这会清空当前译文，但不会修改原始 MOD 文件。确定吗？')) return;
          saveEntry({dest: null, status: 'untranslated', reason: 'Web Entries tab clear translation'});
        }
      });
      document.addEventListener('change', event => {
        if (event.target && ['xtl-entries-sig', 'xtl-entries-field', 'xtl-entries-status'].includes(event.target.id)) {
          loadEntries();
        }
      });
      document.addEventListener('input', event => {
        if (event.target && event.target.id === 'xtl-entries-search') {
          window.clearTimeout(searchTimer);
          searchTimer = window.setTimeout(() => loadEntries(), 220);
        }
      });
      loadEntries();
    })();
    </script>
    """
    return script.replace("__PROJECT__", project_json)


def _theme_file(name: str) -> str:
    return (Path(__file__).parent / "themes" / name).read_text(encoding="utf-8")


def _bulk_update_entries_status(
    project: str,
    row_ids: list[str],
    status_value: str,
    *,
    reason: str,
) -> dict[str, Any]:
    from bgs_translator.cli.edit import _append_audit, _apply_edit, _get_unit

    selected_ids = list(dict.fromkeys(item.strip() for item in row_ids if isinstance(item, str) and item.strip()))
    if not selected_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先勾选至少一个条目。")
    if len(selected_ids) > 500:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "一次最多批量修改 500 个条目。")
    new_status = status_value.strip().lower()
    allowed_statuses = {"untranslated", "translated", "partial", "locked"}
    if new_status not in allowed_statuses:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"status must be one of {sorted(allowed_statuses)}")

    project_root = paths.project_root(project)
    conn = open_memory_db(project_root)
    updated: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    try:
        for row_id in selected_ids:
            before = _get_unit(conn, row_id)
            if before is None:
                skipped.append({"row_id": row_id, "reason": "条目已经不存在"})
                continue
            source = str(before.get("source") or "")
            current_dest = before.get("dest")
            if new_status == "untranslated":
                next_dest = None
            elif new_status == "locked":
                next_dest = str(current_dest or source)
            else:
                next_dest = str(current_dest or "").strip()
                if not next_dest:
                    skipped.append({"row_id": row_id, "reason": "没有译文，不能标记为已翻译或需复查"})
                    continue
            conn.execute("BEGIN")
            after = _apply_edit(conn, row_id, dest=next_dest, status=new_status)
            conn.commit()
            _append_audit(project_root, row_id=row_id, before=before, after=after, reason=reason, operation="bulk-status")
            updated.append(after)
    except sqlite3.Error as exc:
        conn.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    finally:
        conn.close()

    return {
        "ok": True,
        "project": project,
        "status": new_status,
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "entries": updated,
    }


def _create_batch_queue(
    project: str,
    row_ids: list[str],
    *,
    batch_size: int | None = None,
    max_selected: int | None = 500,
) -> dict[str, Any]:
    selected_ids = list(dict.fromkeys(item.strip() for item in row_ids if isinstance(item, str) and item.strip()))
    if not selected_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先勾选至少一个条目。")
    if max_selected is not None and len(selected_ids) > max_selected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"一次最多提交 {max_selected} 个条目到批量队列。")
    normalized_batch_size = int(batch_size or 100)
    if normalized_batch_size < 1 or normalized_batch_size > 500:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "每组条数必须在 1 到 500 之间。")

    project_root = paths.project_root(project)
    data = _project_toml_data(project_root)
    raw_project_block = data.get("project")
    project_block: dict[str, Any] = raw_project_block if isinstance(raw_project_block, dict) else {}
    target_lang = str(project_block.get("target_lang") or "zh-cn").strip() or "zh-cn"
    game = str(project_block.get("game") or "").strip()
    cfg = _load_profiles_for_api()
    profile_name = cfg.active or next(iter(cfg.profiles), "")

    conn = open_memory_db(project_root)
    try:
        placeholders = ",".join("?" for _ in selected_ids)
        rows = conn.execute(
            f"""
            SELECT row_id, plugin, formid, edid, signature, field, source, dest, status
            FROM units
            WHERE row_id IN ({placeholders})
            """,
            selected_ids,
        ).fetchall()
    finally:
        conn.close()
    row_order = {row_id: index for index, row_id in enumerate(selected_ids)}
    rows = sorted(rows, key=lambda row: row_order.get(str(row[0]), len(row_order)))
    found_ids = {str(row[0]) for row in rows}
    missing = [row_id for row_id in selected_ids if row_id not in found_ids]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"有 {len(missing)} 个勾选条目已经不存在，请刷新条目页。")
    untranslated = [row for row in rows if str(row[8]) == "untranslated"]
    if not untranslated:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "勾选的条目都不是“未翻译”状态，不会加入批量队列。")
    llm_skip_reasons = _queue_llm_skip_reasons(untranslated)
    llm_skipped_count = sum(llm_skip_reasons.values())
    translatable_rows = [row for row in untranslated if not _queue_row_skip_reason(row)]
    if not translatable_rows:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "勾选的未翻译条目都是占位符、数字或内部标识，不需要交给 AI 翻译。",
        )
    source_groups: dict[tuple[str, str, str], list[Any]] = {}
    source_group_order: list[tuple[str, str, str]] = []
    for row in translatable_rows:
        key = (str(row[6]), str(row[4]), str(row[5]))
        if key not in source_groups:
            source_groups[key] = []
            source_group_order.append(key)
        source_groups[key].append(row)
    grouped_rows = [source_groups[key][0] for key in source_group_order]
    source_group_payload = [
        {
            "representative_row_id": str(source_groups[key][0][0]),
            "member_row_ids": [str(row[0]) for row in source_groups[key]],
            "member_count": len(source_groups[key]),
            "source": str(source_groups[key][0][6]),
            "signature": str(source_groups[key][0][4]),
            "field": str(source_groups[key][0][5]),
            "sample_contexts": [
                {
                    "row_id": str(row[0]),
                    "plugin": str(row[1]),
                    "formid": f"0x{int(row[2]):08X}",
                    "edid": row[3],
                    "signature": str(row[4]),
                    "field": str(row[5]),
                }
                for row in source_groups[key][:8]
            ],
        }
        for key in source_group_order
    ]
    queued_ids = [str(row[0]) for row in grouped_rows]
    covered_ids = [str(row[0]) for row in translatable_rows]
    group_count = (len(queued_ids) + normalized_batch_size - 1) // normalized_batch_size
    last_group_size = len(queued_ids) % normalized_batch_size or normalized_batch_size
    queue_id = f"queue-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    queue_dir = project_root / "batches" / "selection-queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    command = _batch_queue_command(
        project=project,
        queue_id=queue_id,
        target_lang=target_lang,
        profile_name=profile_name,
        game=game,
        batch_size=normalized_batch_size,
    )
    payload = {
        "queue_id": queue_id,
        "project": project,
        "created_at": datetime.now(UTC).isoformat(),
        "row_ids": queued_ids,
        "covered_row_ids": covered_ids,
        "source_groups": source_group_payload,
        "batch_size": normalized_batch_size,
        "group_count": group_count,
        "last_group_size": last_group_size,
        "skipped_non_untranslated": [str(row[0]) for row in rows if str(row[8]) != "untranslated"],
        "llm_skipped_count": llm_skipped_count,
        "llm_skipped_reasons": llm_skip_reasons,
        "target_lang": target_lang,
        "game": game,
        "profile": profile_name,
        "recommended_cli": command,
        "note": "GUI 只记录玩家勾选的条目。下一步仍需翻译助手生成提示词，并按设置交由你预览审批。",
        "entries": [
            {
                "row_id": str(row[0]),
                "plugin": str(row[1]),
                "formid": f"0x{int(row[2]):08X}",
                "edid": row[3],
                "signature": str(row[4]),
                "field": str(row[5]),
                "source": str(row[6]),
                "status": str(row[8]),
                "member_count": len(source_groups[(str(row[6]), str(row[4]), str(row[5]))]),
            }
            for row in grouped_rows[:50]
        ],
    }
    queue_path = queue_dir / f"{queue_id}.json"
    queue_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "queue_id": queue_id,
        "queue_path": str(queue_path),
        "queued_count": len(queued_ids),
        "covered_count": len(covered_ids),
        "batch_size": normalized_batch_size,
        "group_count": group_count,
        "last_group_size": last_group_size,
        "skipped_count": len(rows) - len(untranslated),
        "llm_skipped_count": llm_skipped_count,
        "llm_skipped_reasons": llm_skip_reasons,
        "command": command,
        "message": "已把勾选条目加入待翻译清单。下一步请让翻译助手生成提示词，并等待你预览确认。",
    }


def _queue_llm_skip_reasons(rows: list[Any]) -> dict[str, int]:
    reasons: Counter[str] = Counter()
    for row in rows:
        if reason := _queue_row_skip_reason(row):
            reasons[reason] += 1
    return dict(sorted(reasons.items()))


def _queue_row_skip_reason(row: Any) -> str:
    return _masked_skip_reason(
        plugin=str(row[1]),
        formid=int(row[2]),
        formid_sanitized=int(row[2]),
        edid=str(row[3] or ""),
        signature=str(row[4]),
        field=str(row[5]),
        source=str(row[6] or ""),
    )


def _batch_queue_command(
    *,
    project: str,
    queue_id: str,
    target_lang: str,
    profile_name: str,
    game: str,
    batch_size: int,
) -> str:
    parts = [
        "xtl",
        "batch",
        "plan",
        project,
        "--queue",
        queue_id,
        "--register",
        "ui_label",
        "--target-lang",
        target_lang,
        "--batch-size",
        str(batch_size),
    ]
    if profile_name:
        parts.extend(["--profile", profile_name])
    if game:
        parts.extend(["--game-lore-world", game, "--mod-name", project])
    return " ".join(_quote_cli_part(part) for part in parts)


def _quote_cli_part(part: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=@+-]+", part):
        return part
    return "'" + part.replace("'", "''") + "'"


async def _quick_translate_entry(project: str, row_id: str) -> dict[str, Any]:
    from bgs_translator.cli.edit import _append_audit, _get_unit
    from bgs_translator.pipeline.batcher import Batch
    from bgs_translator.pipeline.clients.base import build_client_for
    from bgs_translator.pipeline.mask import build_masked_unit, unmask_dest
    from bgs_translator.pipeline.validator import validate_item

    cfg = _load_profiles_for_api()
    profile = get_active_profile(cfg)
    project_root = paths.project_root(project)
    project_data = _project_toml_data(project_root)
    raw_project_block = project_data.get("project")
    project_block: dict[str, Any] = raw_project_block if isinstance(raw_project_block, dict) else {}
    game = str(project_block.get("game") or "Bethesda Game Studios").strip() or "Bethesda Game Studios"
    target_lang = str(project_block.get("target_lang") or "zh-cn").strip() or "zh-cn"
    source_plugin = str(project_block.get("source_plugin_path") or "").strip()
    mod_name = Path(source_plugin).stem if source_plugin else project

    conn = open_memory_db(project_root)
    try:
        before = _get_unit(conn, row_id)
        if before is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"entry not found: {row_id}")
        unit = _translation_unit_from_entry(before)
        masked = build_masked_unit(unit)
        if masked.skip_llm:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"这条文本不适合交给 AI 快速翻译：{masked.skip_reason}")
        batch_id = f"quick-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{row_id[:8]}"
        batch = Batch(
            batch_id=batch_id,
            items=[masked],
            parent_context_summary=None,
            glossary_subset=[],
            do_not_translate=[],
        )
        system_prompt = _quick_translate_prompt(game=game, mod_name=mod_name, target_lang=target_lang)
        response = await _quick_translate_with_profile(
            profile=profile,
            batch=batch,
            system_prompt=system_prompt,
            build_client_for=build_client_for,
        )
        dest_masked = _quick_translate_dest_from_response(response.items)
        if not dest_masked and profile.json_mode == "json_schema":
            fallback_profile = profile.model_copy(update={"json_mode": "json_object"})
            response = await _quick_translate_with_profile(
                profile=fallback_profile,
                batch=batch,
                system_prompt=system_prompt,
                build_client_for=build_client_for,
            )
            dest_masked = _quick_translate_dest_from_response(response.items)
        validation = validate_item(masked, dest_masked, [], ["utf-8"])
        dest = unmask_dest(dest_masked, masked.mask_map, masked.mcm_token_prefix)
        if not dest.strip():
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 返回了空译文，已取消写入。请稍后重试。")
        if not validation.ok:
            reasons = "；".join(failure.reason for failure in validation.failures) or "校验未通过"
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"AI 返回内容未通过校验，已取消写入：{reasons}")
        new_status = "translated" if not validation.failures else "partial"
        group_row_ids = _entry_translation_group_row_ids(conn, before)
        if row_id not in group_row_ids:
            group_row_ids.insert(0, row_id)
        before_by_row_id = {
            target_row_id: _get_unit(conn, target_row_id)
            for target_row_id in group_row_ids
        }
        item_cost = None
        if response.cost_usd is not None and group_row_ids:
            item_cost = response.cost_usd / max(1, len(group_row_ids))
        for target_row_id in group_row_ids:
            update_unit_translation(
                conn,
                row_id=target_row_id,
                dest=dest,
                status=new_status,
                sparams=_sparams_for_entry_status(new_status),
                via_llm=True,
                profile_used=profile.name,
                sdk_via=response.via,
                cost_estimate_usd=item_cost,
                cost_exact=response.cost_exact,
                retry_count=0,
                last_batch_id=batch_id,
            )
        after = _get_unit(conn, row_id)
        if after is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"entry disappeared: {row_id}")
        for target_row_id in group_row_ids:
            target_after = _get_unit(conn, target_row_id)
            target_before = before_by_row_id.get(target_row_id)
            if target_before is not None and target_after is not None:
                _append_audit(
                    project_root,
                    row_id=target_row_id,
                    before=target_before,
                    after=target_after,
                    reason=f"Web Entries quick translate safe duplicate group via {profile.name}",
                    operation="quick-translate",
                )
    finally:
        conn.close()

    return {
        "ok": True,
        "entry": after,
        "updated_count": len(group_row_ids),
        "member_row_ids": group_row_ids,
        "profile": profile.name,
        "model": profile.model,
        "batch_id": batch_id,
        "cost_usd": response.cost_usd,
        "cost_exact": response.cost_exact,
        "request_id": response.request_id,
        "validation": {
            "ok": validation.ok,
            "failures": [failure.model_dump(mode="json") for failure in validation.failures],
        },
    }


async def _quick_translate_with_profile(
    *,
    profile: ProviderProfile,
    batch: Any,
    system_prompt: str,
    build_client_for: Callable[[ProviderProfile], Any],
) -> Any:
    client = build_client_for(profile)
    try:
        return await client.translate_batch(batch, system_prompt)
    finally:
        await client.aclose()


def _quick_translate_dest_from_response(items: dict[str, str]) -> str:
    dest_masked = items.get("I1", "")
    if not dest_masked and len(items) == 1:
        dest_masked = next(iter(items.values()))
    return dest_masked


def _entry_translation_group_row_ids(conn: sqlite3.Connection, entry: dict[str, Any]) -> list[str]:
    rows = conn.execute(
        """
        SELECT row_id FROM units
        WHERE source = ? AND signature = ? AND field = ?
          AND status IN ('untranslated', 'partial')
        ORDER BY signature, field, formid, index_n
        """,
        (entry.get("source") or "", entry.get("signature") or "", entry.get("field") or ""),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _translation_unit_from_entry(entry: dict[str, Any]) -> Any:
    from bgs_translator.parsers.tes4_family import TranslationUnit

    return TranslationUnit(
        plugin=str(entry["plugin"]),
        formid=int(str(entry["formid"]), 16),
        formid_sanitized=int(str(entry["formid_sanitized"]), 16),
        edid=entry.get("edid"),
        signature=str(entry["signature"]),
        field=str(entry["field"]),
        source=str(entry["source"]),
        index_n=int(entry.get("index") or 0),
        index_max=int(entry.get("index_max") or 0),
        list_index=int(entry.get("list_index") or 0),
        strid=int(entry.get("strid") or 0),
    )


def _quick_translate_prompt(*, game: str, mod_name: str, target_lang: str) -> str:
    language = "简体中文" if target_lang.casefold() in {"zh-cn", "zhhans", "zh-hans"} else target_lang
    return (
        f"你正在翻译 {game} 的 MOD「{mod_name}」。\n"
        f"把提供的英文文本翻译成{language}，面向普通玩家，表达自然、简洁。\n"
        "保持所有占位符、变量、换行、尖括号标签、{{P0}} 这类标记完全不变。\n"
        "必须翻译并返回用户消息里的每个编号，例如 I1；不要省略任何条目。\n"
        "不要添加解释，不要补充原文没有的信息。只返回要求的 JSON 对象。"
    )


def _sparams_for_entry_status(status_value: str) -> int:
    from bgs_translator.sst.status import SStrParam

    mapping = {
        "translated": SStrParam.TRANSLATED,
        "partial": SStrParam.INCOMPLETE_TRANS,
        "locked": SStrParam.LOCKED_TRANS,
        "untranslated": SStrParam.NONE,
    }
    return int(mapping.get(status_value, SStrParam.NONE))


def _import_project_from_plugin(payload: ProjectImportRequest) -> dict[str, Any]:
    project_name = payload.project_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}", project_name):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "项目名只能使用字母、数字、点、下划线和横线，长度 2-64。")

    plugin = Path(payload.plugin_path).expanduser()
    if plugin.suffix.casefold() not in {".esp", ".esm", ".esl"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择 .esp / .esm / .esl 文件。")
    if not plugin.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"找不到这个 MOD 文件：{plugin}")

    project_root = paths.project_root(project_name)
    if project_root.exists() and any(project_root.iterdir()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"项目 {project_name} 已存在，请换一个项目名。")

    header = _read_tes4_header_for_import(plugin)
    candidates = detect_game_from_header(header.form_version, header.masters)
    selected_game = payload.game.strip() if isinstance(payload.game, str) and payload.game.strip() else None
    if selected_game is None:
        if len(candidates) != 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                {
                    "code": "ambiguous_game",
                    "message": "无法只根据文件头判断这是哪个游戏的 MOD，请在导入框里选择游戏。",
                    "form_version": header.form_version,
                    "candidates": candidates,
                },
            )
        selected_game = candidates[0]

    try:
        schema = get_schema_for_game(selected_game)
    except KeyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"暂不支持这个游戏：{selected_game}") from exc

    strings_status = _localized_strings_status(
        plugin, header.is_localized, payload.source_lang, selected_game
    )
    if header.is_localized and not strings_status["found"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "code": "missing_strings",
                "message": "这个插件使用本地化 Strings 文件，但没有从同目录 Strings 或 BA2 archive 里解析到文本。请确认插件旁边有对应 archive，或在 MO2 中启用包含该插件文本的 MOD。",
                "strings": strings_status,
            },
        )

    created = False
    try:
        units = list(extract_translation_units(plugin, selected_game, schema=schema))
        if not units:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有从这个插件里抽取到可翻译文本。")
        for subdir in ["sources", "memory", "batches", "exports"]:
            (project_root / subdir).mkdir(parents=True, exist_ok=True)
        created = True
        plugin_sha = _sha256(plugin)
        _write_cache(project_root, plugin, units, plugin_sha, schema)
        conn = open_memory_db(project_root)
        try:
            inserted = insert_units(conn, units)
        finally:
            conn.close()
        _write_project_toml(
            project_root,
            name=project_name,
            plugin=plugin,
            plugin_sha=plugin_sha,
            game=selected_game,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
        )
    except Exception:
        if created and project_root.exists():
            shutil.rmtree(project_root)
        raise

    return {
        "ok": True,
        "project": project_name,
        "project_root": str(project_root),
        "game": selected_game,
        "detected_candidates": candidates,
        "form_version": header.form_version,
        "source_plugin_path": str(plugin),
        "plugin_type": plugin.suffix.upper().lstrip("."),
        "is_esl": header.is_esl,
        "is_localized": header.is_localized,
        "strings": strings_status,
        "units_extracted": inserted,
        "signature_distribution": dict(Counter(unit.signature for unit in units)),
    }


def _select_plugin_file(current_path: str = "") -> dict[str, Any]:
    initial_dir = _plugin_dialog_initial_dir(current_path)
    env = os.environ.copy()
    if initial_dir:
        env["XTL_FILE_DIALOG_INITIAL_DIR"] = str(initial_dir)
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '选择要导入的 MOD 文件'
$dialog.Filter = 'Bethesda MOD 文件 (*.esm;*.esp;*.esl)|*.esm;*.esp;*.esl|所有文件 (*.*)|*.*'
$dialog.CheckFileExists = $true
$dialog.Multiselect = $false
if ($env:XTL_FILE_DIALOG_INITIAL_DIR -and (Test-Path -LiteralPath $env:XTL_FILE_DIALOG_INITIAL_DIR)) {
  $dialog.InitialDirectory = $env:XTL_FILE_DIALOG_INITIAL_DIR
}
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
  [pscustomobject]@{ path = $dialog.FileName; canceled = $false } | ConvertTo-Json -Compress
} else {
  [pscustomobject]@{ path = ''; canceled = $true } | ConvertTo-Json -Compress
}
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=env,
        timeout=300,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Windows 文件选择器启动失败。"
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return {"path": "", "canceled": True}
    try:
        data = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Windows 文件选择器返回了无法读取的结果。") from exc
    path = str(data.get("path") or "")
    if path and Path(path).suffix.casefold() not in {".esp", ".esm", ".esl"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择 .esm、.esp 或 .esl 文件。")
    return {"path": path, "canceled": bool(data.get("canceled") or not path)}


def _plugin_dialog_initial_dir(current_path: str) -> Path | None:
    raw = current_path.strip()
    if raw:
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate.parent
        if candidate.is_dir():
            return candidate
    for candidate in (Path("D:/Starfield MO2/mods"), Path("D:/awesome-bgs-mod-master/.artifacts/bgs-mod-plugins")):
        if candidate.is_dir():
            return candidate
    return None


def _read_tes4_header_for_import(plugin: Path) -> TES4Header:
    walker = TES4FamilyWalker(plugin)
    next(walker.walk(), None)
    if walker.header is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "无法读取 TES4 文件头，请确认这是 Bethesda 插件文件。")
    return walker.header


def _localized_strings_status(
    plugin: Path, localized: bool, source_lang: str, game: str | None = None
) -> dict[str, Any]:
    slug = "english" if source_lang.casefold() == "en" else source_lang.casefold()
    found = find_strings_sources(plugin, slug, game=game)
    required = ["STRINGS", "DLSTRINGS", "ILSTRINGS"] if localized else []
    return {
        "localized": localized,
        "language_slug": slug,
        "found": {kind: str(source.path) for kind, source in found.items()},
        "archives": {
            kind: str(source.archive_path)
            for kind, source in found.items()
            if source.archive_path is not None
        },
        "missing": [kind for kind in required if kind not in found],
        "required": required,
    }


def _list_projects() -> list[dict[str, Any]]:
    root = paths.projects_root()
    return [
        {"name": item.name, "path": str(item)}
        for item in (sorted(root.iterdir()) if root.exists() else [])
        if item.is_dir() and ((item / "project.toml").exists() or (item / "memory" / "memory.sqlite").exists())
    ]


def _selected_project_name(candidate: str | None = None) -> str | None:
    projects = _list_projects()
    if not projects:
        return None
    names = {str(item["name"]) for item in projects}
    if candidate and candidate in names:
        return candidate
    return _default_project_name()


def _default_project_name() -> str | None:
    projects = _list_projects()
    if not projects:
        return None
    preferred = next((item for item in projects if item["name"] == "ryos-zhcn"), None)
    return str((preferred or projects[0])["name"])


def _page_href(page: str, project: str | None) -> str:
    path = "/" if page == "project-index" else f"/{quote(page.strip('/') or 'project')}"
    if not project:
        return path
    return f"{path}?{urlencode({'project': project})}"


def _project_summary(project: str | None) -> dict[str, Any]:
    if project is None:
        return {
            "game": "",
            "units_total": 0,
            "units_translated": 0,
            "units_pending_ai": 0,
            "source": _empty_source_details(),
            "signature_status": [],
        }
    project_root = paths.project_root(project)
    game = "Unknown"
    data = _project_toml_data(project_root)
    source = _project_source_details(project)
    if data:
        game = str((data.get("project") or {}).get("game") or game)
    memory_path = project_root / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return {
            "game": game,
            "units_total": 0,
            "units_translated": 0,
            "units_pending_ai": 0,
            "source": source,
            "signature_status": [],
        }
    conn = sqlite3.connect(memory_path)
    try:
        signature_status = _signature_status_rows(conn)
        return {
            "game": game,
            "units_total": sum(int(row.get("total") or 0) for row in signature_status),
            "units_translated": sum(int(row.get("translated") or 0) for row in signature_status),
            "units_pending_ai": sum(int(row.get("pending_ai") or 0) for row in signature_status),
            "source": source,
            "signature_status": signature_status,
        }
    finally:
        conn.close()


def _signature_status_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT plugin, formid, formid_sanitized, edid, signature, field, source, dest, status, sparams
        FROM units
        """
    ).fetchall()
    stats: dict[str, Counter[str]] = {}
    for row in rows:
        signature = str(row[4] or "")
        bucket = stats.setdefault(signature, Counter())
        status_value = _effective_unit_status(
            status=str(row[8] or ""),
            sparams=int(row[9] or 0),
            skip_reason=_translation_unit_skip_reason(row),
            signature=signature,
            field=str(row[5] or ""),
        )
        bucket["total"] += 1
        if status_value == "translated":
            bucket["translated"] += 1
        elif status_value == "locked":
            bucket["locked"] += 1
        elif status_value in {"partial", "manual_review", "failed"}:
            bucket["partial"] += 1
        elif status_value == "untranslated":
            bucket["pending_ai"] += 1
        else:
            bucket["other"] += 1
    return [
        {
            "signature": signature,
            "total": int(counter["total"]),
            "translated": int(counter["translated"]),
            "pending_ai": int(counter["pending_ai"]),
            "partial": int(counter["partial"]),
            "locked": int(counter["locked"]),
            "other": int(counter["other"]),
        }
        for signature, counter in sorted(stats.items(), key=lambda item: (-int(item[1]["total"]), item[0].casefold()))
        if int(counter["total"]) > 0
    ]


def _translation_unit_skip_reason(row: Any) -> str:
    return _masked_skip_reason(
        plugin=str(row[0]),
        formid=int(row[1]),
        formid_sanitized=int(row[2] if row[2] is not None else row[1]),
        edid=str(row[3] or ""),
        signature=str(row[4]),
        field=str(row[5]),
        source=str(row[6] or ""),
    )


def _entry_row_skip_reason(row: sqlite3.Row | dict[str, Any]) -> str:
    if isinstance(row, sqlite3.Row):
        return _masked_skip_reason(
            plugin=str(row["plugin"]),
            formid=int(row["formid"]),
            formid_sanitized=int(row["formid_sanitized"] if row["formid_sanitized"] is not None else row["formid"]),
            edid=str(row["edid"] or ""),
            signature=str(row["signature"]),
            field=str(row["field"]),
            source=str(row["source"] or ""),
        )
    return _masked_skip_reason(
        plugin=str(row.get("plugin") or ""),
        formid=int(row.get("formid") or 0),
        formid_sanitized=int(row.get("formid_sanitized") or row.get("formid") or 0),
        edid=str(row.get("edid") or ""),
        signature=str(row.get("signature") or ""),
        field=str(row.get("field") or ""),
        source=str(row.get("source") or ""),
    )


def _effective_unit_status(
    *,
    status: str,
    sparams: int = 0,
    skip_reason: str = "",
    signature: str = "",
    field: str = "",
) -> str:
    params = SStrParam(int(sparams or 0) & 0xFF)
    if SStrParam.LOCKED_TRANS in params:
        return "locked"
    if signature.strip().upper() == "TES4" and field.strip().upper() in {"CNAM", "SNAM"}:
        return "locked"
    if skip_reason:
        return "locked"
    if SStrParam.INCOMPLETE_TRANS in params:
        return "partial"
    if SStrParam.TRANSLATED in params:
        return "translated"
    if SStrParam.PENDING in params:
        return "untranslated"
    status_value = status.strip().lower()
    return status_value


def _masked_skip_reason(
    *,
    plugin: str,
    formid: int,
    formid_sanitized: int,
    edid: str,
    signature: str,
    field: str,
    source: str,
) -> str:
    from bgs_translator.parsers.tes4_family import TranslationUnit
    from bgs_translator.pipeline.mask import build_masked_unit

    unit = TranslationUnit(
        plugin=plugin,
        formid=formid,
        formid_sanitized=formid_sanitized,
        edid=edid,
        signature=signature,
        field=field,
        source=source,
    )
    masked = build_masked_unit(unit)
    return masked.skip_reason if masked.skip_llm else ""


def _signature_label(signature: str) -> str:
    return {
        "MESG": "菜单、提示消息、开始选项",
        "INFO": "对话、NPC 信息",
        "QUST": "任务名称或任务说明",
        "BOOK": "书籍、说明文本、终端内容",
        "CELL": "地点、区域名称",
        "WEAP": "武器名称或说明",
        "ARMO": "护甲、服装名称或说明",
        "NPC_": "角色名称",
        "FACT": "派系名称",
        "MISC": "杂项物品",
        "TERM": "终端菜单或终端文本",
    }.get(signature, "其它可翻译记录类型")


def _project_toml_data(project_root: Path) -> dict[str, Any]:
    project_toml = project_root / "project.toml"
    if not project_toml.exists():
        return {}
    try:
        return tomllib.loads(project_toml.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _empty_source_details() -> dict[str, Any]:
    return {
        "path": "",
        "plugin_name": "",
        "plugin_type": "",
        "exists": False,
        "size_bytes": 0,
        "modified_at": "",
        "source_lang": "",
        "target_lang": "",
        "parser_version": "",
        "stored_sha256": "",
        "actual_sha256": "",
        "sha_status": "unknown",
        "is_esl": None,
        "is_localized": None,
        "masters": [],
        "memory_plugins": [],
        "cache": {},
    }


def _project_source_details(project: str, *, verify_sha: bool = False) -> dict[str, Any]:
    project_root = paths.project_root(project)
    data = _project_toml_data(project_root)
    raw_project_block = data.get("project")
    project_block: dict[str, Any] = raw_project_block if isinstance(raw_project_block, dict) else {}
    source_path_text = str(project_block.get("source_plugin_path") or "")
    source_path = Path(source_path_text) if source_path_text else None
    stored_sha = str(project_block.get("source_plugin_sha256") or "")
    details = _empty_source_details()
    details.update(
        {
            "path": source_path_text,
            "plugin_name": source_path.name if source_path else "",
            "plugin_type": source_path.suffix.upper().lstrip(".") if source_path and source_path.suffix else "",
            "source_lang": str(project_block.get("source_lang") or ""),
            "target_lang": str(project_block.get("target_lang") or ""),
            "parser_version": str(project_block.get("parser_version") or ""),
            "stored_sha256": stored_sha,
            "memory_plugins": _memory_plugin_rows(project),
            "cache": _source_cache_details(project_root, source_path.name if source_path else ""),
        }
    )
    if not source_path:
        return details
    try:
        exists = source_path.exists()
    except OSError:
        exists = False
    details["exists"] = exists
    if not exists:
        return details
    try:
        stat = source_path.stat()
        details["size_bytes"] = stat.st_size
        details["modified_at"] = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
    except OSError:
        pass
    if verify_sha and stored_sha:
        actual_sha = _sha256_file(source_path)
        details["actual_sha256"] = actual_sha
        details["sha_status"] = "match" if actual_sha == stored_sha else "mismatch"
    elif stored_sha:
        details["sha_status"] = "not_checked"
    if verify_sha:
        details.update(_source_header_details(source_path))
    return details


def _memory_plugin_rows(project: str) -> list[dict[str, Any]]:
    memory_path = paths.project_root(project) / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return []
    conn = sqlite3.connect(memory_path)
    try:
        rows = conn.execute(
            "SELECT plugin, COUNT(*) AS count FROM units GROUP BY plugin ORDER BY plugin"
        ).fetchall()
    finally:
        conn.close()
    return [{"name": str(row[0] or ""), "count": int(row[1] or 0)} for row in rows]


def _source_cache_details(project_root: Path, plugin_name: str) -> dict[str, Any]:
    if not plugin_name:
        return {}
    cache_path = project_root / "sources" / f"{plugin_name}.cache.toml"
    if not cache_path.exists():
        return {}
    try:
        return tomllib.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _source_header_details(source_path: Path) -> dict[str, Any]:
    try:
        walker = TES4FamilyWalker(source_path)
        next(walker.walk(), None)
        header = walker.header
    except (OSError, ValueError):
        return {"is_esl": None, "is_localized": None, "masters": []}
    if header is None:
        return {"is_esl": None, "is_localized": None, "masters": []}
    return {"is_esl": header.is_esl, "is_localized": header.is_localized, "masters": header.masters}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_close_summary(project: str) -> dict[str, Any]:
    project_root = paths.project_root(project)
    latest_export = _latest_export_timestamp(project_root)
    memory_path = project_root / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return {
            "project": project,
            "in_flight_count": 0,
            "unsaved_manual_edits": 0,
            "latest_export": latest_export,
            "exports_dir": str(project_root / "exports"),
            "files": _export_file_rows(project),
        }
    conn = sqlite3.connect(memory_path)
    try:
        run_rows = [_sqlite_row_dict(row) for row in list_recent_runs(conn, limit=50)]
        annotated_runs = _annotate_run_rows(project, conn, run_rows)
        in_flight = len([row for row in annotated_runs if str(row.get("status") or "") in {"running", "queued"}])
        orphaned = len([row for row in annotated_runs if str(row.get("status") or "") == "orphaned"])
        cutoff = latest_export or ""
        unsaved = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM units
                WHERE via_llm = 0
                  AND dest IS NOT NULL
                  AND COALESCE(updated_at, '') > ?
                """,
                (cutoff,),
            ).fetchone()[0]
        )
    finally:
        conn.close()
    return {
        "project": project,
        "in_flight_count": in_flight,
        "orphaned_run_count": orphaned,
        "unsaved_manual_edits": unsaved,
        "latest_export": latest_export,
        "exports_dir": str(project_root / "exports"),
        "files": _export_file_rows(project),
    }


def _latest_export_timestamp(project_root: Path) -> str:
    exports = project_root / "exports"
    if not exports.exists():
        return ""
    latest = max((path.stat().st_mtime for path in exports.glob("*") if path.is_file()), default=None)
    if latest is None:
        return ""
    return datetime.fromtimestamp(latest, UTC).isoformat()


def _export_file_rows(project: str) -> list[dict[str, Any]]:
    exports = paths.project_root(project) / "exports"
    if not exports.exists():
        return []
    return [
        {
            "name": path.name,
            "path": str(path),
            "size": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        }
        for path in sorted((item for item in exports.iterdir() if item.is_file()), key=lambda item: item.name)
    ]


def _entry_rows(
    project: str | None,
    *,
    limit: int,
    sig: str | None = None,
    field: str | None = None,
    entry_status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    if project is None:
        return []
    memory_path = paths.project_root(project) / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return []
    conn = _open_project_db(project)
    try:
        derived_status_filter = entry_status if entry_status in {"locked", "untranslated", "partial", "translated"} else None
        rows = select_units_filtered(
            conn,
            sigs=[sig] if sig else None,
            fields=[field] if field else None,
            statuses=None if derived_status_filter else ([entry_status] if entry_status else None),
            search=search,
            limit=max(limit, min(limit * 5, 5000)),
        )
        visible: list[dict[str, Any]] = []
        for row in rows:
            item = _sqlite_row_dict(row)
            skip_reason = _entry_row_skip_reason(row)
            stored_status = str(item.get("status") or "")
            if skip_reason and stored_status != "locked":
                continue
            effective_status = _effective_unit_status(
                status=stored_status,
                sparams=int(item.get("sparams") or 0),
                skip_reason=skip_reason,
                signature=str(item.get("signature") or ""),
                field=str(item.get("field") or ""),
            )
            item["status"] = effective_status
            if effective_status == "locked":
                item["sparams"] = int(SStrParam.LOCKED_TRANS)
            elif effective_status == "partial":
                item["sparams"] = int(SStrParam.INCOMPLETE_TRANS)
            elif effective_status == "translated":
                item["sparams"] = int(SStrParam.TRANSLATED)
            else:
                item["sparams"] = int(item.get("sparams") or 0)
            if derived_status_filter and effective_status != derived_status_filter:
                continue
            visible.append(item)
        return _group_entry_rows(visible)[:limit]
    finally:
        conn.close()


def _filtered_entry_row_ids(
    project: str,
    *,
    sig: str | None = None,
    field: str | None = None,
    entry_status: str | None = None,
    search: str | None = None,
) -> list[str]:
    memory_path = paths.project_root(project) / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return []
    conn = _open_project_db(project)
    try:
        derived_status_filter = entry_status if entry_status in {"locked", "untranslated", "partial", "translated"} else None
        rows = select_units_filtered(
            conn,
            sigs=[sig] if sig else None,
            fields=[field] if field else None,
            statuses=None if derived_status_filter else ([entry_status] if entry_status else None),
            search=search,
            limit=None,
        )
        row_ids: list[str] = []
        for row in rows:
            item = _sqlite_row_dict(row)
            skip_reason = _entry_row_skip_reason(row)
            stored_status = str(item.get("status") or "")
            if skip_reason and stored_status != "locked":
                continue
            effective_status = _effective_unit_status(
                status=stored_status,
                sparams=int(item.get("sparams") or 0),
                skip_reason=skip_reason,
                signature=str(item.get("signature") or ""),
                field=str(item.get("field") or ""),
            )
            if derived_status_filter and effective_status != derived_status_filter:
                continue
            row_id = item.get("row_id")
            if row_id:
                row_ids.append(str(row_id))
        return row_ids
    finally:
        conn.close()


def _group_entry_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold duplicate source text only inside the same signature:field and status."""

    source_contexts: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        source = str(row.get("source") or "")
        signature = str(row.get("signature") or "")
        field = str(row.get("field") or "")
        source_contexts.setdefault(source, set()).add((signature, field))

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    order: list[tuple[str, str, str, str]] = []
    for row in rows:
        key = (
            str(row.get("source") or ""),
            str(row.get("signature") or ""),
            str(row.get("field") or ""),
            str(row.get("status") or ""),
        )
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)

    result: list[dict[str, Any]] = []
    for key in order:
        members = grouped[key]
        representative = dict(members[0])
        representative["member_row_ids"] = [str(member.get("row_id") or "") for member in members if member.get("row_id")]
        representative["member_count"] = len(representative["member_row_ids"])
        representative["is_source_group"] = len(members) > 1
        representative["group_key"] = _entry_group_key(representative)
        representative["cross_signature_field_count"] = len(source_contexts.get(str(representative.get("source") or ""), set()))
        representative["sample_contexts"] = [
            {
                "row_id": str(member.get("row_id") or ""),
                "edid": member.get("edid") or "",
                "signature": member.get("signature") or "",
                "field": member.get("field") or "",
                "formid": _entry_formid_display(member.get("formid")),
            }
            for member in members[:8]
        ]
        result.append(representative)
    return result


def _entry_group_key(row: dict[str, Any]) -> str:
    digest = hashlib.sha1()
    for key in ("source", "signature", "field", "status"):
        digest.update(str(row.get(key) or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _entry_formid_display(value: Any) -> str:
    try:
        return f"0x{int(value):08X}"
    except (TypeError, ValueError):
        text = str(value or "")
        return text if text.startswith("0x") else text


def _all_filter(value: str | None) -> bool:
    return value is None or value.strip() in {"", "全部", "All", "all", "*"}


def _short_display_id(value: object, *, width: int = 8) -> str:
    text = str(value or "")
    return text[:width] if text else ""


def _status_label(value: object) -> str:
    labels = {
        "running": "翻译中",
        "queued": "排队中",
        "orphaned": "未正常收尾",
        "complete": "已完成",
        "failed": "有问题",
        "cancelled": "已取消",
        "manual_review": "需人工复查",
        "partial": "部分完成",
    }
    text = str(value or "")
    return labels.get(text, text or "等待")


def _top_status(project: str | None) -> tuple[str, str]:
    if _pending_previews(project):
        return "等待你确认提示词", "warn"
    rows = _run_rows(project)
    running = [row for row in rows if str(row.get("status") or "") == "running"]
    if running:
        return f"有 {len(running)} 个任务运行中，已发送请求可能仍在服务商侧处理", "danger"
    orphaned = [row for row in rows if str(row.get("status") or "") == "orphaned"]
    if orphaned:
        return f"有 {len(orphaned)} 个历史任务未正常收尾，当前不会继续运行", "warn"
    abandoned = [row for row in rows if str(row.get("status") or "") in {"abandoned", "paused"}]
    if abandoned:
        return "有历史任务已中断，仅供审计", "warn"
    review = [row for row in rows if str(row.get("status") or "") in {"manual_review", "failed"}]
    if review:
        return "有任务需要处理", "danger"
    if any(str(row.get("status") or "") == "cancelled" for row in rows[:1]):
        return "最近任务已取消", "warn"
    if any(str(row.get("status") or "") == "complete" for row in rows[:1]):
        return "最近任务已完成", "good"
    return "没有运行中的任务", "good"


def _event_kind_label(value: str) -> str:
    labels = {
        "run.start": "开始翻译",
        "run.complete": "全部完成",
        "run.failed": "运行失败",
        "run.abandoned": "已中断，仅审计",
        "run.paused": "已中断，仅审计",
        "run.cancelled": "已取消",
        "batch.start": "批次开始",
        "batch.progress": "批次进度更新",
        "batch.request_sent": "已发送给模型",
        "batch.response_received": "模型已返回",
        "batch.complete": "批次完成",
        "batch.failed": "批次失败",
        "batch.abandoned": "已中断，仅审计",
        "batch.paused": "已中断，仅审计",
        "batch.waiting_preview": "已中断，仅审计",
        "batch.cancelled": "批次取消",
        "prompt.preview_request": "等待你确认提示词",
        "prompt.preview_response": "已确认提示词",
        "cost.update": "用量记录",
        "manual_review": "需要人工复查",
    }
    return labels.get(value, value)


def _run_option_label(run: dict[str, Any], index: int) -> str:
    raw_status = run.get("status")
    status_text = {
        "running": "正在翻译",
        "queued": "排队中",
        "orphaned": "未正常收尾",
        "abandoned": "已中断，仅审计",
        "paused": "已中断，仅审计",
        "waiting_preview": "已中断，仅审计",
        "complete": "已完成",
        "failed": "翻译失败",
        "cancelled": "已取消",
        "discarded": "已抛弃",
    }.get(str(raw_status or ""), _status_label(raw_status))
    total = run.get("batches_total") or run.get("item_count")
    parts = [f"{status_text}：{'最近一次任务' if index == 1 else f'第 {index} 次任务'}"]
    if total:
        parts.append(f"{total} 组文本")
    return "，".join(parts)


def _preferred_run_id(runs: list[dict[str, Any]]) -> str:
    running = next((row for row in runs if row.get("status") in {"running", "queued"}), None)
    selected = running or (runs[0] if runs else None)
    return str(selected.get("run_id") or "") if selected else ""


def _planned_batch_item_count(batch: dict[str, Any]) -> int:
    for key in ("item_count", "items_total", "total"):
        value = batch.get(key)
        if isinstance(value, int) and value > 0:
            return value
    items = batch.get("items")
    if isinstance(items, list):
        return len(items)
    units = batch.get("units")
    if isinstance(units, list):
        return len(units)
    return 0


def _planned_batch_label(_plan_id: str, _batch_id: str, index: int, batch: dict[str, Any]) -> str:
    count = _planned_batch_item_count(batch)
    count_text = f"{count} 条待翻译" if count else "待翻译内容"
    return f"历史第 {index} 批：{count_text}"


def _audit_plan_batch_label(
    *,
    project: str,
    plugin_name: str,
    planned_at: str,
    index: int,
    batch: dict[str, Any],
) -> str:
    count = _planned_batch_item_count(batch)
    count_text = f"{count} 条" if count else "若干条"
    source = plugin_name or "未记录 ESP/ESM/ESL"
    return f"{planned_at} / {project} / {source} / 历史第 {index} 批：{count_text}"


def _preview_select_label(preview: PreviewRequest) -> str:
    batch_count = len(preview.items)
    batch_text = f"{batch_count} 条" if batch_count else "若干条"
    index = preview.batch_index or 1
    if preview.total_batches and preview.total_items:
        return f"当前第 {index}/{preview.total_batches} 组：本组 {batch_text}，本次任务共 {preview.total_items} 条，等待确认"
    if preview.total_batches:
        return f"当前第 {index}/{preview.total_batches} 组：本组 {batch_text}，等待确认"
    return f"当前第 {index} 组文本：{batch_text}，等待确认"


def _pending_previews(project: str | None) -> list[PreviewRequest]:
    if project is None:
        return []
    pending = [
        payload
        for payload, _future in _PENDING_PREVIEWS.values()
        if payload.project == project
    ]
    return sorted(pending, key=lambda payload: (payload.run_id, payload.batch_id))


def _annotate_run_rows(project: str | None, conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending_run_ids = {payload.run_id for payload in _pending_previews(project)}
    now = datetime.now(UTC)
    annotated: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        raw_status = str(copy.get("status") or "")
        if raw_status in {"running", "queued"} and not _run_looks_active(conn, copy, pending_run_ids, now):
            copy["raw_status"] = raw_status
            copy["status"] = "orphaned"
            copy["status_note"] = "上次任务没有正常写入完成状态；如果没有外部 CLI 还在运行，它不会继续执行。"
        annotated.append(copy)
    return annotated


def _run_looks_active(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    pending_run_ids: set[str],
    now: datetime,
) -> bool:
    run_id = str(row.get("run_id") or "")
    if run_id in pending_run_ids:
        return True
    latest = _latest_run_activity(conn, run_id) or _parse_datetime(str(row.get("started_at") or ""))
    return latest is not None and now - latest <= _ACTIVE_RUN_WINDOW


def _latest_run_activity(conn: sqlite3.Connection, run_id: str) -> datetime | None:
    if not run_id:
        return None
    try:
        row = conn.execute("SELECT MAX(emitted_at) FROM events WHERE run_id = ?", (run_id,)).fetchone()
    except sqlite3.Error:
        return None
    return _parse_datetime(str(row[0] or "")) if row else None


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _run_rows(project: str | None) -> list[dict[str, Any]]:
    if project is None:
        return []
    memory_path = paths.project_root(project) / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return []
    conn = _open_project_db(project)
    try:
        return _annotate_run_rows(project, conn, [_sqlite_row_dict(row) for row in list_recent_runs(conn, limit=20)])
    finally:
        conn.close()


def _batch_rows(project: str | None, run_id: str) -> list[dict[str, Any]]:
    if project is None or not run_id:
        return []
    memory_path = paths.project_root(project) / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return []
    conn = _open_project_db(project)
    try:
        rows = conn.execute(
            """
            SELECT batch_id, run_id, plan_id, item_count, started_at, completed_at,
                   status, tokens_in, tokens_out, cost_usd, cost_exact, retry_count
            FROM batches
            WHERE run_id = ?
            ORDER BY started_at ASC, batch_id ASC
            """,
            (run_id,),
        ).fetchall()
        batch_rows = [_sqlite_row_dict(row) for row in rows]
        return batch_rows or _batch_rows_from_events(conn, run_id)
    finally:
        conn.close()


def _batch_rows_from_events(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for event in fetch_events_for_run(conn, run_id, 0):
        batch_id = event.get("batch_id")
        if not batch_id:
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        row = batches.setdefault(
            str(batch_id),
            {
                "batch_id": str(batch_id),
                "run_id": run_id,
                "plan_id": "",
                "item_count": int(payload.get("item_count") or payload.get("total") or 0),
                "started_at": event.get("emitted_at"),
                "completed_at": None,
                "status": "running",
                "tokens_in": None,
                "tokens_out": None,
                "cost_usd": None,
                "cost_exact": False,
                "retry_count": 0,
            },
        )
        if payload.get("item_count") or payload.get("total") or payload.get("items_total"):
            row["item_count"] = int(payload.get("item_count") or payload.get("total") or payload.get("items_total") or 0)
        kind = str(event.get("kind") or "")
        if kind == "batch.complete":
            row["status"] = str(payload.get("status") or "complete")
            row["completed_at"] = event.get("emitted_at")
            row["tokens_in"] = payload.get("tokens_in")
            row["tokens_out"] = payload.get("tokens_out")
            row["cost_usd"] = payload.get("cost_usd") or payload.get("cost")
            row["cost_exact"] = bool(payload.get("cost_exact"))
            row["retry_count"] = int(payload.get("retry_count") or 0)
        elif kind in {"batch.failed", "batch.cancelled"}:
            row["status"] = "cancelled" if kind == "batch.cancelled" else "failed"
            row["completed_at"] = event.get("emitted_at")
    return sorted(batches.values(), key=lambda row: str(row.get("started_at") or ""))


def _recent_event_rows(project: str | None) -> list[dict[str, Any]]:
    if project is None:
        return []
    memory_path = paths.project_root(project) / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return []
    conn = _open_project_db(project)
    try:
        row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        if row is None:
            return []
        return fetch_events_for_run(conn, str(row[0]), 0)[-100:]
    finally:
        conn.close()


def _run_dir(project: str, run_id: str) -> Path:
    safe_run_id = _safe_log_file_name(run_id)
    run_dir = paths.project_root(project) / "batches" / safe_run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"run not found: {run_id}")
    return run_dir


def _safe_log_file_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid log file name: {name}")
    return name


def _read_run_file(run_dir: Path, name: str) -> str | None:
    safe_name = _safe_log_file_name(name)
    path = run_dir / safe_name
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _log_file_rows(run_dir: Path) -> list[dict[str, Any]]:
    preferred = [
        "status.toml",
        "validator-failures.jsonl",
        "results.json",
        "system-prompt.md",
        "plan.json",
    ]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for name in preferred:
        path = run_dir / name
        if path.exists() and path.is_file():
            rows.append({"name": name, "size": path.stat().st_size})
            seen.add(name)
    for path in sorted(run_dir.iterdir()):
        if path.name in seen or not path.is_file():
            continue
        rows.append({"name": path.name, "size": path.stat().st_size})
    return rows


def _planned_batches(project: str | None, *, limit: int = 80) -> list[dict[str, Any]]:
    """Return recent plan batches for Prompt-tab browsing."""

    if project is None:
        return []
    plan_paths = sorted(
        (paths.project_root(project) / "batches").glob("*/plan.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    planned: list[dict[str, Any]] = []
    for plan_path in plan_paths:
        try:
            data = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        base_prompt = str(data.get("sample_system_prompt") or "")
        plan_id = str(data.get("plan_id") or plan_path.parent.name)
        plan_project = str(data.get("project") or project)
        source = _project_source_details(plan_project)
        plugin_name = str(source.get("plugin_name") or "")
        planned_at = datetime.fromtimestamp(plan_path.stat().st_mtime).astimezone().strftime("%Y-%m-%d %H:%M")
        for index, batch in enumerate(data.get("batches") or [], start=1):
            if not isinstance(batch, dict):
                continue
            batch_id = str(batch.get("batch_id") or f"batch-{index}")
            parent_context = batch.get("parent_context_summary")
            prompt = base_prompt
            if isinstance(parent_context, str) and parent_context:
                prompt = f"{base_prompt}\n\n{parent_context}"
            planned.append(
                {
                    "label": _planned_batch_label(plan_id, batch_id, index, batch),
                    "audit_label": _audit_plan_batch_label(
                        project=plan_project,
                        plugin_name=plugin_name,
                        planned_at=planned_at,
                        index=index,
                        batch=batch,
                    ),
                    "project": plan_project,
                    "source_plugin": plugin_name,
                    "planned_at": planned_at,
                    "plan_id": plan_id,
                    "batch_id": batch_id,
                    "item_count": _planned_batch_item_count(batch),
                    "prompt": prompt,
                    "glossary_subset": [
                        item for item in (batch.get("glossary_subset") or []) if isinstance(item, dict)
                    ],
                    "glossary_evidence": [
                        item for item in (batch.get("glossary_evidence") or []) if isinstance(item, dict)
                    ],
                    "do_not_translate": [
                        str(item) for item in (batch.get("do_not_translate") or []) if str(item)
                    ],
                }
            )
            if len(planned) >= limit:
                return planned
    return planned


def _sample_prompt(project: str | None) -> str:
    if project is not None:
        for plan_path in sorted(
            (paths.project_root(project) / "batches").glob("*/plan.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(plan_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            prompt = data.get("sample_system_prompt")
            if isinstance(prompt, str) and prompt:
                return prompt
    return (
        "你是 Starfield 2330 殖民星区的中文本地化助手。\\n\\n"
        "游戏世界：硬科幻 NASA-punk；UC/FC/Crimson Fleet/Va'ruun House 等派系缩写保持原文。\\n"
        "mod：RYOS - Roll Your Own Start，替代起始模组，重点是角色开局选择、飞船、债务和背景故事。\\n\\n"
        "风格要求：语气务实，菜单标题简短一致。保留 <Global.*>、{{P0}} 等占位符。\\n\\n"
        "返回 JSON 格式：{\"I1\":\"译文\",\"I2\":\"译文\"}"
    )


def _open_project_db(project: str) -> sqlite3.Connection:
    project_root = paths.project_root(project)
    memory_path = project_root / "memory" / "memory.sqlite"
    if not memory_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"memory.sqlite not found for {project}")
    conn = open_memory_db(project_root)
    conn.row_factory = sqlite3.Row
    return conn


def _load_profiles_for_api() -> ProfilesConfig:
    try:
        return load_profiles()
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"could not load profiles: {exc}") from exc


def _profile_from_payload(payload: ProfileSave, cfg: ProfilesConfig) -> tuple[ProviderProfile, str | None]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "profile name is required")
    base_url, stripped_suffix = normalize_base_url(payload.base_url)
    original_name = (payload.original_name or payload.name).strip()
    created_at = cfg.profiles[original_name].created_at if original_name in cfg.profiles else None
    json_mode = payload.json_mode.strip() if isinstance(payload.json_mode, str) and payload.json_mode.strip() else None
    try:
        profile = ProviderProfile(
            name=name,
            sdk_kind=payload.sdk_kind,  # type: ignore[arg-type]
            base_url=base_url,
            model=payload.model.strip(),
            api_key_env=payload.api_key_env.strip(),
            max_concurrency=max(1, int(payload.max_concurrency)),
            rate_limit_rpm=payload.rate_limit_rpm,
            rate_limit_tpm=payload.rate_limit_tpm,
            cost_cap_usd=payload.cost_cap_usd,
            notes=payload.notes.strip(),
            created_at=created_at,
            prompt_caching=payload.prompt_caching,
            json_mode=json_mode,  # type: ignore[arg-type]
            require_parameters=payload.require_parameters,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return profile, stripped_suffix


def _profile_payload(profile: ProviderProfile, *, active: bool) -> dict[str, Any]:
    return {
        "name": profile.name,
        "sdk_kind": profile.sdk_kind,
        "base_url": profile.base_url,
        "model": profile.model,
        "api_key_env": profile.api_key_env,
        "max_concurrency": profile.max_concurrency,
        "rate_limit_rpm": profile.rate_limit_rpm,
        "rate_limit_tpm": profile.rate_limit_tpm,
        "cost_cap_usd": profile.cost_cap_usd,
        "notes": profile.notes,
        "prompt_caching": profile.prompt_caching,
        "json_mode": profile.json_mode,
        "require_parameters": profile.require_parameters,
        "active": active,
        "key_configured": _profile_key_configured(profile),
    }


def _profile_key_configured(profile: ProviderProfile) -> bool:
    try:
        return bool(resolve_api_key(profile))
    except ProfileMissingKeyError:
        return False


_GLOSSARY_WRITABLE_SCOPES = {"player", "do_not_translate"}
_GLOSSARY_SCOPES = {"vanilla", "mod", "player", "do_not_translate"}
_GLOSSARY_CATEGORIES = {
    "lore_term",
    "faction",
    "item",
    "character",
    "location",
    "generic",
    "place",
    "spell",
    "ui_label",
    "brand",
}
_GLOSSARY_CONFIDENCES = {"canonical", "preferred", "candidate"}


def _normalize_glossary_scope(scope: str) -> str:
    normalized = scope.strip().lower()
    aliases = {"dnt": "do_not_translate", "do-not-translate": "do_not_translate"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in _GLOSSARY_SCOPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown glossary scope: {scope}")
    return normalized


def _glossary_scope_message(scope: str) -> str:
    if scope == "vanilla":
        return "这是游戏本体术语层，通常由工具从知识库自动整理；普通玩家不用手动添加。"
    if scope == "mod":
        return "这是当前 MOD 术语层，通常由工具根据模组上下文自动整理；普通玩家不用手动添加。"
    if scope == "do_not_translate":
        return "这里放人名、地名、缩写、品牌名等不要翻译的词。新增后，下一次计划会把它们告诉 AI 保持原文。"
    return "这里放玩家自己的翻译偏好。新增后，下一次计划会把这些术语交给 AI 参考。"


def _glossary_project_context(project: str | None) -> dict[str, str | None]:
    if not project:
        return {"project": None, "game": None, "target_lang": "zh-cn", "mod_slug": None}
    project_root = paths.project_root(project)
    data = _project_toml_data(project_root)
    raw_project: object = data.get("project")
    project_data: dict[str, Any] = raw_project if isinstance(raw_project, dict) else {}
    game = str(project_data.get("game") or "").strip() or None
    target_lang = str(project_data.get("target_lang") or "zh-cn").strip() or "zh-cn"
    source_plugin_path = str(project_data.get("source_plugin_path") or "").strip()
    mod_slug = Path(source_plugin_path).stem if source_plugin_path else None
    return {"project": project, "game": game, "target_lang": target_lang, "mod_slug": mod_slug}


def _sync_bundled_game_kb(game: str | None) -> list[str]:
    if not game:
        return []
    bundled_root = _bundled_kb_packs_root()
    if bundled_root is None:
        return []
    notes: list[str] = []
    for source_dir in sorted(child for child in bundled_root.iterdir() if child.is_dir()):
        manifest = _read_json_dict(source_dir / "manifest.json")
        manifest_games = _manifest_games(manifest)
        if game not in manifest_games:
            continue
        if not (_manifest_domains(manifest) & {"glossary", "localization", "translation"}):
            continue
        if not (source_dir / "kb.sqlite").is_file():
            continue
        dest_dir = paths.kb_packs_root() / source_dir.name
        source_manifest = (source_dir / "manifest.json").read_text(encoding="utf-8") if (source_dir / "manifest.json").exists() else ""
        dest_manifest = (dest_dir / "manifest.json").read_text(encoding="utf-8") if (dest_dir / "manifest.json").exists() else ""
        if dest_dir.exists() and source_manifest == dest_manifest:
            record_count = manifest.get("recordCount")
            count_text = f"{record_count} 条" if isinstance(record_count, int) else "已安装"
            notes.append(f"已连接 {game} 本体术语库：{count_text}。")
            continue
        tmp_dir = dest_dir.with_name(f".{dest_dir.name}.tmp")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        shutil.copytree(source_dir, tmp_dir)
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        tmp_dir.rename(dest_dir)
        record_count = manifest.get("recordCount")
        count_text = f"{record_count} 条" if isinstance(record_count, int) else "已同步"
        notes.append(f"已同步 {game} 本体术语库：{count_text}。")
    return notes


def _manifest_games(manifest: dict[str, Any]) -> set[str]:
    games = manifest.get("games")
    if isinstance(games, list):
        return {str(item).strip() for item in games if str(item).strip()}
    game = str(manifest.get("game") or "").strip()
    return {game} if game else set()


def _manifest_domains(manifest: dict[str, Any]) -> set[str]:
    domains = manifest.get("domains")
    if isinstance(domains, list):
        return {str(item).strip() for item in domains if str(item).strip()}
    return set()


def _bundled_kb_packs_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "knowledge" / "bgs-kb" / "packs"
        if candidate.is_dir():
            return candidate
    return None


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _glossary_entries(
    *,
    scope: str,
    search: str | None = None,
    game: str | None = None,
    target_lang: str | None = None,
    mod_slug: str | None = None,
    limit: int = 500,
) -> list[GlossaryEntry]:
    reader = KBGlossaryReader()
    try:
        dbs = [*reader.pack_dbs, *reader.user_pack_dbs]
    finally:
        reader.close()
    needle = (search or "").strip().casefold()
    deduped: dict[str, GlossaryEntry] = {}
    for pack_id, db_path in dbs:
        remaining = max(limit - len(deduped), 0)
        if remaining <= 0:
            break
        for entry in _read_glossary_pack_entries(
            pack_id,
            db_path,
            scope=scope,
            search=needle,
            game=game,
            target_lang=target_lang,
            mod_slug=mod_slug,
            limit=remaining,
        ):
            deduped[entry.record_id] = entry
    return sorted(deduped.values(), key=lambda entry: (entry.source.casefold(), entry.record_id))


def _read_glossary_pack_entries(
    pack_id: str,
    db_path: Path,
    *,
    scope: str,
    search: str,
    game: str | None,
    target_lang: str | None,
    mod_slug: str | None,
    limit: int,
) -> list[GlossaryEntry]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        where = ["r.kind = 'glossary-entry'", "ge.scope = ?"]
        params: list[Any] = [scope]
        if target_lang:
            where.append("LOWER(ge.target_lang) = LOWER(?)")
            params.append(target_lang)
        if scope == "mod":
            if mod_slug:
                where.append("ge.scope_key = ?")
                params.append(mod_slug)
            else:
                where.append("ge.scope_key IS NULL")
        if game:
            where.append(
                """
                (
                    NOT EXISTS (SELECT 1 FROM record_games rg_any WHERE rg_any.record_id = ge.record_id)
                    OR EXISTS (
                        SELECT 1 FROM record_games rg
                        WHERE rg.record_id = ge.record_id AND rg.game = ?
                    )
                )
                """
            )
            params.append(game)
        if search:
            like = f"%{search}%"
            where.append(
                """
                (
                    LOWER(ge.source) LIKE ?
                    OR LOWER(ge.target) LIKE ?
                    OR LOWER(COALESCE(ge.notes, '')) LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM glossary_aliases ga
                        WHERE ga.record_id = ge.record_id AND LOWER(ga.alias) LIKE ?
                    )
                )
                """
            )
            params.extend([like, like, like, like])
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT ge.*, r.pack_id AS row_pack_id
            FROM glossary_entries ge
            JOIN records r ON r.id = ge.record_id
            WHERE {' AND '.join(where)}
            ORDER BY ge.source
            LIMIT ?
            """
            ,
            params,
        ).fetchall()
        entries: list[GlossaryEntry] = []
        for row in rows:
            record_id = str(row["record_id"])
            entries.append(
                GlossaryEntry(
                    record_id=record_id,
                    source=str(row["source"]),
                    source_aliases=_glossary_aliases(conn, record_id, "source"),
                    source_lang=str(row["source_lang"]),
                    target=str(row["target"]),
                    target_aliases=_glossary_aliases(conn, record_id, "target"),
                    target_lang=str(row["target_lang"]),
                    scope=row["scope"],
                    scope_key=row["scope_key"],
                    category=row["category"],
                    confidence=row["confidence"],
                    notes=row["notes"],
                    pack_id=str(row["row_pack_id"] or pack_id),
                    games=_glossary_games(conn, record_id),
                )
            )
        return entries
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _save_glossary_entry(payload: GlossarySave) -> GlossaryEntry:
    scope = _normalize_glossary_scope(payload.scope)
    if scope not in _GLOSSARY_WRITABLE_SCOPES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _glossary_scope_message(scope))
    source = payload.source.strip()
    target = payload.target.strip()
    if not source:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "source is required")
    if not target and scope != "do_not_translate":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "target is required for player glossary entries")
    source_lang = payload.source_lang.strip().lower() or "en"
    target_lang = payload.target_lang.strip().lower() or "zh-cn"
    category = payload.category.strip() or "lore_term"
    confidence = payload.confidence.strip() or "preferred"
    if category not in _GLOSSARY_CATEGORIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown category: {category}")
    if confidence not in _GLOSSARY_CONFIDENCES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown confidence: {confidence}")

    db_path = _user_glossary_db_path(source_lang=source_lang, target_lang=target_lang)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        apply_stub_schema(conn)
        record_id = payload.record_id or _next_glossary_record_id(conn, scope, source)
        pack_id = db_path.parent.name
        conn.execute(
            "INSERT OR REPLACE INTO records (id, pack_id, kind, title, body_md) VALUES (?, ?, 'glossary-entry', ?, ?)",
            (record_id, pack_id, source, payload.notes.strip() or None),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO glossary_entries (
                record_id, source, source_lang, target, target_lang, scope,
                scope_key, category, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                record_id,
                source,
                source_lang,
                target or source,
                target_lang,
                scope,
                category,
                confidence,
                payload.notes.strip() or None,
            ),
        )
        conn.execute("DELETE FROM glossary_aliases WHERE record_id = ?", (record_id,))
        for alias in _clean_aliases(payload.source_aliases):
            conn.execute(
                "INSERT INTO glossary_aliases (record_id, alias, alias_kind) VALUES (?, ?, 'source')",
                (record_id, alias),
            )
        for alias in _clean_aliases(payload.target_aliases):
            conn.execute(
                "INSERT INTO glossary_aliases (record_id, alias, alias_kind) VALUES (?, ?, 'target')",
                (record_id, alias),
            )
        conn.commit()
        return GlossaryEntry(
            record_id=record_id,
            source=source,
            source_aliases=_clean_aliases(payload.source_aliases),
            source_lang=source_lang,
            target=target or source,
            target_aliases=_clean_aliases(payload.target_aliases),
            target_lang=target_lang,
            scope=scope,  # type: ignore[arg-type]
            scope_key=None,
            category=category,
            confidence=confidence,  # type: ignore[arg-type]
            notes=payload.notes.strip() or None,
            pack_id=pack_id,
            games=[],
        )
    finally:
        conn.close()


def _delete_user_glossary_entry(record_id: str) -> bool:
    dbs = sorted(paths.kb_user_packs_root().glob("translator-overrides-*/kb.sqlite"))
    deleted = False
    for db_path in dbs:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT scope FROM glossary_entries WHERE record_id = ?", (record_id,)).fetchone()
            if row is None or str(row[0]) not in _GLOSSARY_WRITABLE_SCOPES:
                continue
            conn.execute("DELETE FROM glossary_aliases WHERE record_id = ?", (record_id,))
            conn.execute("DELETE FROM record_games WHERE record_id = ?", (record_id,))
            conn.execute("DELETE FROM glossary_entries WHERE record_id = ?", (record_id,))
            conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
            conn.commit()
            deleted = True
        finally:
            conn.close()
    return deleted


def _glossary_payload(entry: GlossaryEntry) -> dict[str, Any]:
    return entry.model_dump(mode="json")


def _user_glossary_db_path(*, source_lang: str = "en", target_lang: str = "zh-cn") -> Path:
    source_part = re.sub(r"[^a-z0-9]+", "", source_lang.casefold()) or "en"
    target_part = re.sub(r"[^a-z0-9]+", "", target_lang.casefold()) or "zhcn"
    return paths.kb_user_packs_root() / f"translator-overrides-{source_part}-{target_part}" / "kb.sqlite"


def _next_glossary_record_id(conn: sqlite3.Connection, scope: str, source: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", source.casefold()).strip("-") or "entry"
    base = f"translator.override.{scope}.{slug}"
    record_id = base
    counter = 2
    while conn.execute("SELECT 1 FROM records WHERE id = ?", (record_id,)).fetchone() is not None:
        record_id = f"{base}.{counter}"
        counter += 1
    return record_id


def _clean_aliases(values: list[str]) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in values if part.strip()))


def _glossary_aliases(conn: sqlite3.Connection, record_id: str, alias_kind: str) -> list[str]:
    rows = conn.execute(
        "SELECT alias FROM glossary_aliases WHERE record_id = ? AND alias_kind = ? ORDER BY rowid",
        (record_id, alias_kind),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _glossary_games(conn: sqlite3.Connection, record_id: str) -> list[str]:
    rows = conn.execute("SELECT game FROM record_games WHERE record_id = ? ORDER BY game", (record_id,)).fetchall()
    return [str(row[0]) for row in rows]


def _active_profile_label() -> str:
    try:
        import tomllib as _tomllib

        path = paths.profiles_toml_path()
        if path.exists():
            data = _tomllib.loads(path.read_text(encoding="utf-8"))
            active = data.get("active")
            if isinstance(active, dict) and active.get("profile"):
                return str(active["profile"])
            if isinstance(active, str):
                return active
    except OSError:
        pass
    return "未配置"


def _sqlite_row_dict(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    return {str(index): value for index, value in enumerate(row)}


def _pick_port(port: int | None) -> int:
    candidates = [port] if port is not None else list(range(7843, 7851))
    for candidate in candidates:
        if candidate is not None and _port_available(candidate):
            return candidate
    raise RuntimeError("No available localhost port in 7843..7850")


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _write_port(port: int) -> None:
    path = paths.translator_root() / "gui.port"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(port), encoding="utf-8")


def _remove_port() -> None:
    try:
        (paths.translator_root() / "gui.port").unlink()
    except FileNotFoundError:
        pass


def _esc(value: object) -> str:
    import html

    return html.escape(str(value), quote=True)


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def main() -> None:
    """Run the web GUI module as ``python -m bgs_translator.web.app``."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--theme", default=None)
    args = parser.parse_args()
    launch_web(theme=args.theme, port=args.port, no_open=args.no_open, native=args.native)


if __name__ == "__main__":
    main()


__all__ = ["fastapi_app", "launch_web", "main", "setup_theme"]
