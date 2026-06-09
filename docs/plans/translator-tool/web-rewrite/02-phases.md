# bgs-translator Web Rewrite — Phase-by-Phase Plan

> See `00-spec.md` for intent and `01-architecture.md` for tech design. This doc is the **execution plan**.
> Per `00-spec.md` directive, this plan covers the **entire rewrite**; no "first slice" is privileged.
> Per writing-plans skill: each phase has bite-sized tasks with exact file targets and verification commands. Phase-internal micro-plans (line-level TDD steps) are written **at phase start** in a per-phase `notes-phase-N.md`, not in advance.

---

## Phase index

| Phase | Goal | Touches | Verification | Est. days |
|---|---|---|---|---|
| 0 | Spec sign-off + branch + skeleton | `web/`, `pyproject.toml`, `tests/web_e2e/conftest.py` | `pytest tests/web_e2e/test_smoke.py` | 0.5 |
| 1 | Events table + EventPublisher + runner integration | `core/memory.py`, `core/event_publisher.py`, `pipeline/runner.py` | `pytest tests/core/ tests/pipeline/` + smoke | 1 |
| 2 | GUI server skeleton + `xtl gui --backend web` + healthz | `web/app.py`, `cli/app.py`, `cli/gui_launcher.py` | `xtl gui --backend web` opens browser; `pytest tests/web_e2e/test_server_lifecycle.py` | 1 |
| 3 | Preview handshake (CLI POST → GUI server → WS broadcast → respond) | `web/api/preview.py`, `core/web_ipc_client.py`, `cli/batch.py`, `web/pages/prompt.py` | Full handshake test against synthetic LLM client | 1.5 |
| 4 | Batches + Project tabs (read-only, sqlite-as-truth) | `web/pages/batches.py`, `web/pages/project.py`, `web/api/runs.py`, `web/api/projects.py` | Live event stream visible in browser during synthetic run | 1 |
| 5 | Entries tab + detail pane (fixes Bug D) | `web/pages/entries.py`, `web/api/entries.py`, `web/components/entry_detail.py` | Browse + edit a unit; 500-row table virtualized | 1 |
| 6 | Profiles tab + Set-API-key + probe + base-URL strip | `web/pages/profiles.py`, `web/api/profiles.py` | Add profile, set key, probe (mocked) | 0.5 |
| 7 | Glossary tab + scope gating + Add dialog | `web/pages/glossary.py`, `web/api/glossary.py`, `web/components/glossary_table.py` | Add player entry visible in next plan | 0.5 |
| 8 | Logs tab + theme switcher + i18n loader | `web/pages/logs.py`, `web/api/logs.py`, `web/themes/*.css`, `web/i18n/loader.py` | All 7 tabs functional + theme switch live | 0.5 |
| 9 | Playwright test suite for parity | `tests/web_e2e/test_*.py` | `pytest tests/web_e2e/ -v` all green | 1 |
| 10 | Live LLM acceptance + cross-process event verification | live run | Real batch end-to-end against web GUI | 0.5 |
| 11 | Cut-over: flip default, deprecate Tk | `cli/app.py`, `pyproject.toml`, `README.md` | `xtl gui` opens web by default | 0.25 |
| 12 | Tk removal | delete `gui/`, `tests/gui/`, `core/ipc.py`, `core/event_queue.py:EventQueueBridge`, dispatch in `cli/batch.py` | `git rm`; full suite green | 0.5 |

**Total: ~9.25 dev-days.** Buffer for rework: +30% → **~12 dev-days** realistic.

---

## Phase 0 — Skeleton

### Goal

Lay down the directory shell, branch, dependencies, and Playwright fixture so subsequent phases land on solid ground.

### Tasks

- [ ] **0.1** Branch off `feat/translator-tool` to `feat/translator-web-rewrite`.

  ```bash
  cd D:\awesome-bgs-mod-master
  git checkout feat/translator-tool
  git pull --ff-only origin feat/translator-tool
  git checkout -b feat/translator-web-rewrite
  ```

- [ ] **0.2** Add dependencies to `tools/bgs-translator/pyproject.toml`:

  ```toml
  [project.dependencies]
  # ... existing ...
  nicegui = ">=3.12.1,<4.0"
  httpx = ">=0.27"
  playwright = ">=1.45; extra=='test'"
  pytest-playwright = ">=0.5; extra=='test'"
  ```

- [ ] **0.3** Create directory shell:

  ```
  tools/bgs-translator/bgs_translator/web/
    __init__.py
    app.py            (placeholder: just FastAPI() + healthz)
    security.py       (placeholder: require_shared_secret stub)
    api/
      __init__.py
    pages/
      __init__.py
    components/
      __init__.py
    themes/
      base.css
      amber.css
    static/
      .gitkeep
    i18n/
      loader.py       (placeholder: returns english strings)
  ```

  Each placeholder `__init__.py` is empty. Each placeholder module has a one-line docstring and `__all__ = []`.

- [ ] **0.4** Create `tools/bgs-translator/tests/web_e2e/`:

  ```
  conftest.py    (gui_server fixture per 01-architecture §5.1)
  test_smoke.py  (asserts /healthz returns 200)
  ```

- [ ] **0.5** `tools/bgs-translator/bgs_translator/web/app.py` minimal:

  ```python
  """NiceGUI server entry point for the web control panel."""
  from __future__ import annotations
  from fastapi import FastAPI

  fastapi_app = FastAPI(title="bgs-translator web GUI")

  @fastapi_app.get("/healthz")
  def healthz() -> dict[str, str]:
      return {"status": "ok"}

  if __name__ == "__main__":
      import uvicorn
      import argparse
      parser = argparse.ArgumentParser()
      parser.add_argument("--port", type=int, default=7843)
      parser.add_argument("--no-open", action="store_true")
      args = parser.parse_args()
      uvicorn.run(fastapi_app, host="127.0.0.1", port=args.port)
  ```

- [ ] **0.6** Run smoke:

  ```bash
  cd D:\awesome-bgs-mod-master\tools\bgs-translator
  pip install -e .[test]
  playwright install chromium
  pytest tests/web_e2e/test_smoke.py -v
  ```

  Expected: 1 passed.

- [ ] **0.7** Commit:

  ```
  git add tools/bgs-translator/bgs_translator/web/ tools/bgs-translator/tests/web_e2e/ tools/bgs-translator/pyproject.toml
  git commit -m "feat(web): phase 0 — skeleton, dependencies, smoke test"
  ```

### Phase 0 acceptance

- `pytest tests/web_e2e/test_smoke.py -v` → 1 passed
- `pytest tests/` full suite → no regressions vs `feat/translator-tool` HEAD
- ruff + mypy clean
- All Tk tests still pass (Tk path untouched)

---

## Phase 1 — Events table + EventPublisher

### Goal

Replace `EventQueueBridge` semantics with a sqlite-backed event log + best-effort HTTP push, so cross-process event flow works structurally. Keeps `GuiEvent` and `GuiEventKind` types verbatim; only the bridge implementation changes.

### Tasks

- [ ] **1.1** Add CREATE TABLE for `events` to `core/memory.py`:

  ```python
  _CREATE_EVENTS_TABLE = """
  CREATE TABLE IF NOT EXISTS events (
      event_id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      batch_id TEXT,
      kind TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      emitted_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
  );

  CREATE INDEX IF NOT EXISTS idx_events_run_emitted ON events (run_id, event_id);
  CREATE INDEX IF NOT EXISTS idx_events_kind ON events (kind);
  """
  ```

  Run on `init_memory_db()`.

- [ ] **1.2** Create `core/event_publisher.py` per `01-architecture.md` §3.2.

  - `class EventPublisher` with `emit(event: GuiEvent)`.
  - `get_publisher()` returns process-singleton.
  - Lazy-reads `gui.port` + `gui.secret` to discover GUI; if absent, `_gui_url=None` and HTTP push is no-op.

- [ ] **1.3** Add helpers to `core/memory.py`:

  ```python
  def insert_event(conn, event: GuiEvent) -> int: ...
  def fetch_events_for_run(conn, run_id: str, since_event_id: int = 0) -> list[dict]: ...
  ```

  Both wrap raw sqlite calls; used by EventPublisher and the GUI reconcile endpoint.

- [ ] **1.4** Tests under `tests/core/test_event_publisher.py`:

  ```
  test_emit_writes_to_sqlite
  test_emit_swallows_http_push_failure
  test_get_publisher_returns_singleton
  test_fetch_events_for_run_filters_by_run_id_and_since
  ```

  All synthetic; no real network.

- [ ] **1.5** Update `pipeline/runner.py` to use `EventPublisher`:

  ```python
  # old: from bgs_translator.core.event_queue import get_bridge
  # new:
  from bgs_translator.core.event_publisher import get_publisher

  # in BatchRunner.__init__:
  self._publisher = get_publisher()

  # everywhere bridge.emit(...) was called:
  self._publisher.emit(GuiEvent(kind=..., payload=..., ...))
  ```

  The `EventQueueBridge` class stays in `core/event_queue.py` because Tk path still uses it. `BatchRunner` migrates exclusively to publisher.

- [ ] **1.6** Update `tests/pipeline/test_runner_persistence.py`:

  Switch the event-capture from `bridge.drain()` to `fetch_events_for_run(conn, run_id, 0)`. Assertions on event order/kinds/payloads unchanged.

- [ ] **1.7** Run full suite, fix anything that broke:

  ```bash
  cd D:\awesome-bgs-mod-master\tools\bgs-translator
  pytest -x -q
  ruff check bgs_translator tests
  mypy bgs_translator
  ```

- [ ] **1.8** Commit:

  ```
  git commit -am "feat(events): sqlite-backed event log + EventPublisher cross-process bridge"
  ```

### Phase 1 acceptance

- All existing tests pass.
- New `test_event_publisher.py` tests pass.
- An end-to-end CLI run (`xtl batch run --dry-run`) writes events to `events` table; verifiable via `sqlite3 memory.sqlite "SELECT COUNT(*) FROM events"`.
- The Tk GUI (`xtl gui`) still works — Tk uses `EventQueueBridge` for its own widgets which is untouched. Only `BatchRunner` switched publisher.

---

## Phase 2 — GUI server skeleton + xtl gui --backend web

### Goal

`xtl gui --backend web` starts a real NiceGUI server. Browser opens automatically and shows a placeholder shell with the tab nav. No tab content yet.

### Tasks

- [ ] **2.1** Implement `web/app.py` per `01-architecture.md` §4.4:

  - `setup_theme()` injects `base.css` + `amber.css` + body classes + primary color.
  - Mounts NiceGUI via `ui.run_with(fastapi_app, mount_path="/", storage_secret=...)`.
  - Includes API routers (placeholders for now — preview, events).
  - Reads/writes `gui.port`, `gui.pid`, `gui.secret` lifecycle files.
  - Generates a random `gui.secret` on startup (32-byte urlsafe).

- [ ] **2.2** Implement `web/security.py`:

  ```python
  from fastapi import Header, HTTPException, status

  def require_shared_secret(authorization: str | None = Header(None)) -> None:
      expected = _load_gui_secret()
      if not authorization or not authorization.startswith("Bearer "):
          raise HTTPException(status.HTTP_401_UNAUTHORIZED)
      token = authorization.removeprefix("Bearer ").strip()
      if token != expected:
          raise HTTPException(status.HTTP_403_FORBIDDEN)
  ```

- [ ] **2.3** Implement `web/components/tab_nav.py` (per `01-architecture.md` §4.3).

- [ ] **2.4** Implement `web/pages/shell.py`:

  ```python
  from nicegui import ui
  from bgs_translator.web.components.tab_nav import render_tab_nav

  @ui.page("/")
  def index() -> None:
      render_tab_nav(active="project")
      with ui.column().mark("page-shell"):
          ui.label("Welcome to bgs-translator (web)").classes("text-amber-400 text-2xl")
          ui.label("Use the tabs to navigate.").classes("text-amber-300")
  ```

  Other tab pages (`@ui.page("/project")`, `@ui.page("/entries")`, etc.) similarly placeholder.

- [ ] **2.5** Extend `cli/gui_launcher.py` with `--backend` flag:

  ```python
  def launch_gui(
      theme: str | None = None,
      language: str | None = None,
      backend: str = "tk",
      port: int | None = None,
      no_open: bool = False,
  ) -> None:
      if backend == "web":
          from bgs_translator.web.app import launch_web
          launch_web(theme=theme, port=port, no_open=no_open)
      else:
          from bgs_translator.gui.app import launch as launch_tk
          launch_tk(theme=theme, language=language)
  ```

  Add `@app.command("gui")` Typer signature update in `cli/app.py`.

- [ ] **2.6** Write `web/app.py:launch_web()`:

  ```python
  def launch_web(
      *,
      theme: str | None = None,
      port: int | None = None,
      no_open: bool = False,
  ) -> None:
      actual_port = _pick_port(port)
      _write_lifecycle_files(actual_port)
      setup_theme(theme or "amber")
      if not no_open:
          import webbrowser
          webbrowser.open(f"http://127.0.0.1:{actual_port}/")
      import uvicorn
      try:
          uvicorn.run(fastapi_app, host="127.0.0.1", port=actual_port, log_level="warning")
      finally:
          _remove_lifecycle_files()
  ```

- [ ] **2.7** Tests under `tests/web_e2e/test_server_lifecycle.py`:

  ```
  test_server_starts_and_responds_to_healthz
  test_server_writes_gui_port_and_secret
  test_server_removes_lifecycle_files_on_clean_shutdown
  test_shell_page_renders_tab_nav_with_all_seven_tabs
  ```

- [ ] **2.8** Manual smoke:

  ```bash
  xtl gui --backend web --port 7843 --no-open
  curl http://127.0.0.1:7843/healthz
  curl -H "Authorization: Bearer $(cat ~/.bgs-modding-superpowers/translator/gui.secret)" http://127.0.0.1:7843/api/preview/request -X POST -d '{}'  # should 422 (validation), not 401
  ```

- [ ] **2.9** Commit:

  ```
  git commit -am "feat(web): phase 2 — server skeleton, --backend web flag, tab nav shell"
  ```

### Phase 2 acceptance

- `xtl gui --backend web` opens browser to amber-themed shell with 7 tab links.
- All 7 tab routes return 200 (with placeholder content).
- `gui.port`, `gui.secret`, `gui.pid` written on start; removed on clean stop.
- All Tk tests still green.
- `pytest tests/web_e2e/test_server_lifecycle.py` all green.

---

## Phase 3 — Preview handshake (the load-bearing slice)

### Goal

End-to-end: a CLI worker POSTs a preview request, the GUI server fans it out via WS, the browser shows the prompt + Approve buttons, user clicks Approve, the CLI worker unblocks. Tested against a synthetic LLM client (no real money).

### Tasks

- [ ] **3.1** Implement `web/api/preview.py` per `01-architecture.md` §2.3.

- [ ] **3.2** Implement `web/events.py:broadcast_ws` per `01-architecture.md` §3.3.

- [ ] **3.3** WS endpoint in `web/app.py`:

  ```python
  from fastapi import WebSocket
  from bgs_translator.web.events import _connected_ws

  @fastapi_app.websocket("/ws")
  async def ws_endpoint(ws: WebSocket) -> None:
      await ws.accept()
      _connected_ws.add(ws)
      try:
          while True:
              await ws.receive_text()  # heartbeat / no-op
      except Exception:
          pass
      finally:
          _connected_ws.discard(ws)
  ```

- [ ] **3.4** Implement `web/pages/prompt.py` minimal:

  - Subscribes to WS in browser via JS injection (NiceGUI `ui.add_body_html` for the `<script>` block).
  - On `preview.opened` message: render prompt body + Approve / Approve-all / Discard buttons.
  - On click Approve: POST to `/api/preview/respond/{batch_id}` with `{"op": "approved", "prompt": "<edited>"}`.
  - On `preview.closed` message: clear UI.

- [ ] **3.5** Implement `core/web_ipc_client.py` per `01-architecture.md` §2.3 (CLI side).

- [ ] **3.6** Adapt `cli/batch.py:_PreviewingLLMClient._request_preview`:

  ```python
  def _request_preview(self, batch, system_prompt):
      backend = os.environ.get("BGS_TRANSLATOR_PREVIEW_BACKEND", "auto")
      if backend == "web" or (backend == "auto" and _has_web_gui()):
          from bgs_translator.core.web_ipc_client import request_preview_http
          return request_preview_http(
              batch_id=batch.batch_id,
              run_id=self._run_id,  # need to thread run_id through
              system_prompt=system_prompt,
              items=_items_payload(batch),
              glossary_subset=[entry.model_dump() for entry in batch.glossary_subset],
              do_not_translate=batch.do_not_translate,
          )
      else:
          # existing Tk named-pipe path
          return request_preview(...)
  ```

- [ ] **3.7** Tests under `tests/web_e2e/test_preview_handshake.py`:

  ```
  test_request_preview_returns_no_gui_when_server_not_running
  test_request_preview_blocks_then_resolves_on_browser_approve
  test_approve_all_resolves_subsequent_requests_for_same_run
  test_discard_returns_discarded
  test_timeout_returns_timeout
  test_concurrent_browser_tabs_first_wins_others_409
  ```

  Uses `gui_server` fixture + `page` fixture + a parallel-thread CLI POST.

- [ ] **3.8** Acceptance smoke: synthetic batch run end-to-end through web preview:

  ```bash
  # in one terminal: start GUI
  xtl gui --backend web --port 7843
  # in another terminal: run synthetic batch
  xtl batch plan ryos-zhcn --register player --target-lang zh-cn \
      --profile dummy-synthetic --sig MESG --field DESC
  BGS_TRANSLATOR_PREVIEW_BACKEND=web \
      xtl batch run ryos-zhcn --plan <plan-id> --dry-run
  # in browser: Approve each batch. Verify run completes.
  ```

- [ ] **3.9** Commit:

  ```
  git commit -am "feat(web): phase 3 — preview handshake end-to-end with synthetic LLM"
  ```

### Phase 3 acceptance

- Live synthetic batch with prompt-preview-required works fully through the web GUI.
- All 6 handshake tests in `test_preview_handshake.py` pass.
- WS connection survives 5 sequential approvals without reconnect.
- Timeout (300s with synthetic clock) is reached and reported correctly.

---

## Phase 4 — Batches + Project tabs (live read-only views)

### Goal

Browser shows live batch progress driven by the event stream and sqlite reads. Project tab lists projects and shows cost / progress for active runs.

### Tasks

- [ ] **4.1** `web/api/runs.py`:

  - `GET /api/runs` — list runs from sqlite (recent first).
  - `GET /api/runs/{run_id}` — run detail + batch list.
  - `GET /api/runs/{run_id}/events?since=<id>` — reconcile per `01-architecture.md` §3.3.

- [ ] **4.2** `web/api/projects.py`:

  - `GET /api/projects` — list projects from disk.
  - `GET /api/projects/{name}` — project detail (game, register, cost_spent, units total/translated).
  - `POST /api/projects/{name}/reload` — re-scan from disk.

- [ ] **4.3** `web/pages/batches.py`:

  - Renders a table per run (most recent at top).
  - Each row: batch_id, status, items, tokens_in/out, cost.
  - On `batch.start` / `batch.progress` / `batch.complete` / `batch.failed` / `cost.update` WS messages: update row in-place.
  - On WS connect: GET reconcile from sqlite for active runs.

- [ ] **4.4** `web/pages/project.py`:

  - Project list on the left.
  - Selected project's detail panel: name, game, register, total units, translated/untranslated count, cost spent.
  - "Reload from disk" button.

- [ ] **4.5** `BatchRunner` event-emit completeness check:

  - Audit `pipeline/runner.py` for every event kind in `01-architecture.md` §1.3 — every `batch.start`, `batch.progress`, `batch.complete`, `batch.failed`, `cost.update`, `run.start`, `run.complete`, `run.failed` is actually emitted in the right place. (This is the Bug C structural fix.)
  - Add unit tests confirming each event is emitted at the right point in the run lifecycle.

- [ ] **4.6** Tests:

  ```
  tests/web_e2e/test_batches_tab.py:
    test_synthetic_run_streams_batch_events_into_browser_table
    test_late_joining_tab_reconciles_from_sqlite
    test_cost_update_event_updates_cost_chip_in_header
  tests/web_e2e/test_project_tab.py:
    test_project_list_loads
    test_project_detail_shows_unit_counts
    test_reload_button_rescans
  ```

- [ ] **4.7** Live acceptance (synthetic): start GUI, run a synthetic 5-batch plan, confirm browser shows 5 rows appear → progress → complete; cost-chip updates 5 times.

- [ ] **4.8** Commit:

  ```
  git commit -am "feat(web): phase 4 — Batches + Project tabs with live event stream"
  ```

### Phase 4 acceptance

- `[尚无运行]` issue (Bug C from handoff) is structurally fixed: a CLI batch run shows up in the browser Batches tab live.
- Late-joining browser tab catches up via sqlite reconcile.
- Cost chip updates.
- Project tab loads.

---

## Phase 5 — Entries tab + detail pane

### Goal

Browseable, filterable Entries table with source/dest detail pane (vertical split). Fixes Bug D from handoff.

### Tasks

- [ ] **5.1** `web/api/entries.py`:

  - `GET /api/entries?project=<>&signature=<>&field=<>&status=<>&q=<>&page=<>&per_page=<>` — paginated filter.
  - `GET /api/entries/{unit_id}` — full unit including parent context.
  - `POST /api/entries/{unit_id}` — update dest, status, etc.

- [ ] **5.2** `web/components/entry_detail.py`:

  - Vertical split: top pane = source (read-only `ui.textarea`); bottom pane = dest (`ui.textarea`).
  - Header buttons: Save edit / Restore / Lock / Mark orphaned.
  - **Bug D fix** verified: both panes exist, each with own scrollbar.

- [ ] **5.3** `web/pages/entries.py`:

  - Uses `ui.aggrid({...})` for the table (AG Grid handles 500+ rows with virtual scroll).
  - Filters: signature, field, status, search box.
  - Row click → selects unit, populates detail pane.

- [ ] **5.4** Tests:

  ```
  tests/web_e2e/test_entries_tab.py:
    test_filter_by_signature
    test_filter_by_status
    test_search_box_filters_by_source_text
    test_row_click_populates_detail_pane_with_both_source_and_dest
    test_edit_dest_save_persists_to_sqlite
    test_500_rows_virtualizes
  ```

- [ ] **5.5** Commit:

  ```
  git commit -am "feat(web): phase 5 — Entries tab + vertical-split detail pane (fixes Bug D)"
  ```

### Phase 5 acceptance

- Bug D from handoff is closed on the web surface.
- 500+ row table responsive.
- Edit-save-reload round-trip works.

---

## Phase 6 — Profiles tab + Set-API-key + probe + base-URL strip

### Goal

Profile management on the web surface with all UX fixes from Q2.

### Tasks

- [ ] **6.1** `web/api/profiles.py`:

  - `GET /api/profiles` — list.
  - `POST /api/profiles` — add (with base-URL auto-strip).
  - `POST /api/profiles/{name}` — edit.
  - `POST /api/profiles/{name}/activate` — set as active.
  - `POST /api/profiles/{name}/probe` — real probe call, hard-fails on missing key.
  - `POST /api/profiles/{name}/set-api-key` — value-only (env var name read-only).

- [ ] **6.2** `web/pages/profiles.py`:

  - Profile list with active marker.
  - Add/Edit dialog with base-URL helper text + auto-strip warning.
  - Set-API-key dialog: env var name as read-only label, value input only (UX 7 invariant).
  - Probe button shows result + green/red badge.

- [ ] **6.3** Tests:

  ```
  tests/web_e2e/test_profiles_tab.py:
    test_add_profile_with_endpoint_in_base_url_auto_strips
    test_set_api_key_dialog_shows_env_name_readonly
    test_probe_with_missing_key_shows_missing_api_key_error
    test_activate_changes_active_marker
  ```

- [ ] **6.4** Commit:

  ```
  git commit -am "feat(web): phase 6 — Profiles tab + Set-API-key + probe + base-URL strip"
  ```

### Phase 6 acceptance

- UX 6, 7, 8 invariants from Q2 are enforced on the web surface.

---

## Phase 7 — Glossary tab + scope gating + Add dialog

### Goal

Glossary management with scope-aware Add gating (UX 1) and field helpers (UX 2).

### Tasks

- [ ] **7.1** `web/api/glossary.py`:

  - `GET /api/glossary?scope=<>` — list entries per scope.
  - `POST /api/glossary` — add entry (player/DNT only; vanilla/mod return 403 with a player-facing "tool automatically maintains this layer" message).
  - `POST /api/glossary/{record_id}` — edit.
  - `DELETE /api/glossary/{record_id}` — remove (player/DNT only).

- [ ] **7.2** `web/components/glossary_table.py`:

  - Per-scope table.
  - Add button disabled when scope=vanilla or scope=mod with empty-state message.
  - Add button enabled when scope=player or scope=dnt.

- [ ] **7.3** `web/pages/glossary.py`:

  - Scope tabs (vanilla / mod / player / dnt).
  - Add dialog with field tooltips (UX 2).

- [ ] **7.4** Tests:

  ```
  tests/web_e2e/test_glossary_tab.py:
    test_scope_vanilla_shows_use_ai_agent_message_with_add_disabled
    test_scope_player_with_empty_shows_no_entries_with_add_enabled
    test_add_player_entry_persists_and_appears_in_next_plan
    test_add_dialog_shows_field_helpers
  ```

- [ ] **7.5** Commit:

  ```
  git commit -am "feat(web): phase 7 — Glossary tab + scope gating + Add dialog helpers"
  ```

### Phase 7 acceptance

- UX 1, 2 invariants from Q3 enforced.
- Newly added player entry appears in the next plan's glossary subset.

---

## Phase 8 — Logs + theme switcher + i18n

### Goal

Round out the 7-tab parity with Logs tab, theme switcher, and bilingual labels.

### Tasks

- [ ] **8.1** `web/api/logs.py`:

  - `GET /api/runs/{run_id}/logs` — read `status.toml` + `validator-failures.jsonl`.
  - `GET /api/runs/{run_id}/log-files` — list files in run dir.
  - `GET /api/runs/{run_id}/log-file/{name}` — fetch one file content.

- [ ] **8.2** `web/pages/logs.py`:

  - Recent events stream (last 100 events from sqlite, live-updated via WS).
  - Per-run log file viewer.

- [ ] **8.3** Theme switcher in shell header:

  - Dropdown: amber / green / mono.
  - On change: `POST /api/theme` saves to settings; page reloads with new theme.

- [ ] **8.4** Language switcher in shell header:

  - Dropdown: en / zh-cn.
  - On change: `POST /api/language` saves to settings; page reloads.

- [ ] **8.5** `web/i18n/loader.py`:

  - Loads `bgs_translator/gui/i18n/en.po` and `zh_CN.po` via standard `gettext`.
  - Exposes `gettext(msgid)` function used by templates.

- [ ] **8.6** Implement `green.css` and `mono.css` per `amber.css` pattern.

- [ ] **8.7** Tests:

  ```
  tests/web_e2e/test_logs_tab.py
  tests/web_e2e/test_theme_switcher.py
  tests/web_e2e/test_language_switcher.py
  ```

- [ ] **8.8** Commit:

  ```
  git commit -am "feat(web): phase 8 — Logs tab + theme switcher + i18n"
  ```

### Phase 8 acceptance

- All 7 tabs functional on web surface.
- Theme switch live without restart.
- Language switch live without restart.

---

## Phase 9 — Playwright test parity suite

### Goal

Comprehensive Playwright coverage so the agent can self-verify every UI change without human round-trip.

### Tasks

- [ ] **9.1** Audit Tk tests under `tests/gui/` and map each to a web-e2e equivalent (or mark "Tk-specific, skip").

- [ ] **9.2** Author missing web-e2e tests until every Tk-version flow has a Playwright counterpart.

- [ ] **9.3** Add `tests/web_e2e/test_keyboard_shortcuts.py` for Ctrl+1..7, Ctrl+B, Ctrl+R, Escape.

- [ ] **9.4** Add `tests/web_e2e/test_full_acceptance.py` — synthetic round-trip:

  - Start GUI.
  - Plan synthetic batch.
  - Run with preview-required.
  - Approve all in browser.
  - Verify completion + cost-chip + Batches tab final state.

- [ ] **9.5** Run full suite:

  ```bash
  pytest tests/ -v
  ```

- [ ] **9.6** Commit:

  ```
  git commit -am "test(web): phase 9 — comprehensive Playwright parity suite"
  ```

### Phase 9 acceptance

- `pytest tests/web_e2e/ -v` green; ≥ 30 tests.
- Every Tk-version user flow has a Playwright counterpart.
- Agent can `pytest tests/web_e2e/ -k <test-name>` and trust the result.

---

## Phase 10 — Live LLM acceptance + cross-process event verification

### Goal

Real OpenRouter run end-to-end against the web GUI. Documents the artifacts under `.opencode/artifacts/web-rewrite-acceptance/round-N/`. Closes Bug C from the handoff with semantic proof.

### Tasks

- [ ] **10.1** Start GUI: `xtl gui --backend web --port 7843`.

- [ ] **10.2** Plan a small live batch:

  ```bash
  xtl batch plan ryos-zhcn --register player --target-lang zh-cn \
      --profile OpenRouter-DeepSeek --sig MESG --field FULL
  ```

- [ ] **10.3** Run with preview-required:

  ```bash
  BGS_TRANSLATOR_PREVIEW_BACKEND=web xtl batch run ryos-zhcn --plan <id>
  ```

- [ ] **10.4** In browser: approve each batch. Verify live:

  - Prompt tab auto-jumps on each preview-request event.
  - Approve button visible.
  - Batches tab populates live (events flow).
  - Cost chip updates per batch.
  - Final completion shows succeeded/retried/manual_review counts.

- [ ] **10.5** Capture artifacts to `.opencode/artifacts/web-rewrite-acceptance/round-1/`:

  - Screenshots of each tab during the run.
  - `events` table dump.
  - `runs` + `batches` table snapshot.
  - Audit dir tree.

- [ ] **10.6** Verify:

  - `events` table has N rows for N events emitted (canonical proof of cross-process event flow).
  - Browser saw every event live (verifiable from WS log + screenshots).
  - Bug C from handoff is now closed.

- [ ] **10.7** Commit:

  ```
  git commit -am "test(web): phase 10 — live LLM acceptance, Bug C closed with semantic proof"
  ```

### Phase 10 acceptance

- A live batch run end-to-end works on the web GUI.
- Cross-process event flow demonstrably works.
- Audit artifacts preserved.

---

## Phase 11 — Cut-over

### Goal

Flip default of `xtl gui` from `tk` to `web`. Tk becomes opt-in for one release.

### Tasks

- [x] **11.1** Run final Tk-vs-web parity check using `00-spec.md` §6 checklist. Block if any item fails.

- [x] **11.2** Get explicit user signoff in chat ("ship cut-over").

- [x] **11.3** Change default backend:

  ```python
  # cli/gui_launcher.py
  def launch_gui(... backend: str = "web", ...) -> None:  # changed default
  ```

- [x] **11.4** Update `tools/bgs-translator/README.md`:

  - `xtl gui` opens the browser control panel.
  - `xtl gui --backend tk` remains an opt-in fallback. Tk deletion is outside the current cut-over scope.

- [x] **11.5** Update `docs/plans/translator-tool/AMENDMENTS.md` with the cut-over date and link.

- [ ] **11.6** Commit:

  ```
  git commit -am "feat(gui): cut over default to --backend web; Tk deprecated"
  ```

### Phase 11 acceptance

- User has signed off.
- `xtl gui` opens browser.
- `xtl gui --backend tk` still works.
- Tk deletion is deferred out of the current Phase 11 cut-over scope.

---

## Phase 12 — Tk removal

### Goal

Delete the Tk tree. The migration is complete.

### Tasks

- [ ] **12.1** Confirm at least one user-workday or release cycle has elapsed since cut-over with no regression complaints. If complaints exist, fix on web; do not roll back to Tk.

- [ ] **12.2** Get explicit user signoff in chat ("delete Tk").

- [ ] **12.3** `git rm -r`:

  - `tools/bgs-translator/bgs_translator/gui/`
  - `tools/bgs-translator/tests/gui/`
  - `tools/bgs-translator/bgs_translator/core/ipc.py`

- [ ] **12.4** Edit `core/event_queue.py`: remove `EventQueueBridge` class. Keep `GuiEvent` dataclass + `GuiEventKind` enum (used by `EventPublisher`).

- [ ] **12.5** Edit `cli/batch.py:_PreviewingLLMClient._request_preview`: remove backend dispatch; only `request_preview_http` remains.

- [ ] **12.6** Edit `cli/gui_launcher.py`: remove `--backend` flag entirely; only web path remains.

- [ ] **12.7** Edit `cli/app.py`: drop `--backend` typer argument.

- [ ] **12.8** Edit `pyproject.toml`: drop `pywin32` (was only for Tk-named-pipe IPC).

- [ ] **12.9** Run full suite. Fix any reference to deleted code.

  ```bash
  pytest -x -q
  ruff check bgs_translator tests
  mypy bgs_translator
  ```

- [ ] **12.10** Update `docs/plans/translator-tool/HANDOFF-POST-LIVE-TEST.md`: mark Bug C as STRUCTURALLY FIXED via web rewrite; mark Bug D as FIXED on web. Bug B stays open as backend-only.

- [ ] **12.11** Update `tools/bgs-translator/README.md`: drop mentions of Tk; mention `xtl gui` opens the web panel.

- [ ] **12.12** Final commit:

  ```
  git commit -m "refactor(gui): remove Tk control panel; web is the only surface"
  ```

- [ ] **12.13** Update `docs/dev-log.md` (per `writing-modpack-devlog` skill) with the migration completion entry.

### Phase 12 acceptance

- `git grep -r "tkinter"` returns zero hits in `tools/bgs-translator/`.
- Full test suite green.
- README accurate.
- Tk-removal commit lands. Migration complete.

---

## Cross-phase invariants

These must hold from Phase 1 through Phase 11 (until cut-over makes them moot):

- ✅ `xtl gui` (no flag) still works as Tk.
- ✅ All existing pipeline tests pass.
- ✅ A live or synthetic batch run with `--backend tk` still works.
- ✅ Bug A regression test (`tests/gui/test_app_prompt.py::test_preview_event_shows_approve_action_row`) stays green until Phase 12 deletes the Tk path.
- ✅ Push to `feat/translator-web-rewrite` after every phase. PR to `feat/translator-tool` at cut-over (Phase 11).

## Backout plan

If at any phase the web path proves architecturally wrong:

1. Stop the phase mid-flight.
2. Revert phase commits on `feat/translator-web-rewrite`.
3. Tk path is untouched; user is not blocked.
4. Re-consult oracle / re-evaluate framework if needed.
5. Resume with corrected approach.

No data loss possible; backend stays intact throughout.

---

**Next document:** `03-acceptance.md` — per-phase semantic acceptance criteria + Playwright marker conventions + risk register.
