# bgs-translator Web Rewrite — Architecture

> See `00-spec.md` for intent. This doc is the **technical design**: process layout, IPC redesign, event topology, theming, Playwright integration.
> Every decision here is final unless overridden in writing during a phase.

---

## 1. Process topology

Two long-running processes during normal use:

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   GUI server process     │         │   CLI worker process     │
│   (NiceGUI / uvicorn)    │◀═══════▶│   (xtl batch run)        │
│   Long-lived             │  HTTP   │   Transient (per run)    │
│   PID written to gui.pid │   +     │                          │
│   Listens on             │   WS    │   Reuses:                │
│   127.0.0.1:<port>       │         │     pipeline/runner.py   │
│                          │         │     pipeline/clients/*   │
│   Owns:                  │         │     pipeline/validator   │
│     web/app.py           │         │     core/memory.py       │
│     web/tabs/*           │         │     kb/* parsers/*       │
│     web/api/* (FastAPI)  │         │                          │
│     web/themes/*.css     │         │   New:                   │
│     web/static/*         │         │     core/web_ipc_client  │
│                          │         │       (HTTP POST helper) │
│   Stable shared seams:   │         │                          │
│     core/memory.sqlite   │◀════════│ writes batches/runs/units│
│     events table         │◀════════│ writes events            │
│     audit dirs           │◀════════│ writes artifacts         │
└──────────────────────────┘         └──────────────────────────┘
            ▲
            │ WebSocket
            ▼
┌──────────────────────────┐
│   Browser tab(s)         │
│   (Quasar + Vue under    │
│    NiceGUI hood;         │
│    Playwright addresses  │
│    via .mark() markers   │
│    + ARIA roles)         │
└──────────────────────────┘
```

### 1.1 GUI server lifecycle

- Started by `xtl gui --backend web`.
- Writes own PID to `~/.bgs-modding-superpowers/translator/gui.pid` (same path Tk used, semantics unchanged).
- Binds to `127.0.0.1:<port>` where port is either explicit (`--port`), or auto-pick.
- Auto-pick rule: try 7843; if busy, try 7844..7850; if all busy, fail with error envelope.
- Writes port to `~/.bgs-modding-superpowers/translator/gui.port` so CLI workers can discover it without prompting.
- Opens user's default browser to `http://127.0.0.1:<port>/` UNLESS `--no-open` is passed OR `--native` was passed (PyWebView mode).
- Stops cleanly on Ctrl+C or `xtl gui stop` (new subcommand) — uvicorn shutdown.
- On stop: removes `gui.pid` and `gui.port` files.

### 1.2 CLI worker lifecycle

- Unchanged from current. `xtl batch run` is still a transient process per run.
- New module `bgs_translator/core/web_ipc_client.py` provides `request_preview_http(...)` that the runner calls. It:
  - Reads `gui.port` and `gui.pid` to discover the GUI server.
  - If `gui.pid` is dead or `gui.port` is missing, returns `{"op": "no_gui"}` immediately (matches Tk behavior).
  - Otherwise POSTs to `http://127.0.0.1:<port>/api/preview/request` with `Authorization: Bearer <shared-secret>` header.
  - Blocks until response or 300s timeout.

### 1.3 Why two processes (not one)

- The CLI worker can be killed without taking down the GUI.
- The GUI server can be restarted without aborting an in-flight batch (CLI worker would get a `no_gui` on the next preview and fall through to no-preview mode; not great but not catastrophic).
- This matches the user's mental model from Tk (`xtl batch run` is a separate process from the panel).
- The alternative — embed the runner inside the GUI server's uvicorn loop — would block the event loop during LLM calls and is a worse architecture.

### 1.4 Shared secret

A short token written to `~/.bgs-modding-superpowers/translator/gui.secret` (mode 0600 on POSIX; ACL-restricted on Windows) on GUI startup. CLI workers read it and send as `Authorization: Bearer <secret>`. Prevents accidental cross-user IPC on a shared machine. Rotated on every GUI startup.

## 2. IPC redesign — preview handshake

### 2.1 Wire protocol

**Request from CLI to GUI**:

```
POST /api/preview/request
Authorization: Bearer <gui.secret>
Content-Type: application/json

{
  "batch_id": "9bde9f04-...",
  "run_id": "rn_cdffc06ed3f2",
  "system_prompt": "...",
  "items": [
    {"unit": {...}, "source_masked": "...", "byte_budget": 65520, ...},
    ...
  ],
  "glossary_subset": [...],
  "do_not_translate": [...],
  "timeout_seconds": 300
}
```

**Response back to CLI** (after user approves OR timeout):

```json
{
  "op": "approved" | "approve_all" | "discarded" | "no_gui" | "timeout",
  "prompt": "<possibly edited prompt body>",
  "responded_at": "2026-06-08T14:25:00Z",
  "responded_by_session": "<session-uuid>" 
}
```

**Browser approve POST**:

```
POST /api/preview/respond/{batch_id}
Authorization: Bearer <gui.secret>  # passed via cookie or header from the same origin
Content-Type: application/json

{
  "op": "approved",
  "prompt": "<edited prompt body>"
}
```

`approve_all` semantics: the server flags the run so subsequent `request_preview` calls for the same `run_id` resolve immediately with `op=approve_all` and the in-flight prompt unchanged. This matches the Tk `_PreviewingLLMClient` behavior.

### 2.2 Race / edge cases (per oracle's review)

| Case | Server behavior |
|---|---|
| No browser tab open when CLI POSTs | After 5s grace period, server returns `{"op": "no_gui"}`. CLI falls back to no-preview mode. |
| Multiple browser tabs open | All see "preview opened" WS event. First POST to `/api/preview/respond/{batch_id}` wins; later POSTs get HTTP 409. Late tabs see resolution via WS broadcast and grey out their approve UI. |
| Browser disconnects mid-approval | Server-side `asyncio.Future` keeps waiting until timeout or another tab approves. Reconnect-and-replay supported because pending list is server-side. |
| CLI process crashes mid-approval | Future remains until 300s timeout. UI shows "stale preview from {timestamp}" with explicit Discard button. |
| User clicks Discard | Future resolves with `{"op": "discarded"}`. CLI's `_PreviewingLLMClient` returns the discarded-response stub (no LLM call). |
| Server restarts mid-approval | All pending futures lost. CLI's POST eventually times out (300s) and returns `{"op": "timeout"}`. Acceptable; documented in user-facing release notes. |

### 2.3 Reference implementation skeleton

`bgs_translator/web/api/preview.py`:

```python
from __future__ import annotations
import asyncio
from collections.abc import Awaitable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bgs_translator.web.security import require_shared_secret
from bgs_translator.web.events import broadcast_ws

router = APIRouter(prefix="/api/preview")

class PreviewRequest(BaseModel):
    batch_id: str
    run_id: str
    system_prompt: str
    items: list[dict[str, Any]]
    glossary_subset: list[dict[str, Any]]
    do_not_translate: list[str]
    timeout_seconds: float = 300.0

class PreviewResponse(BaseModel):
    op: str
    prompt: str = ""

_pending: dict[str, tuple[PreviewRequest, asyncio.Future[dict[str, Any]]]] = {}
_approve_all_runs: set[str] = set()

@router.post("/request")
async def request_preview(
    payload: PreviewRequest,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    if payload.run_id in _approve_all_runs:
        return {"op": "approve_all", "prompt": payload.system_prompt}
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[payload.batch_id] = (payload, future)
    await broadcast_ws({"kind": "preview.opened", **payload.model_dump()})
    try:
        return await asyncio.wait_for(future, timeout=payload.timeout_seconds)
    except asyncio.TimeoutError:
        _pending.pop(payload.batch_id, None)
        await broadcast_ws({"kind": "preview.timeout", "batch_id": payload.batch_id})
        return {"op": "timeout"}

@router.post("/respond/{batch_id}")
async def respond_preview(
    batch_id: str,
    payload: PreviewResponse,
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    pending = _pending.pop(batch_id, None)
    if pending is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no pending preview")
    request, future = pending
    if payload.op == "approve_all":
        _approve_all_runs.add(request.run_id)
    future.set_result(payload.model_dump())
    await broadcast_ws({"kind": "preview.closed", "batch_id": batch_id, "op": payload.op})
    return {"ok": True}
```

`bgs_translator/core/web_ipc_client.py` (CLI side):

```python
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

import httpx

from bgs_translator.config import paths
from bgs_translator.core import runtime_pid

def _discover_gui() -> tuple[str, str] | None:
    """Return (url, secret) if GUI is alive, else None."""
    port_path = paths.translator_root() / "gui.port"
    secret_path = paths.translator_root() / "gui.secret"
    if not port_path.exists() or not secret_path.exists():
        return None
    alive, _pid = runtime_pid.is_gui_alive()
    if not alive:
        return None
    port = port_path.read_text(encoding="utf-8").strip()
    secret = secret_path.read_text(encoding="utf-8").strip()
    return f"http://127.0.0.1:{port}", secret

def request_preview_http(
    batch_id: str,
    run_id: str,
    system_prompt: str,
    items: list[dict[str, Any]],
    glossary_subset: list[dict[str, Any]],
    do_not_translate: list[str],
    timeout: float = 300.0,
) -> dict[str, Any]:
    discovered = _discover_gui()
    if discovered is None:
        return {"op": "no_gui"}
    url, secret = discovered
    try:
        response = httpx.post(
            f"{url}/api/preview/request",
            json={
                "batch_id": batch_id,
                "run_id": run_id,
                "system_prompt": system_prompt,
                "items": items,
                "glossary_subset": glossary_subset,
                "do_not_translate": do_not_translate,
                "timeout_seconds": timeout,
            },
            headers={"Authorization": f"Bearer {secret}"},
            timeout=timeout + 10.0,  # small buffer over server-side timeout
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, httpx.TimeoutException):
        return {"op": "timeout"}
```

The Tk `request_preview` (named-pipe) function in `core/client.py` is **kept** during the parallel phase so that `cli/batch.py:_PreviewingLLMClient` can dispatch on backend:

```python
# cli/batch.py (during parallel phase)
def _request_preview(self, batch, system_prompt):
    backend = _resolve_backend()  # reads env / settings
    if backend == "web":
        return request_preview_http(...)
    else:
        return request_preview(...)  # Tk named-pipe path
```

After Tk removal, the dispatch goes away and only `request_preview_http` remains.

## 3. Event topology

### 3.1 Events table schema

In `core/memory.sqlite`:

```sql
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    batch_id TEXT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    emitted_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);

CREATE INDEX IF NOT EXISTS idx_events_run_emitted
    ON events (run_id, event_id);

CREATE INDEX IF NOT EXISTS idx_events_kind
    ON events (kind);
```

`payload_json` is the same shape as today's `GuiEvent.payload` dict — JSON-serialized.

### 3.2 New EventPublisher (replaces EventQueueBridge)

`bgs_translator/core/event_publisher.py` (new module, replaces `event_queue.py` over time):

```python
from __future__ import annotations
import json
import sqlite3
from dataclasses import asdict
from typing import Any

import httpx

from bgs_translator.config import paths
from bgs_translator.core.event_queue import GuiEvent  # dataclass kept

class EventPublisher:
    """Cross-process event publisher: sqlite-as-truth + best-effort HTTP push.

    Replaces the process-local Queue-based EventQueueBridge.
    """

    def __init__(
        self,
        db_path: str | None = None,
        gui_url: str | None = None,
        gui_secret: str | None = None,
    ) -> None:
        self._db_path = db_path or str(paths.memory_db_path())
        self._gui_url = gui_url
        self._gui_secret = gui_secret

    def emit(self, event: GuiEvent) -> None:
        """Write event to sqlite (canonical); fire-and-forget HTTP push to GUI."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO events (run_id, batch_id, kind, payload_json) VALUES (?, ?, ?, ?)",
                (
                    event.run_id or "",
                    event.batch_id,
                    str(event.kind),
                    json.dumps(event.payload, ensure_ascii=False),
                ),
            )
            conn.commit()
        if self._gui_url and self._gui_secret:
            try:
                httpx.post(
                    f"{self._gui_url}/internal/events",
                    json={
                        "kind": event.kind,
                        "run_id": event.run_id,
                        "batch_id": event.batch_id,
                        "payload": event.payload,
                    },
                    headers={"Authorization": f"Bearer {self._gui_secret}"},
                    timeout=1.0,  # short — best-effort
                )
            except httpx.HTTPError:
                pass  # WS reconcile via sqlite poll handles the gap

def get_publisher() -> EventPublisher:
    """Return a process-singleton publisher configured from environment."""
    # Implementation: lazy-init from gui.port + gui.secret if present
    ...
```

`BatchRunner` change: replaces `bridge.emit(GuiEvent(...))` with `publisher.emit(GuiEvent(...))`. The `GuiEvent` dataclass stays — only the bridge implementation changes.

### 3.3 GUI server event reconciliation

`bgs_translator/web/events.py`:

```python
from __future__ import annotations
import asyncio
import sqlite3
from collections.abc import AsyncIterator
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

_connected_ws: set[WebSocket] = set()

async def broadcast_ws(message: dict[str, Any]) -> None:
    """Broadcast to all live WS connections; drop dead ones."""
    dead: list[WebSocket] = []
    for ws in _connected_ws:
        if ws.application_state != WebSocketState.CONNECTED:
            dead.append(ws)
            continue
        try:
            await ws.send_json(message)
        except (asyncio.CancelledError, RuntimeError):
            dead.append(ws)
    for ws in dead:
        _connected_ws.discard(ws)

async def replay_events_from_sqlite(
    db_path: str,
    run_id: str,
    since_event_id: int = 0,
) -> AsyncIterator[dict[str, Any]]:
    """Yield events from sqlite for the given run, after the given event_id.

    Used by the browser-side reconcile on (re)connect:
      GET /api/runs/{run_id}/events?since=<last_seen_event_id>
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT event_id, run_id, batch_id, kind, payload_json, emitted_at
              FROM events
             WHERE run_id = ? AND event_id > ?
             ORDER BY event_id ASC
            """,
            (run_id, since_event_id),
        )
        for row in cursor:
            yield {
                "event_id": row[0],
                "run_id": row[1],
                "batch_id": row[2],
                "kind": row[3],
                "payload": row[4],  # caller can json.loads if needed
                "emitted_at": row[5],
            }
```

`bgs_translator/web/api/events.py`:

```python
@router.post("/internal/events")
async def push_event(
    event: dict[str, Any],
    _auth: None = Depends(require_shared_secret),
) -> dict[str, Any]:
    """Fire-and-forget push from CLI runner. Just forwards to WS broadcast."""
    await broadcast_ws({"kind": "event", **event})
    return {"ok": True}

@router.get("/api/runs/{run_id}/events")
async def get_events(
    run_id: str,
    since: int = 0,
    _auth: None = Depends(require_shared_secret),
) -> list[dict[str, Any]]:
    """Browser reconcile from sqlite."""
    db_path = str(paths.memory_db_path())
    return [
        evt async for evt in replay_events_from_sqlite(db_path, run_id, since)
    ]
```

### 3.4 Why two channels (HTTP push + sqlite poll)

- **HTTP push** (best-effort, 1s timeout): low-latency notify-on-emit. Drives the live-update feel.
- **Sqlite-as-truth**: every emit is durable. Browser reconnects always catch up. Subscribers can rebuild state from scratch by replaying events.

Per oracle's review: **never treat the event stream as source of truth.** Always reconcile from sqlite on connect / reconnect / suspicion.

### 3.5 Browser-side wiring (in tabs)

```javascript
// in NiceGUI page setup or shared.js
const ws = new WebSocket(`ws://${location.host}/ws`);
let lastEventId = 0;

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.kind === "event") {
    handleEvent(msg);
    if (msg.event_id) lastEventId = Math.max(lastEventId, msg.event_id);
  }
};

ws.onclose = () => {
  // reconcile gap, then reconnect
  fetch(`/api/runs/${currentRunId}/events?since=${lastEventId}`)
    .then(r => r.json())
    .then(events => events.forEach(handleEvent))
    .finally(() => setTimeout(reconnect, 1000));
};
```

NiceGUI auto-wires WS for `@ui.refreshable` patterns; this manual JS goes only into tabs that subscribe to live runs (Batches, Prompt, Logs).

## 4. UI architecture

### 4.1 Module layout

```
bgs_translator/
  web/
    __init__.py
    app.py                  # uvicorn entry, theme injection, route registration
    security.py             # require_shared_secret dependency
    events.py               # broadcast_ws, replay_events_from_sqlite
    api/
      __init__.py
      preview.py            # POST /api/preview/request and respond
      events.py             # POST /internal/events, GET /api/runs/{id}/events
      runs.py               # GET /api/runs, GET /api/runs/{id}
      projects.py           # GET /api/projects, POST /api/projects
      entries.py            # GET /api/entries (filter, paginate), POST /api/entries/{id}
      profiles.py           # CRUD + probe + activate + set-key
      glossary.py           # per-scope CRUD
    pages/
      __init__.py
      shell.py              # the root page: header + nav + theme switcher
      project.py            # @ui.page("/project")
      entries.py            # @ui.page("/entries")
      batches.py            # @ui.page("/batches") — drives WS subscribe
      prompt.py             # @ui.page("/prompt") — drives WS subscribe + approve UI
      profiles.py           # @ui.page("/profiles")
      glossary.py           # @ui.page("/glossary")
      logs.py               # @ui.page("/logs")
    components/
      __init__.py
      tab_nav.py            # shared top nav widget
      empty_state.py        # replacement for Tk EmptyStatePanel
      cost_chip.py          # status-bar cost indicator
      preview_request_card.py
      glossary_table.py
      entry_detail.py       # vertical split source/dest — fixes Bug D
    themes/
      amber.css
      green.css
      mono.css
      base.css              # shared resets
    static/
      fonts/                # VT323, Cascadia Mono, etc.
      img/                  # any logo / SVG
    i18n/
      loader.py             # gettext loader for *.po files
```

### 4.2 Theme injection

```python
# in web/app.py
from nicegui import app, ui

def setup_theme(theme_name: str = "amber") -> None:
    ui.add_head_html(
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2?family=VT323&display=swap">'
    )
    ui.add_css(_read_theme_file("base.css"), shared=True)
    ui.add_css(_read_theme_file(f"{theme_name}.css"), shared=True)
    ui.query("body").classes(f"bg-black text-amber-400 font-mono theme-{theme_name}")
    ui.colors(primary="#FFB000")

def _read_theme_file(name: str) -> str:
    path = Path(__file__).parent / "themes" / name
    return path.read_text(encoding="utf-8")
```

### 4.3 Tab nav as a single shared widget

```python
# in web/components/tab_nav.py
from nicegui import ui

_TABS = [
    ("project", "项目 / Project"),
    ("entries", "条目 / Entries"),
    ("batches", "批次 / Batches"),
    ("prompt", "提示词 / Prompt"),
    ("profiles", "档案 / Profiles"),
    ("glossary", "术语表 / Glossary"),
    ("logs", "日志 / Logs"),
]

def render_tab_nav(active: str) -> None:
    with ui.row().classes("gap-2 border-b border-amber-700"):
        for key, label in _TABS:
            classes = "tab-active" if key == active else "tab-inactive"
            ui.link(label, target=f"/{key}").classes(classes).mark(f"tab-{key}")
```

### 4.4 NiceGUI mounting on FastAPI

```python
# in web/app.py
from fastapi import FastAPI
from nicegui import app as nicegui_app, ui

from bgs_translator.web.api import preview, events, runs, projects, entries, profiles, glossary

fastapi_app = FastAPI()
fastapi_app.include_router(preview.router)
fastapi_app.include_router(events.router)
fastapi_app.include_router(runs.router)
# ... etc.

# Mount NiceGUI UI pages onto the FastAPI app
ui.run_with(
    fastapi_app,
    mount_path="/",
    storage_secret=_load_storage_secret(),
)
```

Single uvicorn process serves both `/` (UI) and `/api/*` (REST).

## 5. Playwright integration

### 5.1 Fixture

`tests/web_e2e/conftest.py`:

```python
from __future__ import annotations
import os
import subprocess
import time
import socket
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, sync_playwright

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="session")
def gui_server(tmp_path_factory: pytest.TempPathFactory):
    """Start a NiceGUI server in a subprocess; yield (url, secret); teardown on session end."""
    home = tmp_path_factory.mktemp("bgs-home")
    os.environ["BGS_MODDING_SUPERPOWERS_HOME"] = str(home)
    port = _free_port()
    proc = subprocess.Popen(
        ["python", "-m", "bgs_translator.web.app", "--port", str(port), "--no-open"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    # wait for /healthz
    for _ in range(50):
        try:
            if httpx.get(f"{url}/healthz", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("GUI server did not start in time")
    secret = (home / ".bgs-modding-superpowers" / "translator" / "gui.secret").read_text().strip()
    yield (url, secret)
    proc.terminate()
    proc.wait(timeout=5)

@pytest.fixture
def page(gui_server) -> Page:
    url, _secret = gui_server
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(url)
        yield page
        browser.close()
```

### 5.2 Selector convention

All Playwright selectors go through `data-marker` attributes set by `.mark("<id>")` in NiceGUI. Examples:

```python
# in a test
page.get_by_test_id("tab-prompt").click()
page.get_by_test_id("btn-approve-batch").click()
page.get_by_test_id("field-api-key-value").fill("sk-fake")
```

The `get_by_test_id` helper maps to `[data-marker="..."]` by configuring `playwright-pytest`'s `testid_attribute`:

```python
# in conftest.py
@pytest.fixture(scope="session", autouse=True)
def _configure_testid():
    from playwright.sync_api import sync_playwright
    # NiceGUI uses data-marker, not data-testid
    # configure once at session start
    ...
```

Full marker naming list is in `03-acceptance.md` §3.

### 5.3 Agent-self-verification flow

After the rewrite is complete, a typical UI-change cycle becomes:

1. Agent makes the code change.
2. Agent runs `pytest tests/web_e2e/ -k <relevant>` to check.
3. If fails, agent inspects via `chrome_devtools_take_snapshot` against `http://127.0.0.1:<port>` from a parallel browser session.
4. Agent diffs the snapshot against expected, iterates.
5. No human round-trip required for verification.

This is the **primary success criterion** of the rewrite per `00-spec.md` §9.

## 6. Backend module classification (per oracle)

Repeats from spec for traceability:

| Module | Classification | Action |
|---|---|---|
| `pipeline/runner.py` | REUSE-AS-IS | Just point `bridge.emit` at new `EventPublisher`. |
| `pipeline/clients/*`, `validator.py`, `retry.py`, `batcher.py`, `planner.py` | REUSE-AS-IS | Zero change. |
| `core/memory.py` | EXTEND | Add `events` table CREATE + helpers. |
| `core/event_queue.py` | DEPRECATE-IN-PLACE | Keep `GuiEvent` dataclass + `GuiEventKind` enum. Drop `EventQueueBridge` class at Tk removal. |
| `core/ipc.py` | DEPRECATE-IN-PLACE | Used only by `--backend tk` after Phase 1 lands. Delete at Tk removal. |
| `core/runtime_pid.py` | EXTEND | Add `is_web_gui_alive()` that checks `gui.port` + healthz. Keep `is_gui_alive()` for backward compat. |
| `cli/batch.py` | ADAPT MINIMAL | Add `_resolve_backend()` dispatch in `_PreviewingLLMClient._request_preview`. |
| `cli/app.py` | EXTEND | Add `--backend tk|web` flag to `gui` command. |
| `kb/`, `parsers/`, `output/`, `sst/`, `config/`, `observability/` | REUSE-AS-IS | Zero change. |
| `gui/*`, `tests/gui/*` | DELETE AT CUT-OVER | Untouched during parallel phase. |

## 7. Decision log (locked-in by this doc)

| # | Decision | Rationale |
|---|---|---|
| D-1 | Framework: NiceGUI (not HTMX+Alpine). | Python single-source, FastAPI-native, `.mark()` for Playwright, 30-50% fewer LOC vs Tk; per librarian-alpha + librarian-beta + user signoff. |
| D-2 | Two-process topology (GUI server + transient CLI worker). | Restart isolation; matches user mental model; avoids blocking uvicorn event loop on LLM I/O. |
| D-3 | Sqlite-as-truth event log + HTTP push fan-out. | Per oracle: events as notifications, sqlite as canonical. Fixes Bug C structurally. |
| D-4 | Shared-secret auth between CLI and GUI; localhost-only. | Cheap, sufficient for single-user single-machine threat model. |
| D-5 | Default browser mode (`native=False`). | Playwright clean access. `native=True` reserved as fallback. |
| D-6 | Theme via CSS injection (amber.css / green.css / mono.css). | Decouples from Tk widget hacks; CSS is more flexible. |
| D-7 | `.mark()` data-marker naming convention (see §5.2). | Stable Playwright selectors; no class-name churn. |
| D-8 | `xtl gui --backend tk|web` dispatch during parallel phase. | Reversible; Tk fallback during transition; flag removed at cut-over. |
| D-9 | Tk deleted (not deprecated long-term) once §6 of `00-spec.md` is satisfied. | User directive; no permanent dual-tree. |
| D-10 | `events` table lives in `memory.sqlite` (decision deferred from OQ-2). | Single backup target; row volume is manageable. **Override later if events-table contention with translation writes becomes measurable.** |

---

**Next document:** `02-phases.md` — phase-by-phase implementation breakdown.
