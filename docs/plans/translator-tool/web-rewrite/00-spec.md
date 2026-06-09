# bgs-translator Web Rewrite — Specification

> **Audience:** the engineer (human or agent) who will implement and ship the NiceGUI-based control panel that replaces the current Tk GUI.
> **Status:** APPROVED 2026-06-08 by project owner.
> **Decision pre-history:** see `D:\awesome-bgs-mod-master\.opencode\artifacts\web-rewrite-research\` (3 lens consultation: librarian-alpha NiceGUI, librarian-beta HTMX+Alpine, oracle architecture).
> **Predecessor:** the Tk control panel under `tools/bgs-translator/bgs_translator/gui/` (kept running during transition; deleted on cut-over).

---

## 1. Intent

Replace the Tk-based control panel of `bgs-translator` with a NiceGUI-powered browser-rendered surface so that:

1. The agent driving the project (an LLM in OpenCode) can self-verify any UI change via Playwright / Chrome DevTools MCP — closing the verification loop that Tk's invisible-to-Playwright surface forces back through the human.
2. The cross-process event topology bug that silently broke Bug 5 (the `EventQueueBridge` process-local singleton problem; see `HANDOFF-POST-LIVE-TEST.md` Bug C) is structurally fixed by construction — the GUI server and the CLI worker communicate over HTTP + WebSocket, not via an in-process queue that lives in only one of the two.
3. The amber-CRT retro aesthetic is preserved (CSS, not Tk widget contortions).
4. Long-session UI lag on the user's Windows machine is eliminated.

## 2. Hard contract: Tk gets deleted

This is the single most load-bearing clause. **Tk is not a long-term parallel surface.** It exists during the migration only as a working fallback so the user is not blocked while the web path is built. The moment the web path reaches **feature parity + acceptance parity** (defined in §6), the Tk tree under `tools/bgs-translator/bgs_translator/gui/` is **deleted entirely**, along with:

- All Tk tests under `tools/bgs-translator/tests/gui/`
- The `xtl gui` Typer command's `--backend tk` flag (web becomes the only backend)
- The `pythonw + stdio-redirect-wrapper` launch helper documented in `HANDOFF-POST-LIVE-TEST.md`
- All Tk-specific config keys in `bgs_translator/config/settings.py` (window_width, window_height, the `ui.theme` Tk-mapped values, etc.)
- The named-pipe `IPCServer` in `bgs_translator/core/ipc.py` (web flow does not use it)
- The `EventQueueBridge` in `bgs_translator/core/event_queue.py` (web flow replaces its semantics with sqlite + WS)

The Tk removal commit's title must be: `refactor(gui): remove Tk control panel; web is the only surface`. It is the marker of migration completion.

**2026-06-09 scope note:** Phase 11 cut-over is authorized and ships `xtl gui` as the browser default while keeping `xtl gui --backend tk` as an opt-in fallback. The project owner explicitly moved Tk deletion out of the current construction/goal scope. Do not delete Tk, Tk tests, `core/ipc.py`, or `--backend tk` as part of this Phase 11 cut-over.

## 3. Non-goals

These are out of scope and stay that way through this rewrite:

- **Remote access.** The web server binds to `127.0.0.1` only. No LAN, no internet, no auth more elaborate than a shared-secret check between CLI worker and GUI server. One user, one machine.
- **Multi-user / multi-tenancy.** The user is one human at one keyboard. Multiple browser tabs are tolerated but only one approves any given preview (first-POST-wins).
- **Browser application packaging (Electron-style).** Default mode is `native=False` — open a real browser tab. `native=True` (NiceGUI's PyWebView wrapper) is offered as a fallback if the user prefers a single-window experience, but is not the verification target.
- **Mobile / responsive layouts.** Desktop only. Min viewport 1024×600.
- **Replacement of any backend module** other than `core/event_queue.py` and `core/ipc.py`. `pipeline/`, `kb/`, `parsers/`, `output/`, `sst/`, `config/`, `cli/`, `core/memory.py`, `core/runtime_pid.py`, `observability/` all stay verbatim except for the IPC client swap in `cli/batch.py:_PreviewingLLMClient`.
- **New features that don't exist in Tk today.** This is a port + structural fix, not a feature push. New features are queued for after Tk removal.
- **Internationalization changes.** Existing `bgs_translator/gui/i18n/*.po` files carry over verbatim. Loader becomes server-side gettext.

## 4. Functional scope — what the web GUI must do

### 4.1 Seven-tab feature parity

The web GUI must offer functional equivalents of all seven Tk tabs. "Functional equivalent" means a user familiar with the Tk version can perform every existing workflow without consulting documentation. Aesthetics are restated (CSS-driven), not preserved pixel-perfect.

| Tab | Feature surface |
|---|---|
| Project | Project list, project detail card (game / register / cost-spent / units total), Create-project dialog, Reload-from-disk action |
| Entries | Filterable table (signature, field, status), Source/Dest detail pane, Mark-orphaned / Lock / Restore / Save-edit actions per entry, search box |
| Batches | Live run/batch progress (driven by event stream + sqlite reads), per-batch status, per-batch tokens/cost, Cancel-run action |
| Prompt | System prompt preview, Approve / Approve-all-remaining / Discard actions per pending preview, glossary-subset side panel, DNT side panel, preview-required toggle |
| Profiles | Profile list, Add/Edit profile dialog, Set-API-key dialog (read-only env var name, value-only input), Probe action, base-URL auto-strip helper, Activate action |
| Glossary | Per-scope tabs (vanilla, mod, player, DNT), Add-entry dialog (player/DNT only; vanilla/mod say the tool automatically maintains those read-only layers), filterable per-scope table |
| Logs | Recent-events stream, per-run log file viewer |

Each tab is implemented as one `@ui.page` route or one module under `bgs_translator/web/tabs/`. See `02-phases.md` for per-tab file targets.

### 4.2 Prompt approve handshake (the IPC-replacement surface)

The most architecturally load-bearing flow. The Tk version used a named pipe; the web version uses HTTP + WS as designed by oracle.

**CLI worker side** (`cli/batch.py:_PreviewingLLMClient`):

```python
# pseudo-code; canonical in 01-architecture.md
async def translate_batch(self, batch, system_prompt):
    response = await self._request_preview_http(batch, system_prompt)
    if response["op"] == "approved":
        return await self._inner.translate_batch(batch, response["prompt"])
    elif response["op"] == "discarded":
        return _discarded_response(batch)
    elif response["op"] in ("no_gui", "timeout"):
        return await self._inner.translate_batch(batch, system_prompt)
```

**GUI server side** (`bgs_translator/web/api/preview.py`):

```python
# pseudo-code; canonical in 01-architecture.md
@app.post("/api/preview/request")
async def request_preview(payload: PreviewRequest):
    future = asyncio.get_event_loop().create_future()
    _pending_previews[payload.batch_id] = (payload, future)
    await _broadcast_ws({"kind": "preview.opened", **payload.model_dump()})
    try:
        return await asyncio.wait_for(future, timeout=300.0)
    except TimeoutError:
        _pending_previews.pop(payload.batch_id, None)
        return {"op": "timeout"}

@app.post("/api/preview/respond/{batch_id}")
async def respond_preview(batch_id: str, payload: PreviewResponse):
    pending = _pending_previews.pop(batch_id, None)
    if pending is None:
        raise HTTPException(409, "no pending preview for batch_id")
    _, future = pending
    future.set_result(payload.model_dump())
    await _broadcast_ws({"kind": "preview.closed", "batch_id": batch_id})
    return {"ok": True}
```

This single handshake replaces ~300 LOC of named-pipe framing.

### 4.3 Event topology (the cross-process fix)

**Old model (broken in production):**
- `BatchRunner` calls `bridge.emit(...)` from CLI process.
- `EventQueueBridge` is a process-local singleton.
- GUI process has a different singleton.
- Events are lost across the process boundary.

**New model:**

1. `BatchRunner` continues to call `bridge.emit(...)`. The local function call stays the same.
2. The bridge implementation is replaced. The new bridge writes each emitted event to a sqlite `events` table (immediate fsync, see `01-architecture.md` for trade-offs) AND optionally POSTs to the GUI's `/internal/events` endpoint as fire-and-forget notification.
3. The GUI server subscribes to its own sqlite event log via a 200-500ms poll OR receives push from CLI's POST. WS broadcasts to all connected browser tabs.
4. Late-joining browser tabs query `GET /api/runs/{run_id}/events?since=<last_id>` to catch up.
5. **Critical rule (from oracle):** sqlite is the source of truth. Events are notifications. If the WS push is missed, the next `GET` to a tab will reconcile from sqlite.

This means every batch operation has two persistence calls instead of one (`INSERT INTO batches` + `INSERT INTO events`). The cost is small (sqlite is fast); the gain is "Bug 5 cannot fail silently again" — if the runner inserts to `batches`, the browser will see it on next reconcile even if the WS broadcast was missed.

### 4.4 Theme: amber-CRT preserved as CSS

- Global CSS injected via `ui.add_css(open('bgs_translator/web/themes/amber.css').read(), shared=True)`.
- VT323 / Cascadia Mono / IBM Plex Mono font stack injected via `ui.add_head_html('<link href="...VT323..." rel="stylesheet">', shared=True)`.
- Body classes: `ui.query('body').classes('bg-black text-amber-400 font-mono')`.
- Custom scrollbars via `::-webkit-scrollbar` rules in `amber.css`.
- Primary color: `ui.colors(primary='#FFB000')`.
- Title bar (custom under `native=True`, default browser chrome under `native=False`).
- Themes available: amber (default), green, mono. Same names as Tk version. Switched at runtime via `/api/theme` POST.

### 4.5 Playwright self-verification surface

Every interactive widget gets a `.mark('<stable-id>')` so Playwright tests can address it by `data-marker="<id>"` selector. Naming convention:

- Tab nav: `tab-{key}` — e.g. `tab-prompt`, `tab-entries`
- Action buttons: `btn-{verb}-{scope}` — e.g. `btn-approve-batch`, `btn-add-entry-player`
- Form fields: `field-{name}` — e.g. `field-api-key-value`, `field-glossary-source`
- Dialog roots: `dialog-{purpose}` — e.g. `dialog-set-api-key`, `dialog-add-entry`
- Table rows: `row-{table}-{id}` — e.g. `row-batches-{batch_id}`
- Status indicators: `status-{topic}` — e.g. `status-batch-progress`, `status-cost-total`

Per-component naming list lives in `03-acceptance.md` §3.

A Playwright fixture (`tests/web_e2e/conftest.py`) starts the GUI server on a random port, returns a `Page` pre-pointed at it. Tests under `tests/web_e2e/` are the acceptance harness; they replace the Tk `tests/gui/` tree at cut-over.

## 5. Strategy: parallel, flag-gated, then cut

```
Phase 0 (this spec).
Phase 1-7 (per 02-phases.md).
  Throughout: `xtl gui` defaults to Tk.
              `xtl gui --backend web` runs new NiceGUI server.
              Both code trees coexist.
              `pipeline/`, `kb/`, etc. stay shared.
Cut-over (when §6 criteria met):
  - Flip default: `xtl gui` opens web.
  - `--backend tk` becomes opt-in for one release.
  - Tk tree marked deprecated in README.
Removal (one release after cut-over OR immediately if user signs off):
  - Delete `bgs_translator/gui/`, `tests/gui/`, `core/ipc.py`, `core/event_queue.py`
  - Delete `--backend tk` flag.
  - Squash any straggler references.
  - Commit: `refactor(gui): remove Tk control panel; web is the only surface`.
```

Phase ordering and per-phase goals are in `02-phases.md`. Acceptance gates per phase are in `03-acceptance.md`.

## 6. Cut-over criteria (when Tk gets deleted)

Tk **may not** be deleted until **all** of the following hold simultaneously, demonstrably, and reproducibly:

### 6.1 Feature parity

- [ ] All 7 tabs in §4.1 are implemented on the web surface.
- [ ] Every Tk-version action listed in §4.1 has a working web equivalent.
- [ ] Every Tk-version modal dialog has a working web equivalent.
- [ ] Theme switching (amber / green / mono) works on the web surface.
- [ ] Language switching (en / zh-cn) works on the web surface.
- [ ] Set API key dialog has UX 7 invariant (env var name read-only).
- [ ] Glossary scope gating (UX 1) is enforced on the web surface.
- [ ] Entries detail pane has both source AND dest panels (Bug D from handoff — must be fixed on web port; not on Tk).

### 6.2 Acceptance parity — `把真实生产 scenario 都走一遍`

- [ ] Playwright test suite under `tests/web_e2e/` covers, at minimum, every flow listed in `03-acceptance.md` §4.
- [ ] All Playwright tests pass green from a single `pytest tests/web_e2e/ -v` invocation.
- [ ] A live batch run against a real LLM provider executes end-to-end against the web GUI: plan → preview → approve → dispatch → progress events stream → completion → cost-update settles → audit artifacts written. Documented evidence required under `.opencode/artifacts/web-rewrite-acceptance/round-N/`.
- [ ] The cross-process event topology fix is verified: an `xtl batch run` (CLI process) emits events that show up in the browser's Batches tab live. Bug C from `HANDOFF-POST-LIVE-TEST.md` is closed.
- [ ] Bug B (Glossary subset incomplete) is fixed on the backend (not GUI-related; this just needs to be done before Tk removal to prove the web port doesn't paper over it).

### 6.3 Performance parity

- [ ] First-byte response time of any tab navigation: ≤ 200ms on the user's machine.
- [ ] Event-to-render latency for batch progress: ≤ 300ms (sqlite write + WS broadcast + browser DOM update).
- [ ] Browser memory after 4 hours of idle session: ≤ 500 MB. (NiceGUI long-session leak mitigation: `message_history_length=0`, `reload=False`, minimal `ui.timer` usage.)
- [ ] No "stutter" reports from the user during a normal-density 10-batch run.

### 6.4 Operational

- [ ] User explicitly signs off in writing on cut-over (text in chat, captured in dev-log).
- [ ] Tk-removal commit is reviewed by `@oracle` (read-only adjudication, not approval gate).
- [ ] One full release cycle (or one full user workday, whichever is shorter) elapses between cut-over and removal so the user can flag regressions on `--backend tk` fallback.

If **any** criterion above fails, Tk stays.

**2026-06-09 scope note:** The four-hour browser memory check is running as a separate PowerShell monitor. Reviewing that result is outside the current cut-over scope unless the project owner brings it back in.

## 7. Anti-goals — what NOT to do

- ❌ Do not port Tk widget class structure 1:1. Each web tab is re-thought as either a server-rendered HTML page (NiceGUI's normal mode) or a thin reactive component. Tk's overrideredirect-and-custom-titlebar contortion does not survive.
- ❌ Do not keep `EventQueueBridge` as the canonical event channel. Replace with sqlite-backed event log + WS broadcaster. This is the structural fix for Bug C and is not optional.
- ❌ Do not run NiceGUI inside the CLI worker process. GUI = uvicorn server, CLI = transient worker. They communicate over HTTP.
- ❌ Do not lose the existing Pydantic models. `BatchPlan`, `Batch`, `MaskedUnit`, `GlossaryEntry`, `ProviderProfile`, `GuiEvent` carry over verbatim. The web layer renders them.
- ❌ Do not skip the Playwright test suite. This is the whole point of the migration — the agent must be able to self-verify any UI change.
- ❌ Do not attempt browser-based file dialogs. Replace with server-side directory listing API + browser-side path picker.
- ❌ Do not support remote browsers. Localhost only. No production deployment scenario.
- ❌ Do not begin Phase 1 implementation until this spec is signed off (already done 2026-06-08).
- ❌ Do not add a new feature during the rewrite. Port-only. New features queue for after Tk removal.

## 8. Risk register (high-level)

Full risks are in `03-acceptance.md`. The top-3 to know up front:

1. **Long-session memory leak** (NiceGUI issue #5803). Mitigation: `message_history_length=0`, `reload=False`, minimal `ui.timer`, daily restart for the user. Acceptable risk if mitigations hold; reassess if browser RAM > 500 MB after 4h idle.
2. **Multiple browser tabs racing approvals.** Mitigation: first-POST-wins on `/api/preview/respond/{batch_id}`; subsequent POSTs get HTTP 409. Other tabs see resolution via WS broadcast and grey out their approve UI.
3. **CLI worker crashes mid-approval.** Mitigation: GUI's `asyncio.Future` times out after 300s; stale-preview banner with explicit Discard button.

## 9. Success metric

- **Primary:** the agent can implement, change, and verify any UI tweak end-to-end without the user touching the keyboard for verification.
- **Secondary:** the user's perceived UI lag complaint is gone.
- **Tertiary:** `tools/bgs-translator/bgs_translator/gui/` no longer exists. The Tk-removal commit lands.

## 10. References

- `HANDOFF-POST-LIVE-TEST.md` — bug list and live-acceptance evidence that motivated this rewrite.
- `01-architecture.md` — concrete tech design (process layout, IPC, event bridge, theming, Playwright).
- `02-phases.md` — phase-by-phase implementation plan.
- `03-acceptance.md` — per-phase semantic acceptance + Playwright test list.
- `.opencode/artifacts/web-rewrite-research/nicegui-eval.md` — librarian-alpha framework eval.
- `.opencode/artifacts/web-rewrite-research/fastapi-htmx-alpine-eval.md` — librarian-beta alternative eval.
- `.opencode/artifacts/web-rewrite-research/architecture-review.md` — oracle architecture review.

## 11. Open questions (deliberately deferred)

These are intentionally NOT decided here; they will be settled at the relevant phase.

- **OQ-1.** Should the GUI server bundle uvicorn as a dependency, or import it on demand? (Decided at Phase 1.)
- **OQ-2.** Should the event-log table live in `memory.sqlite` or a separate `events.sqlite`? Trade-off: same-file simplifies backup; separate avoids contention with translation-memory writes. (Decided at Phase 2.)
- **OQ-3.** Should `--backend web` open the system default browser via `webbrowser.open`, or should it print the URL and let the user open it? (Decided at Phase 1.)
- **OQ-4.** When does Tk-version dev-log/changelog get a deprecation notice? (Decided at cut-over.)
- **OQ-5.** Should the Playwright fixture use `pytest-playwright` or hand-rolled? (Decided at Phase 1; default = `pytest-playwright`.)
