# bgs-translator Web Rewrite — Corrections (Pre-Execution)

> **Status**: Mandatory corrections from oracle's read-only adjudication pass 2026-06-08.
> **Effect**: these overrides take precedence over the corresponding sections in `01-architecture.md`, `02-phases.md`, `03-acceptance.md`, and `00-spec.md` where they conflict.
> **Why a separate file**: lower-friction errata pattern; the inline files stay readable, the audit trail of "what oracle flagged + how we addressed it" is preserved here.

---

## C-1 (HARD) — Event database path is per-project, not global

**Conflicts with**: `01-architecture.md` §3.2 (EventPublisher init), §3.3 (replay query), the `_load_event_db_path()` placeholder in `web/api/events.py`.

**Problem**: the architecture doc references `paths.memory_db_path()` (singular, global). The current backend uses **per-project** `memory.sqlite` files under `~/.bgs-modding-superpowers/translator/projects/<project>/memory/memory.sqlite`. A global publisher would land events in the wrong db, hide history across projects, or silently corrupt.

**Correction**:

1. `EventPublisher.__init__` takes a `project: str` argument, not `db_path`:

   ```python
   class EventPublisher:
       def __init__(
           self,
           project: str,
           gui_url: str | None = None,
           gui_secret: str | None = None,
       ) -> None:
           self._project = project
           self._db_path = str(paths.project_root(project) / "memory" / "memory.sqlite")
           self._gui_url = gui_url
           self._gui_secret = gui_secret
   ```

2. `get_publisher()` becomes `get_publisher(project: str)`. Callers (i.e. `BatchRunner.__init__`) thread the project name through.

3. The GUI server reconcile endpoint becomes:

   ```
   GET /api/projects/{project}/runs/{run_id}/events?since=<id>
   ```

   not `/api/runs/{run_id}/events`. The project is the disambiguator.

4. The `events` table CREATE goes into each project's memory.sqlite during `init_memory_db()`. Same schema; no global table.

5. The HTTP push payload carries `project`:

   ```json
   {"kind": "...", "project": "ryos-zhcn", "run_id": "...", "batch_id": "...", "payload": {...}}
   ```

   so the GUI server can route the WS broadcast with project context.

**Test impact**: Phase 1 acceptance gets one more item:

- [ ] Event publisher rejects cross-project writes: instantiating `EventPublisher(project="A")` and emitting events does NOT land in project B's memory.sqlite. Verify via two-project synthetic run.

---

## C-2 (HARD) — Preview pending key is composite, not just batch_id

**Conflicts with**: `01-architecture.md` §2.1 wire protocol, §2.3 reference implementation, `03-acceptance.md` §2 Phase 3 "Concurrent runs" item.

**Problem**: `batch_id` UUIDs are generated per plan_batches call, but if the user runs the same plan twice (replan + rerun against partially-translated memory), or runs two different plans concurrently with overlapping batches, the bare-`batch_id` key in `_pending` collides. First wins; second's POST hits a stale pending or 409 unexpectedly.

**Correction**:

1. The `_pending` map keys on a tuple `(run_id, batch_id)`:

   ```python
   _pending: dict[tuple[str, str], tuple[PreviewRequest, asyncio.Future[dict[str, Any]]]] = {}
   ```

2. The HTTP routes become:

   ```
   POST /api/preview/request               # body carries run_id + batch_id; server keys on the tuple
   POST /api/preview/respond/{run_id}/{batch_id}    # both in path
   ```

3. The browser uses `(run_id, batch_id)` from the WS event when constructing its respond URL.

4. The CLI `request_preview_http(...)` signature already includes `run_id` (per `01-architecture.md` §2.3 wire protocol); no change there.

5. WS broadcast messages carry both: `{"kind": "preview.opened", "run_id": "...", "batch_id": "...", ...}`.

**Test impact**: replace the Phase 3 "concurrent runs" acceptance test with a more precise:

- [ ] Two parallel synthetic runs (different `run_id`, identical plan-generated `batch_id` distribution) → both previews appear; approving run A's batch 1 does NOT resolve run B's batch 1; each is independently waited on.

---

## C-3 (HARD) — Missing parity tasks in Phases 3, 4, and a new phase for Bug B

**Conflicts with**: `02-phases.md` Phase 3 (Prompt tab parity) and Phase 4 (Project + Batches tab parity); cut-over criteria in `00-spec.md` §6.

### C-3.1 Phase 3 additions — Prompt tab full parity

Add to Phase 3 task list:

- [ ] **3.10** Implement planned-prompt browsing: when no live preview is active, the Prompt tab lists batches from all recent plans in the project's `batches/*/plan.json` files. User can select a batch from the dropdown and view its system prompt + glossary subset + DNT — but cannot approve (no `_action_row`). Mirror Tk `PromptTab._load_plans()` + `render_prompt_for_batch()` semantics on the web surface.
- [ ] **3.11** Implement plan-watcher: a server-side filesystem watcher on `<project>/batches/*/plan.json`. On change, server broadcasts WS message `{"kind": "plans.changed", "project": "..."}`; browser refreshes the dropdown.
- [ ] **3.12** Implement prompt-preview-required setting persistence: read on tab load from `settings.behavior.prompt_preview_required`; write on toggle via `POST /api/settings/behavior/prompt_preview_required`. This was UX 5 in Q3; needs a web-side equivalent.
- [ ] **3.13** Implement side-panel render-or-hide (UX 10 from Q3): if active batch has empty `glossary_subset`, hide the glossary panel entirely; same for DNT.

### C-3.2 Phase 4 additions — Project tab Create dialog + Batches Cancel

Add to Phase 4 task list:

- [ ] **4.9** Implement Create-project dialog: web equivalent of Tk `ProjectTab` create flow. `POST /api/projects` with `{name, game, register, register_default, ...}`. Mirror Tk's `xtl project init` semantics. Dialog fields per the existing Tk impl.
- [ ] **4.10** Implement Cancel-run action: `POST /api/runs/{run_id}/cancel` writes the `cancel.requested` marker file (same path Tk's `xtl batch cancel` uses). Browser shows confirmation. Marker file inspection by runner stays unchanged.
- [ ] **4.11** Implement Reload-from-disk action for projects: `POST /api/projects/{name}/reload` — rescans `project.toml`, recomputes derived stats. Equivalent to Tk's reload behavior.

### C-3.3 New: Bug B investigation phase

Add a new phase between Phase 0 and Phase 1 (or fold into Phase 1 if scope budget allows):

**Phase 1A — Bug B (Glossary collector) backend fix**

This was identified in the handoff as backend-only and the oracle confirmed "not solved by UI rewrite". Cut-over §6.2 makes it a prerequisite. So fix it before Phase 4 lands Glossary parity tests.

Tasks:
- [ ] **1A.1** Diagnose `GlossaryComposer.collect_for_batch` in `bgs_translator/kb/glossary.py`. Verify it reads all 4 scopes (vanilla / mod / player / do_not_translate) and that the user's player + DNT KB pack registrations actually resolve.
- [ ] **1A.2** Compare actual plan `glossary_subset` vs expected entries from `bgs_kb_query` against the user's registered packs. Identify the dropping step.
- [ ] **1A.3** Fix the collector. Add unit tests in `tests/kb/test_glossary_collector.py` covering all 4 scopes + mixed-pack cases.
- [ ] **1A.4** Re-plan a real batch with the fix; verify glossary_subset is no longer 1-entry-only.
- [ ] **1A.5** Commit: `fix(kb): glossary collector includes all scopes (closes Bug B)`.

Acceptance: a plan against `ryos-zhcn` shows ≥ 3 entries in `glossary_subset` per batch (or matches the user's registered entry count, whichever is larger).

Cost: ~0.5 dev-day. Total project estimate becomes ~10 dev-days raw, ~13 with buffer.

### C-3.4 Bug E fix in Phase 8 or earlier

Bug E (game_lore CLI slot collision) gets a small fix:

Add to Phase 8 or split into Phase 0:

- [ ] **8.9** Split `--game-lore` CLI flag into `--game-lore-world` (short title, default = game name) and `--game-lore-summary` (long descriptive paragraph, default = "" or game name). Update `cli/batch.py:plan_batch` to pass them to separate `game_lore_world` and `game_context_lore_summary` prompt slots. Document both flags.

Cost: ~30 minutes.

---

## C-4 (MEDIUM) — Browser auth model needs explicit spec

**Conflicts with**: `01-architecture.md` §2.1 (wire protocol) and §1.4 (shared secret) — neither explains how browser JS receives the secret without sending it from server in plaintext.

**Correction (chosen design)**:

The shared-secret is set as an **HTTP-only same-origin cookie** by the GUI server on first request:

```python
# in web/security.py
async def issue_browser_cookie(response: Response) -> None:
    response.set_cookie(
        "bgs_session",
        _load_gui_secret(),
        httponly=True,
        secure=False,  # localhost only
        samesite="strict",
        max_age=86400,
    )
```

Browser-side `fetch()` calls include `credentials: "same-origin"`. The `require_shared_secret` dependency accepts EITHER the `Authorization: Bearer ...` header (used by the CLI worker) OR the `bgs_session` cookie (used by the browser):

```python
def require_shared_secret(
    authorization: str | None = Header(None),
    bgs_session: str | None = Cookie(None),
) -> None:
    expected = _load_gui_secret()
    if authorization == f"Bearer {expected}":
        return
    if bgs_session == expected:
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED)
```

**Test impact**: add to Phase 2 acceptance:

- [ ] Browser cookie is set on first GET `/`; subsequent POSTs from same browser succeed without manual auth headers.
- [ ] Cookie has `httponly=true`, `samesite=strict`, no `secure` flag (localhost).
- [ ] A second browser without the cookie that POSTs to `/api/preview/respond/...` gets 401.

---

## C-5 (HIGH risk) — Silent provider dispatch on no_gui must be hard-blocked when preview_required=true

**Conflicts with**: `01-architecture.md` §2.1 (timeout / no_gui semantics describing fallback to original prompt) and `03-acceptance.md` §5 risk register.

**Problem**: when the user has `behavior.prompt_preview_required = true` AND the GUI is unreachable, the current Tk code (and the proposed web code) falls back to dispatching the LLM call with the original prompt and a stderr warning. This silently spends money without user oversight, exactly when the user has asked for oversight.

**Correction**:

In `cli/batch.py:_PreviewingLLMClient._request_preview` (web path AND Tk path):

```python
def _request_preview(self, batch, system_prompt):
    response = self._dispatch_request(batch, system_prompt)
    op = response.get("op", "approved")
    settings = load_settings()
    if op in ("no_gui", "timeout", "transport_unavailable"):
        if settings.behavior.prompt_preview_required:
            # HARD BLOCK
            log.error(
                "Preview required but GUI unreachable (op=%s). Aborting run.",
                op,
            )
            raise RuntimeError(
                f"prompt_preview_required=true but GUI is unreachable (op={op}). "
                "Start the GUI (`xtl gui`) or set behavior.prompt_preview_required=false."
            )
        # else: fall through to original-prompt dispatch as before
    return response
```

**Acceptance test addition** (Phase 3):

- [ ] `test_preview_required_true_with_no_gui_aborts_run` — start synthetic batch with `prompt_preview_required=true` and no GUI; verify run fails with the abort message and NO LLM call is dispatched.

This addresses oracle's high-risk flag and turns a silent footgun into a loud one.

---

## C-6 (LOW) — Wording correction in `01-architecture.md` §3.5

**Conflicts with**: `01-architecture.md` §3.5 "browser-side wiring" — the wording suggests reconciling state by replaying events.

**Correction**: replace the phrase

> "rebuild state from scratch by replaying events"

with

> "reconcile UI state from canonical sqlite tables (`runs`, `batches`, `units`) on (re)connect; events are notifications that drive incremental updates but never the canonical state."

This nails oracle's anti-pattern guard: events are NOT source of truth. Sqlite is.

---

## C-7 (MEDIUM) — Cut-over criteria additions

**Conflicts with**: `00-spec.md` §6.

Add to §6.1 Feature parity checklist:

- [ ] **Create-project dialog** works on the web surface (covers C-3.2).
- [ ] **Cancel-run action** works on the web surface (covers C-3.2).
- [ ] **Reload-from-disk action** for Project tab works on the web surface (covers C-3.2).
- [ ] **Planned-prompt browsing** in Prompt tab works on the web surface (covers C-3.1).
- [ ] **Plan-watcher** auto-refreshes the Prompt tab batch dropdown (covers C-3.1).
- [ ] **prompt_preview_required setting** persists across browser sessions (covers C-3.1).
- [ ] **Bug E split CLI flags** (`--game-lore-world` / `--game-lore-summary`) shipped (covers C-3.4).

Add to §6.2 Acceptance parity checklist:

- [ ] **Bug B fixed and verified** — a plan against `ryos-zhcn` shows the full expected glossary subset, not 1 entry.
- [ ] **No-GUI-with-preview-required hard-block test passes** — see C-5.

---

## C-8 (HIGH) — Risk register additions

Add to `03-acceptance.md` §5 High risks:

| Risk | Mitigation | Phase |
|---|---|---|
| Per-project event DB path is mis-configured at runner init time → events land in wrong project's memory.sqlite | C-1: pass `project` explicitly to `EventPublisher.__init__`; cross-project test in Phase 1 acceptance | 1, 4 |
| Browser tries to POST without same-origin cookie (e.g. opened via wrong scheme) → 401 | C-4: cookie-or-header dual auth; document browser MUST be opened via the URL the server printed | 2, 3 |
| Silent provider dispatch when preview_required + no GUI → wasted money | C-5: hard-block raises RuntimeError; test in Phase 3 | 3, 10 |
| Same `batch_id` reused across two concurrent runs collides on `_pending` | C-2: composite `(run_id, batch_id)` key; concurrent-runs test in Phase 3 | 3 |

---

## C-9 (MEDIUM) — README update

**Action**: After applying C-1..C-8, update `README.md` document version table:

```
| 2026-06-08 | Initial draft. Approved by user.                      |
| 2026-06-08 | Corrections from oracle adjudication (C-1..C-9).      |
```

And add a one-liner near the top of README pointing at this corrections doc:

> Before executing Phase 0, read `04-corrections.md`. It contains mandatory pre-flight corrections from oracle's adjudication pass.

---

## Honest summary

Oracle's adjudication identified 3 hard pre-execution blockers (DB path scoping, preview key composite, missing parity tasks), 2 medium gaps (browser auth, cut-over additions), 1 high-risk silent-spend hole (C-5), and minor wording. None are framework-choice problems; all are first-pass plan completeness issues, typical of writing a 2,400-line doc in one shot.

After applying C-1..C-9, the plan is execution-ready. A fresh engineer can pick up Phase 0 and ship through Phase 12 without re-deriving major architectural decisions. The total estimated cost shifts from ~9.25 raw days to ~10 raw days (~13 with buffer) because Phase 1A adds Bug B investigation upfront.

Net assessment: the rewrite is still a good idea. The corrections are the kind of detail that surfaces in a thorough adjudication and gets fixed cheap before code is touched. Plan-doc revision is what the writing-plans skill exists to enable.
