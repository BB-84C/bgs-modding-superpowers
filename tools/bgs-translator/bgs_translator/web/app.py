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
import socket
import sqlite3
import subprocess
import sys
import tomllib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import Depends, HTTPException, Query, Request, Response, WebSocket, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ValidationError

from bgs_translator.config import paths
from bgs_translator.config.profiles import (
    ProfileMissingKeyError,
    ProfilesConfig,
    ProviderProfile,
    load_profiles,
    normalize_base_url,
    resolve_api_key,
    save_profiles,
    write_env_var,
)
from bgs_translator.config.settings import load_settings, update_setting
from bgs_translator.core.memory import (
    fetch_events_for_run,
    get_unit_by_row_id,
    list_recent_runs,
    open_memory_db,
    select_units_filtered,
)
from bgs_translator.core.runtime_pid import remove_gui_pid, write_gui_pid
from bgs_translator.kb._schema import apply_stub_schema
from bgs_translator.kb.models import GlossaryEntry
from bgs_translator.kb.reader import KBGlossaryReader
from bgs_translator.parsers.tes4_family import TES4FamilyWalker
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
    return Response(_document_script(active, _selected_project_name(project)), media_type="application/javascript")


class PreviewRequest(BaseModel):
    """Prompt preview request sent by the CLI worker."""

    batch_id: str
    run_id: str
    project: str = ""
    system_prompt: str
    items: list[dict[str, Any]] = []
    glossary_subset: list[dict[str, Any]] = []
    do_not_translate: list[str] = []
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


@fastapi_app.get("/api/projects/{project}")
def api_project(project: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Return one project summary."""

    return _project_summary(project)


@fastapi_app.post("/api/projects/{project}/reload")
def api_project_reload(project: str, _auth: None = Depends(require_shared_secret)) -> dict[str, Any]:
    """Re-read project metadata, source-plugin status, and sqlite-derived counts."""

    project_root = paths.project_root(project)
    if not (project_root / "project.toml").exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project not found: {project}")
    summary = _project_summary(project)
    source = _project_source_details(project, verify_sha=True)
    return {
        "ok": True,
        "project": project,
        "summary": summary,
        "source": source,
        "message": "已重新读取项目配置、源插件状态和本项目条目统计；不会修改原始 MOD 文件。",
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
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Return glossary entries for one scope."""

    normalized_scope = _normalize_glossary_scope(scope)
    entries = [
        _glossary_payload(entry)
        for entry in _glossary_entries(scope=normalized_scope, search=search)
    ]
    return {
        "scope": normalized_scope,
        "writable": normalized_scope in _GLOSSARY_WRITABLE_SCOPES,
        "message": _glossary_scope_message(normalized_scope),
        "entries": entries,
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
    script_query = html.escape(urlencode(query), quote=True)
    refresh = '<meta http-equiv="refresh" content="2">' if active == "batches" else ""
    return f"""<!doctype html>
<html lang="{html.escape(settings.ui.language, quote=True)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {refresh}
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
    cost = _project_summary(project)["cost_spent"] if project else 0.0
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
      <span>本项目累计费用: <b>约 ${cost:.2f}</b></span>
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
        return '<div class="xtl-empty">还没有项目。先用 xtl project init 创建一个翻译项目。</div>'
    summary = _project_summary(project)
    source = summary["source"]
    plugins = source["memory_plugins"] or []
    memory_plugins = "，".join(f'{item["name"]}（{item["count"]} 条）' for item in plugins) or "尚未读取到插件条目"
    source_status = "源文件存在" if source["exists"] else "源文件不存在"
    if source["sha_status"] == "match":
        source_status += "，指纹匹配"
    elif source["sha_status"] == "mismatch":
        source_status += "，指纹与建项时不同"
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
            <tr><th>语言方向</th><td>{_esc(source["source_lang"])} → {_esc(source["target_lang"])}</td></tr>
            <tr><th>解析版本</th><td>{_esc(source["parser_version"] or "未知")}</td></tr>
            <tr><th>费用</th><td>${summary["cost_spent"]:.4f}</td></tr>
          </table>
          <p class="xtl-help">普通玩家主要看“源插件”和“已加载条目来自”：这里应该是你想汉化的 ESP/ESM/ESL 文件。技术条目会在“条目”页按可读文本展示。</p>
        </div>
      </div>
      <div class="xtl-stack">
        <div class="xtl-panel">
          <div class="xtl-panel-title">工作流</div>
          <div class="xtl-panel-body">
            <p>1. 到“提示词”检查 AI 会收到的说明。</p>
            <p>2. 到“批次”观察翻译进度和费用。</p>
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
            <p class="xtl-help">检测到可能仍在运行的 AI 翻译任务时，关闭页面不一定能停止已发出的请求，也不一定会停止计费。请先到“进度”页点“请求停止”。</p>
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
        if (!res.ok) throw new Error((data && (data.detail || data.message)) || `${path} -> ${res.status}`);
        return data;
      }
      function setStatus(text, tone = '') {
        const el = byId('xtl-project-export-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
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
      document.addEventListener('click', event => {
        if (event.target && event.target.id === 'xtl-project-export') exportProject();
        if (event.target && event.target.id === 'xtl-project-open-exports') openExports();
        if (event.target && event.target.id === 'xtl-project-reload') reloadProject();
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
    </div>
    <div class="xtl-workbench xtl-entries-workbench">
      <div class="xtl-panel" data-marker="panel-entries-table">
        <div class="xtl-panel-title">条目列表</div>
        <div class="xtl-panel-body">
          <table class="xtl-table xtl-entries-table" id="xtl-entries-table"><thead><tr><th>类型</th><th>字段</th><th>状态</th><th>原文</th><th>译文</th></tr></thead><tbody><tr><td colspan="5">正在读取条目...</td></tr></tbody></table>
        </div>
      </div>
      <div class="xtl-panel" data-marker="panel-entry-detail">
        <div class="xtl-panel-title">源文 / 译文 <span class="xtl-detail-id" id="xtl-entry-id">{_esc(str(selected["row_id"])) if selected else "未选择"}</span></div>
        <div class="xtl-panel-body xtl-entry-split">
          <div><div class="xtl-help">源文：只读，供核对。保存只会写入本项目记忆库，不会修改原始 MOD 文件。</div><textarea class="xtl-entry-text" data-marker="field-entry-source" id="xtl-entry-source" readonly>{source}</textarea></div>
          <div>
            <div class="xtl-help">译文：可以手动修正 AI 结果。普通玩家只需要改这里。</div>
            <textarea class="xtl-entry-text" data-marker="field-entry-dest" id="xtl-entry-dest">{dest}</textarea>
            <div class="xtl-toolbar" style="margin-top: 10px">
              <span class="xtl-label">保存状态</span>
              <select class="xtl-select" id="xtl-entry-status">
                <option value="translated" {"selected" if status_value == "translated" else ""}>已翻译</option>
                <option value="partial" {"selected" if status_value == "partial" else ""}>需复查</option>
                <option value="locked" {"selected" if status_value == "locked" else ""}>锁定</option>
                <option value="untranslated" {"selected" if status_value == "untranslated" else ""}>未翻译</option>
              </select>
              <button class="xtl-btn primary" data-marker="btn-entry-save" id="xtl-entry-save">保存修正</button>
              <button class="xtl-btn" data-marker="btn-entry-restore" id="xtl-entry-restore">恢复当前译文</button>
              <button class="xtl-btn" data-marker="btn-entry-lock" id="xtl-entry-lock">标记不翻译</button>
              <button class="xtl-btn danger" data-marker="btn-entry-orphan" id="xtl-entry-clear">清空译文</button>
            </div>
            <div class="xtl-help" data-marker="status-entry-save" id="xtl-entry-save-status">选择左侧条目后可以保存。</div>
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
      <span class="xtl-help">这里显示 AI 汉化任务的实时进度和费用；刷新不会修改 MOD 文件。请求停止会让当前选中的运行中任务在安全检查点结束，已经发给 AI 的请求仍可能计费。</span>
      <span class="xtl-help" data-marker="status-cancel-run" id="xtl-cancel-status"></span>
    </div>
    <div class="xtl-workbench">
      <div class="xtl-stack">
        <div class="xtl-metric-grid" data-marker="panel-run-summary">
          <div class="xtl-metric"><div class="xtl-metric-label">运行状态</div><div class="xtl-metric-value" id="xtl-run-status">等待</div></div>
          <div class="xtl-metric"><div class="xtl-metric-label">文本组数</div><div class="xtl-metric-value" id="xtl-run-batches">0</div></div>
          <div class="xtl-metric"><div class="xtl-metric-label">已完成</div><div class="xtl-metric-value" id="xtl-run-complete">0</div></div>
          <div class="xtl-metric"><div class="xtl-metric-label">费用</div><div class="xtl-metric-value" id="xtl-run-cost">$0.0000</div></div>
        </div>
        <div class="xtl-panel" data-marker="panel-batches-table">
          <div class="xtl-panel-title">文本组进度</div>
          <div class="xtl-panel-body">
            <table class="xtl-table xtl-batch-table" id="xtl-batches">
              <thead><tr><th>文本组</th><th>状态</th><th>文本</th><th>进度</th><th>费用</th></tr></thead>
              <tbody><tr><td colspan="5">正在读取批次...</td></tr></tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="xtl-panel">
        <div class="xtl-panel-title">实时记录</div>
        <div class="xtl-panel-body">
          <div class="xtl-help">普通玩家只需要看“完成/失败/需要人工复查”和费用。下面的记录是给排查问题用的。</div>
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
    first_label = f"当前第 1 组文本：{len(current_preview.items) or '若干'} 条，等待确认" if current_preview else "当前没有等待确认的批次"
    select_disabled = "" if current_preview else "disabled"
    action_disabled = "" if current_preview else "disabled"
    preview_status = "等待你确认。" if current_preview else "当前显示的是历史预览或示例提示词，不会发送给 AI。"
    if planned:
        history_options = "".join(
            f'<option value="{index}" {"selected" if index == 0 else ""}>{_esc(item["label"])}</option>'
            for index, item in enumerate(planned)
        )
    else:
        history_options = "<option>暂无历史预览</option>"
    options = f"<option>{_esc(first_label)}</option>"
    first_glossary = _format_glossary_panel(current_preview.glossary_subset) if current_preview else (
        _format_glossary_panel(planned[0]["glossary_subset"]) if planned else "预览后，这里会显示本次用到的专有名词。"
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
          <span class="xtl-help">只有上方显示“等待确认”时，按钮才会把内容发送给 AI。新手推荐只确认当前文本组；自动确认会继续发送后续文本组，可能继续产生费用。</span>
          <span class="xtl-help" data-marker="status-preview-response" id="xtl-preview-status">{_esc(preview_status)}</span>
        </div>
        <details class="xtl-advanced xtl-history-preview">
          <summary>查看历史预览（不会发送给 AI）</summary>
          <div class="xtl-form-grid compact">
            <label class="wide"><span>历史批次</span><select class="xtl-select" data-marker="select-history-batch" id="xtl-history-batch-select">{history_options}</select></label>
          </div>
          <p class="xtl-help">这里用于回看最近生成过的提示词。只有上方显示“等待确认”的当前批次，才可以点击确认发送给 AI。</p>
        </details>
        <div class="xtl-bottom-split">
          <div class="xtl-panel" data-marker="panel-glossary-subset"><div class="xtl-panel-title">本次用到的专有名词</div><div class="xtl-panel-body" id="xtl-glossary">{_esc(first_glossary)}</div></div>
          <div class="xtl-panel" data-marker="panel-dnt-list"><div class="xtl-panel-title">不要翻译的词</div><div class="xtl-panel-body" id="xtl-dnt">{_esc(first_dnt)}</div></div>
        </div>
      </div>
      <div class="xtl-panel xtl-prompt-aside">
        <div class="xtl-panel-title">为什么要先预览？</div>
        <div class="xtl-panel-body xtl-help">
          <p>这一步不会修改原始 MOD 文件。</p>
          <p>AI 翻译前会先让你看到它收到的说明和文本。你可以检查里面有没有奇怪内容、错误术语或不该翻译的名字，再决定是否继续。</p>
          <p>不确定时，只确认当前内容，不要选择“用于整个项目”。</p>
        </div>
      </div>
    </div>
    </div>
    """


def _format_glossary_panel(items: list[dict[str, Any]]) -> str:
    lines = [
        f"{item.get('source') or item.get('term') or ''} -> {item.get('target') or ''}"
        for item in items
        if item.get("source") or item.get("term")
    ]
    return "\n".join(lines) or "本次没有命中的专有名词。"


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
              <label><span>费用上限 USD</span><input class="xtl-input" id="xtl-profile-cost-cap" data-marker="field-profile-cost-cap" type="number" min="0" step="0.01" placeholder="例如 10.00"></label>
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
      <button class="xtl-btn primary" data-marker="btn-add-glossary-entry" id="xtl-glossary-add">添加术语</button>
    </div>
    <div class="xtl-workbench xtl-glossary-workbench">
      <div class="xtl-panel" data-marker="panel-glossary-table">
        <div class="xtl-panel-title">专有名词表 <span class="xtl-detail-id" id="xtl-glossary-scope-title">游戏本体术语</span></div>
        <div class="xtl-panel-body">
          <div class="xtl-help" data-marker="status-glossary-empty-vanilla" id="xtl-glossary-message">这些词表会交给 AI，用来统一译名、保留人名地名和避免把缩写乱翻。游戏本体术语通常由工具从知识库自动整理。</div>
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
          <div class="xtl-help">普通玩家先看这里：完成、失败、费用、需要人工复查都会出现在这里。右侧文件区是排查问题时使用的技术日志。</div>
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
        if (text) text.textContent = '历史任务提醒已知晓；当前没有检测到运行中计费任务';
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
      const glossaryIntro = '这些词表会交给 AI，用来统一译名、保留人名地名和避免把缩写乱翻。';
      const writableScopes = new Set(['player', 'do_not_translate']);
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
        byId('xtl-profile-cost-cap').value = '10.00';
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
        byId('xtl-profile-cost-cap').value = profile.cost_cap_usd ?? '';
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
          cost_cap_usd: optionalNumber('xtl-profile-cost-cap'),
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
    script = """
    <script>
    (() => {
      let current = null;
      const planned = __PLANNED__;
      const promptBody = () => document.getElementById('xtl-prompt-body');
      const batchSelect = () => document.getElementById('xtl-batch-select');
      const historySelect = () => document.getElementById('xtl-history-batch-select');
      const statusLine = () => document.getElementById('xtl-preview-status');
      function setPreviewStatus(text, tone = '') {
        const el = statusLine();
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function shortId(value) {
        return String(value || '').slice(0, 8);
      }
      function fillSidePanels(glossaryItems, dntItems) {
        const glossary = document.getElementById('xtl-glossary');
        const dnt = document.getElementById('xtl-dnt');
        if (glossary) glossary.textContent = (glossaryItems || []).map(x => `${x.source || x.term || ''} → ${x.target || ''}`).join('\\n') || '本次没有命中的专有名词。';
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
          select.innerHTML = '<option>当前没有等待确认的批次</option>';
          select.disabled = true;
        }
        setPreviewStatus('这是历史预览；不会发送给 AI。');
        if (promptBody()) promptBody().value = item.prompt || '';
        fillSidePanels(item.glossary_subset || [], item.do_not_translate || []);
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
            option.textContent = item.label;
            select.appendChild(option);
          });
        }
        if (!current && !batchSelect()?.dataset.runId) renderPlanned(0);
      }
      function renderPreview(msg) {
        current = msg;
        setPreviewControls(true);
        const count = Array.isArray(msg.items) ? msg.items.length : 0;
        const select = batchSelect();
        if (select) {
          select.innerHTML = `<option>当前第 1 组文本：${count || '若干'} 条，等待确认</option>`;
          select.dataset.runId = msg.run_id || '';
          select.dataset.batchId = msg.batch_id || '';
          select.disabled = false;
        }
        setPreviewStatus('等待你确认。');
        if (promptBody()) promptBody().value = msg.system_prompt || '';
        fillSidePanels(msg.glossary_subset || [], msg.do_not_translate || []);
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
          const ok = window.confirm(`这会让本次任务后续批次自动发送给 AI，可能继续产生费用。当前显示 ${count} 条文本，仍然不会修改原始 MOD 文件。确定继续吗？`);
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
          select.innerHTML = '<option>当前没有等待确认的批次</option>';
          select.disabled = true;
        }
        setPreviewStatus(op === 'discarded' ? '已跳过这一段。' : '已发送确认，AI 正在继续翻译。', 'good');
      }
      document.addEventListener('click', (event) => {
        if (event.target && event.target.id === 'xtl-approve') respond('approved');
        if (event.target && event.target.id === 'xtl-approve-all') respond('approve_all');
        if (event.target && event.target.id === 'xtl-discard') respond('discarded');
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
            select.innerHTML = '<option>当前没有等待确认的批次</option>';
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
    return script.replace("__PLANNED__", planned_json)


def _batches_script(project: str | None) -> str:
    project_json = _json_for_script(project or "")
    script = """
    <script>
    (() => {
      const project = __PROJECT__;
      let currentRunId = '';
      let sinceEventId = 0;
      let userSelectedRun = false;
      let runs = [];
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
        complete: '已完成',
        failed: '有问题',
        cancelled: '已取消',
        manual_review: '需人工复查',
      };
      const eventLabels = {
        'run.start': '开始翻译',
        'run.complete': '全部完成',
        'run.failed': '运行失败',
        'run.cancelled': '已取消',
        'batch.start': '批次开始',
        'batch.progress': '批次进度更新',
        'batch.complete': '批次完成',
        'batch.failed': '批次失败',
        'batch.cancelled': '批次取消',
        'prompt.preview_request': '等待你确认提示词',
        'prompt.preview_response': '已确认提示词',
        'cost.update': '费用更新',
        manual_review: '需要人工复查',
      };
      function api(path, options = {}) {
        return fetch(path, {credentials: 'same-origin', ...options}).then(res => {
          if (!res.ok) throw new Error(`${path} -> ${res.status}`);
          return res.json();
        });
      }
      function money(value) {
        const n = Number(value || 0);
        return `$${n.toFixed(4)}`;
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
        if (run.cost_total_usd !== null && run.cost_total_usd !== undefined) parts.push(money(run.cost_total_usd));
        return parts.join('，');
      }
      function preferredRunId() {
        const running = runs.find(run => run.status === 'running' || run.status === 'queued');
        return running ? running.run_id : (runs[0] ? runs[0].run_id : '');
      }
      function currentRun() {
        return runs.find(run => run.run_id === currentRunId) || null;
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
        select.innerHTML = runs.length
          ? runs.map((run, index) => `<option value="${esc(run.run_id)}" title="${esc(run.run_id)}">${esc(runLabel(run, index))}</option>`).join('')
          : '<option value="">尚无运行</option>';
        currentRunId = runs.some(run => run.run_id === previous) ? previous : preferredRunId();
        select.value = currentRunId;
      }
      function renderSummary(run, batches) {
        const completed = batches.filter(batch => batch.status === 'complete').length;
        const cost = run ? run.cost_total_usd : batches.reduce((total, batch) => total + Number(batch.cost_usd || 0), 0);
        const set = (id, value) => {
          const el = document.getElementById(id);
          if (el) el.textContent = value;
        };
        set('xtl-run-status', statusText(run ? run.status : ''));
        set('xtl-run-batches', String(run ? run.batches_total : batches.length));
        set('xtl-run-complete', String(completed));
        set('xtl-run-cost', money(cost));
        updateCancelState(run);
      }
      function renderBatches(batches, events) {
        const body = batchBody();
        if (!body) return;
        if (!batches.length) {
          body.innerHTML = '<tr><td colspan="5">这个运行还没有批次记录。</td></tr>';
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
            <td>${money(batch.cost_usd)}</td>
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
      async function refreshAll({keepSince = false, preferActive = false} = {}) {
        const started = performance.now();
        if (!project) return;
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
      async function pollEvents() {
        if (!project || !currentRunId) return;
        const events = await api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(currentRunId)}/events?since=${sinceEventId}`);
        if (!events.length) return;
        sinceEventId = Math.max(sinceEventId, ...events.map(event => Number(event.event_id || 0)));
        await refreshAll({keepSince: true});
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
        if (!window.confirm('会请求当前翻译任务尽快停止。已经发送给 AI 的请求可能仍会产生费用，确定继续吗？')) return;
        if (status) status.textContent = '正在写入停止请求...';
        try {
          await api(`/api/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(currentRunId)}/cancel`, {method: 'POST'});
          if (status) status.textContent = '已请求停止。任务会在安全检查点结束。';
          await refreshAll();
        } catch (err) {
          if (status) status.textContent = `停止请求失败：${err.message}`;
        }
      }
      document.addEventListener('change', (event) => {
        if (event.target && event.target.id === 'xtl-run-select') {
          userSelectedRun = true;
          currentRunId = event.target.value || '';
          sinceEventId = 0;
          refreshAll();
        }
      });
      document.addEventListener('click', (event) => {
        if (event.target && event.target.id === 'xtl-refresh-batches') refreshAll();
        if (event.target && event.target.id === 'xtl-cancel-run') cancelRun();
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
        pushMetric('wsMessages', {
          at: performance.now(),
          kind: msg.kind || '',
          runId: msg.run_id || '',
          eventId: msg.event_id || null,
        });
        if (msg.event_id || msg.run_id) {
          if (msg.kind === 'run.start' && msg.run_id) {
            if (!userSelectedRun) {
              currentRunId = msg.run_id;
              sinceEventId = 0;
            }
            refreshAll();
          } else if (!currentRunId || msg.run_id === currentRunId) {
            refreshAll({keepSince: true});
          }
        }
      };
      refreshAll({preferActive: true});
      window.setInterval(pollEvents, 1500);
      window.setInterval(() => refreshAll({keepSince: true, preferActive: true}), 5000);
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
        return fetch(path, {credentials: 'same-origin', ...options}).then(res => {
          if (!res.ok) throw new Error(`${path} -> ${res.status}`);
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
      function setSaveStatus(text, tone = '') {
        const el = byId('xtl-entry-save-status');
        if (!el) return;
        el.textContent = text;
        el.className = `xtl-help ${tone}`;
      }
      function renderTable() {
        const body = document.querySelector('#xtl-entries-table tbody');
        if (!body) return;
        if (!entries.length) {
          body.innerHTML = '<tr><td colspan="5">没有匹配的条目。换个筛选条件试试。</td></tr>';
          return;
        }
        body.innerHTML = entries.map(entry => {
          const active = selected && selected.row_id === entry.row_id ? ' class="active"' : '';
          const sigLabel = signatureLabels[entry.signature] ? `${signatureLabels[entry.signature]}（${entry.signature}）` : entry.signature;
          const fieldLabel = fieldLabels[entry.field] ? `${fieldLabels[entry.field]}（${entry.field}）` : entry.field;
          return `<tr${active} data-row-id="${esc(entry.row_id)}" data-marker="row-entries-${esc(entry.row_id)}">
            <td title="条目编号：${esc(entry.edid || entry.row_id)}"><b>${esc(sigLabel)}</b></td>
            <td>${esc(fieldLabel)}</td>
            <td><span class="xtl-status-pill ${esc(entry.status)}">${esc(statusLabels[entry.status] || entry.status)}</span></td>
            <td>${esc(entry.source)}</td>
            <td>${esc(entry.dest || '')}</td>
          </tr>`;
        }).join('');
      }
      function renderDetail(entry) {
        selected = entry;
        savedDest = entry ? (entry.dest || '') : '';
        savedStatus = entry ? (entry.status || 'untranslated') : 'untranslated';
        if (byId('xtl-entry-id')) byId('xtl-entry-id').textContent = entry ? entry.row_id : '未选择';
        if (byId('xtl-entry-source')) byId('xtl-entry-source').value = entry ? entry.source || '' : '';
        if (byId('xtl-entry-dest')) byId('xtl-entry-dest').value = savedDest;
        if (byId('xtl-entry-status')) byId('xtl-entry-status').value = savedStatus;
        setSaveStatus(entry ? '可以保存当前条目的手动修正。' : '选择左侧条目后可以保存。');
        renderTable();
      }
      async function loadEntries({keepSelection = false} = {}) {
        if (!project) return;
        entries = await api(entryUrl());
        let next = null;
        if (keepSelection && selected) next = entries.find(entry => entry.row_id === selected.row_id) || null;
        renderTable();
        renderDetail(next || entries[0] || null);
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
      document.addEventListener('click', event => {
        const row = event.target && event.target.closest ? event.target.closest('#xtl-entries-table tbody tr[data-row-id]') : null;
        if (row) selectRow(row.getAttribute('data-row-id'));
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
        return {"game": "", "units_total": 0, "units_translated": 0, "cost_spent": 0.0, "source": _empty_source_details()}
    project_root = paths.project_root(project)
    game = "Unknown"
    data = _project_toml_data(project_root)
    source = _project_source_details(project)
    if data:
        game = str((data.get("project") or {}).get("game") or game)
    memory_path = project_root / "memory" / "memory.sqlite"
    if not memory_path.exists():
        return {"game": game, "units_total": 0, "units_translated": 0, "cost_spent": 0.0, "source": source}
    conn = sqlite3.connect(memory_path)
    try:
        units_total = int(conn.execute("SELECT COUNT(*) FROM units").fetchone()[0])
        units_translated = int(conn.execute("SELECT COUNT(*) FROM units WHERE status = 'translated'").fetchone()[0])
        cost = conn.execute("SELECT COALESCE(SUM(cost_total_usd), 0) FROM runs").fetchone()[0]
        return {
            "game": game,
            "units_total": units_total,
            "units_translated": units_translated,
            "cost_spent": float(cost or 0.0),
            "source": source,
        }
    finally:
        conn.close()


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
        rows = select_units_filtered(
            conn,
            sigs=[sig] if sig else None,
            fields=[field] if field else None,
            statuses=[entry_status] if entry_status else None,
            search=search,
            limit=limit,
        )
        return [_sqlite_row_dict(row) for row in rows]
    finally:
        conn.close()


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
        return f"有 {len(running)} 个任务运行中，可能继续计费", "danger"
    orphaned = [row for row in rows if str(row.get("status") or "") == "orphaned"]
    if orphaned:
        return f"有 {len(orphaned)} 个历史任务未正常收尾，不会按运行中计费", "warn"
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
        "run.cancelled": "已取消",
        "batch.start": "批次开始",
        "batch.progress": "批次进度更新",
        "batch.complete": "批次完成",
        "batch.failed": "批次失败",
        "batch.cancelled": "批次取消",
        "prompt.preview_request": "等待你确认提示词",
        "prompt.preview_response": "已确认提示词",
        "cost.update": "费用更新",
        "manual_review": "需要人工复查",
    }
    return labels.get(value, value)


def _run_option_label(run: dict[str, Any], index: int) -> str:
    raw_status = run.get("status")
    status_text = {
        "running": "正在翻译",
        "queued": "排队中",
        "orphaned": "未正常收尾",
        "complete": "已完成",
        "failed": "翻译失败",
        "cancelled": "已取消",
    }.get(str(raw_status or ""), _status_label(raw_status))
    total = run.get("batches_total") or run.get("item_count")
    cost = run.get("cost_total_usd")
    parts = [f"{status_text}：{'最近一次任务' if index == 1 else f'第 {index} 次任务'}"]
    if total:
        parts.append(f"{total} 组文本")
    if cost not in {None, ""}:
        try:
            parts.append(f"${float(str(cost)):.4f}")
        except (TypeError, ValueError):
            pass
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
            copy["status_note"] = "上次任务没有正常写入完成状态；如果没有外部 CLI 还在运行，它不会继续计费。"
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
                    "plan_id": plan_id,
                    "batch_id": batch_id,
                    "item_count": _planned_batch_item_count(batch),
                    "prompt": prompt,
                    "glossary_subset": [
                        item for item in (batch.get("glossary_subset") or []) if isinstance(item, dict)
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


def _glossary_entries(*, scope: str, search: str | None = None) -> list[GlossaryEntry]:
    reader = KBGlossaryReader()
    try:
        dbs = [*reader.pack_dbs, *reader.user_pack_dbs]
    finally:
        reader.close()
    needle = (search or "").strip().casefold()
    deduped: dict[str, GlossaryEntry] = {}
    for pack_id, db_path in dbs:
        for entry in _read_glossary_pack_entries(pack_id, db_path):
            if entry.scope != scope:
                continue
            if needle:
                haystack = " ".join(
                    [entry.source, entry.target, *entry.source_aliases, *entry.target_aliases, entry.notes or ""]
                ).casefold()
                if needle not in haystack:
                    continue
            deduped[entry.record_id] = entry
    return sorted(deduped.values(), key=lambda entry: (entry.source.casefold(), entry.record_id))


def _read_glossary_pack_entries(pack_id: str, db_path: Path) -> list[GlossaryEntry]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT ge.*, r.pack_id AS row_pack_id
            FROM glossary_entries ge
            JOIN records r ON r.id = ge.record_id
            WHERE r.kind = 'glossary-entry'
            ORDER BY ge.source
            """
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
