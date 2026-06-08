# Handoff — Post Live-Test (2026-06-08)

> **STATUS 2026-06-08 (post-Q1/Q2/Q3 + live acceptance round 1)**: Q1/Q2/Q3 landed (15 commits 3deff7f..ff5ec95). Plus `ccd68ff` for approve race. Live acceptance run executed (~$0.01) and surfaced more bugs that landed Tk-replacement decision; see "Live acceptance round 1 — open bugs" section below. Final test sweep before live: 312 passed, 3 skipped, 1 pre-existing flake (`test_drag_start_from_maximized_restores_with_proportional_cursor_anchor` — passes 3/3 in isolation, only fails under full-sweep Tk geometry contamination introduced in earlier commit `4a93ab2`). Ruff + mypy clean. Next decision = whether to rewrite GUI from Tk to a browser-rendered surface so the agent can self-verify via Playwright (see decision doc once written).

## Live acceptance round 1 — open bugs (2026-06-08)

User ran the GUI + a 67-item / 10-batch DeepSeek-via-OpenRouter live batch with full mod context (`plan_id=9bde9f04-bf3d-4d2c-be05-93aed9d2c90f`). Found:

| # | Severity | Bug | Status |
|---|---|---|---|
| A | HIGH (live blocker) | Approve action row hidden by `_focus_prompt_preview` → `refresh_for_batch` → `render_prompt_for_batch:142` race; CLI worker blocked in `IPC.wait()` forever. | **FIXED `ccd68ff`** with regression test (`tests/gui/test_app_prompt.py::test_preview_event_shows_approve_action_row`) |
| B | HIGH | Glossary subset in plan.json only carries 1 entry (`UC → 联殖`), DNT empty. User reports player + DNT glossary layers actually have content. Suggests `GlossaryComposer.collect_for_batch` or its scope filter is dropping entries, OR the user-pack registration is not resolving for `target_lang=zh-cn` + `scope=player`/`do_not_translate`. NOT investigated yet — user said "暂时先不管". | OPEN |
| C | HIGH | Batches tab still shows `[尚无运行]` mid-flight and after completion. Bug 5 fix (`d68661f`) added INSERT runs/batches + emit `run.start`/`batch.*`/`cost.update`, but events don't actually surface in the tab. Either runner not emitting after all, or `BatchesTab._on_event` filter / subscription broken, or `runs`/`batches` rows being written but tab reads stale snapshot. Needs diagnostic (sample memory.sqlite + bridge subscriber list + event_queue.drain trace). | OPEN |
| D | MEDIUM | Entries detail pane: only bottom 译/Dest half rendered; top 源/Source half missing. Q3 UX todo 4 (vertical PanedWindow split source/dest) implementation incomplete — observer-confirmed via screenshot 2026-06-08. | OPEN |
| E | LOW (cosmetic) | `cli/batch.py:plan_batch` passes same `--game-lore` value to both `game_lore_world` and `game_context_lore_summary` prompt slots → header text duplicated in sample_system_prompt. Should be two separate CLI args (`--game-lore-world` short title + `--game-lore` long summary). | OPEN |

### Live run evidence (`rn_<TBD>` from plan `9bde9f04`)
- Cost: ~$0.01 (DeepSeek via OpenRouter, exact)
- Item count: 67 MESG:DESC items in 10 batches
- All 10 batches approved (some via Approve-all-remaining)
- audit artifacts written under `batches/<run-id>/` (validates Q3 audit-write fix from prior round still holds)
- memory.sqlite `units.dest` populated (validates Bug 3 unit-update persistence still holds)
- `runs` / `batches` table state: NOT YET CAPTURED — needed for Bug C diagnosis next session

### Pending investigation order (when ready to resume on Tk surface)
1. Bug C — runs/batches table state + event_queue trace. **Oracle root-caused this during web-rewrite review**: `EventQueueBridge` singleton is process-local; `BatchRunner` runs in CLI process; GUI process has a different singleton; events never cross processes. Q1's `test_runner_persistence.py` passed because emit + drain were same-process in test. **Bug 5 fix is partial — INSERT-runs/batches works (shared sqlite), but emit-events is a no-op live until cross-process channel exists.** Will be naturally solved by web rewrite.
2. Bug B — KB user-pack resolution. Check `bgs_kb_status` for current pack registration, check `GlossaryComposer.collect_for_batch` scope dispatch, check `paths.user_packs_root()` actually resolves to user's player/DNT pack. **Oracle confirms this is a backend KB bug, NOT a UI bug — will NOT be solved by web rewrite.**
3. Bug D — `gui/tabs/entries_tab.py` PanedWindow assembly — Q3 designer likely added bottom pane but skipped top pane wiring. **Skipped — Tk dropping soon.**
4. Bug E — `cli/batch.py:plan_batch` split into `--game-lore-world` (string title) + `--game-lore-summary` (long lore text). **Apply in web port; skip on Tk path.**

### Run `rn_cdffc06ed3f2` actual outcome
- 67 items / 10 batches / $0.10 (3.5x previous because reasoning model used more tokens with rich Starfield context)
- 55 succeeded / 5 retried / **12 manual_review** / 0 cancelled
- 12 manual_review = Bug 4 (empty-completion gate) catching real failures — defense working as designed
- audit artifacts + memory.sqlite UPDATE confirmed (Bugs 3+4 fixes solid)
- runs/batches tables + GUI events: confirmed broken per Oracle's cross-process diagnosis

### Web rewrite decision (2026-06-08)

Three perspectives consulted (saved under `D:\awesome-bgs-mod-master\.opencode\artifacts\web-rewrite-research\`):
- `nicegui-eval.md` — librarian-alpha: NiceGUI strong fit, ~6–7 dev-days, FastAPI-native, `.mark()` for Playwright
- `fastapi-htmx-alpine-eval.md` — librarian-beta: HTMX+Alpine also good fit, ~3–5k LOC, standard web stack
- `architecture-review.md` — oracle: parallel migration strategy, first slice = Prompt approve handshake on synthetic, sqlite-backed event log + WS broadcast replaces process-local bridge

Decision pending user signoff on:
1. Framework choice: NiceGUI vs FastAPI+HTMX+Alpine
2. Migration strategy: parallel (recommended) vs cut-over
3. First slice scope: Prompt approve handshake (recommended) vs broader read-only slice

Once chosen → write spec + implementation plan under `docs/plans/translator-tool/web-rewrite/`.

### Why we are not fixing these immediately
User decided after this round that the Tk surface is the wrong substrate for continued iteration:
- Tk is laggy on the user's machine
- Agent cannot drive Tk (no Playwright equivalent; the agent depends on the user as the eyes-and-hands for every verification)
- The acceptance loop is asymmetric: 1 agent change requires 1 user-driven re-test round trip

Decision pending: **migrate the GUI surface to a browser-rendered control panel** so the agent can self-verify via Playwright / Chrome DevTools MCP. Spec + plan doc to be written if framework choice converges. See `docs/plans/translator-tool/web-rewrite/` (to be created) once architecture proposal is approved.

Context window almost full. Snapshot for next compaction loop. Pick up here.

## Branch state

```
feat/translator-tool
36ed93d fix(runner): bug 3 — persist + audit trail
d7dd3e2 fix(cli):    bug 1+2 — IPC warnings + real glossary reader
2420f87 fix(gui):    wire Chunk L.2 tabs + IPC/PID into app shell
+ commits from L.2 Fixer A/B/C/D + iter1-4 polish
```

Tests: 297 passed, 2 skipped. ruff + mypy clean.

## Live-test evidence (run `rn_b1b3ab2c5df5`)

- Cost: $0.008573 OpenRouter exact, DeepSeek `deepseek/deepseek-v4-pro` via OpenRouter-DeepSeek profile
- Plan: 71 items (MESG:FULL), 3 batches
- **All 71 dest non-empty this run** (last run 42/71 — empty-completion was transient, not deterministic)
- Translation quality samples (look correct): `Merchant's Scion → 商人子嗣`, `Engine Repairs → 引擎维修`, `Auction Find → 拍卖收获`, `Stolen Property → 赃物`, `Estate Sale → 遗产清售`
- Glossary entry `English → 星空` rendered into sample_system_prompt ✓ (Bug 2 fix verified)
- IPC handshake worked: 3 batches each pushed to GUI Prompt tab, user manually selected from dropdown, approved, dispatched ✓

## Audit-artifact verification

Per `<project>/batches/rn_b1b3ab2c5df5/`:

```
plan.json                                                    47 KB
system-prompt.md                                              0.8 KB
results.json                                                 52 KB
status.toml                                                   0.1 KB
validator-failures.jsonl                                     0 KB (clean)
responses/<batch>.raw.json + .normalized.json                3 × pairs
retries/                                                     empty
```

**Bug 3 fix actually works** — my earlier "audit missing" diagnostic was reading the wrong dir (`3c2dbb10...` is the PLAN dir; `rn_<hash>` is the RUN dir). Fixer P3's `36ed93d` is correct.

## Bugs — current state

### FIXED (verified live)

- **Bug 1** — IPC silent fallback. `cli/batch.py:_request_preview` now distinguishes `no_gui` / `transport_unavailable` / `timeout` and emits stderr. `pyproject.toml` declares `pywin32>=308; sys_platform == 'win32'`. Named pipe `\\.\pipe\bgs-translator-gui-<USERNAME>` confirmed listening. Commit `d7dd3e2`.
- **Bug 2** — Empty glossary stub. `cli/batch.py:87` now uses `KBGlossaryReader()` not `_EmptyGlossaryReader()`. User's player-pack entry renders into prompt. Commit `d7dd3e2`.
- **Bug 3** — Persistence + audit trail. `pipeline/runner.py` calls `core.memory.update_unit_translation()` + writes `responses/`, `results.json`, `status.toml`, `validator-failures.jsonl`. `cost_exact` source-truthful from `usage.cost` in OpenRouter response. Commit `36ed93d`.

### REMAINING (real, prioritized)

#### Bug 5 (HIGH) — Runner emits ZERO events to GUI event_queue; runs/batches tables ZERO INSERTs

User confirmed: GUI 批次 tab shows "[尚无运行] 请从CLI启动批次..." even mid-flight.

```
runs table:    0 rows
batches table: 0 rows
```

(But `units.last_batch_id` IS populated correctly with 3 batch UUIDs — so the runner KNOWS the batch ids, it just doesn't INSERT into the batches table or emit `event_queue.emit(...)`.)

**Fix location**: `pipeline/runner.py:BatchRunner.run` and `_process_batch`. Add:
1. `INSERT INTO runs (...)` at run start, `UPDATE runs SET status='complete'/...` at run end
2. `INSERT INTO batches (...)` at batch start, `UPDATE batches SET status='complete'/...` at batch end
3. `event_queue.get_bridge().emit(GuiEvent(kind='batch.start', ...))` at batch start
4. Same for `batch.progress` per item validated, `batch.complete`/`batch.failed` at end, `cost.update` after each batch
5. Subscribe GUI BatchesTab is already there (Fixer B did wire `_on_event`) — when emit works, table populates automatically.

Schema for both tables is already in `core/memory.py` (PRD §2.2). Just nobody writes to them.

#### Bug 4 (HIGH) — Reasoning model + json_schema can return empty completion

Transient this run, but architecturally unsafe. DeepSeek reasoning models (v4-pro, r1) can spend all output budget on reasoning trace and return empty completion content. Validator currently doesn't catch this — it accepts empty string as valid translation → status='translated' + dest=''.

**Fix locations**:
- `pipeline/clients/openai_compat_cc.py`: detect empty `choices[0].message.content` → raise specific exception OR set a marker on `LLMResponse` for runner to escalate to retry
- `pipeline/validator.py`: add gate 9 "non-empty dest" — fail if dest is empty string while source is not; route to retry with `temperature` bump or model swap
- `pipeline/retry.py:CorrectiveAddendum`: for empty-completion case, send the corrective message "Your previous response had empty content; please return the JSON object directly without reasoning"
- OR document: don't pair reasoning models with json_schema strict; recommend `deepseek/deepseek-chat` (non-reasoning) for translation workload

Practical short-term: change AMENDMENTS to warn that reasoning models are unsuitable for translation batch dispatch. User opted into v4-pro knowingly now.

#### Bug 6 — FALSE ALARM (delete this todo)

"Attorney's Fees" exists in RYOS at `MESG:FULL edid=adwBackstoryNewAtlantisGeneralMessage`. Not a bug. (See diagnostic logs.)

## UI/UX todos (still open from user testing)

| # | Area | What | Where |
|---|---|---|---|
| 1 | Glossary tab | Vanilla/Mod 提示 "let AI agent build entries"；Player/DNT 才提示 [Add] | `gui/tabs/glossary_tab.py` |
| 2 | Glossary Add dialog | Field labels misaligned; no tooltips/helpers; source/target lang/aliases meaning unclear | `gui/tabs/glossary_tab.py` |
| 3 | i18n | "Profile 列表" → "大语言模型提供商档案列表" | `gui/i18n/zh_CN.po` |
| 4 | Entries detail pane | Source overflows pushing dest off-screen; needs vertical split (each 50% height) + `ttk.Text` + AmberScrollbar per side | `gui/tabs/entries_tab.py` |
| 5 | Prompt tab toggle | Missing prompt-preview-required checkbox (per PRD §3.1 but also useful in Prompt tab itself) | `gui/tabs/prompt_tab.py` |
| 6 | Profile add UX | base_url should auto-strip trailing `/chat/completions` `/responses` `/messages` `/generate_content`; helper + placeholder visible | `gui/tabs/profiles_tab.py` + `cli/profile.py` |
| 7 | Set API key dialog | UX bug: user can type env_var_name and silently mismatch profile.api_key_env → ProfileMissingKeyError. Dialog should show env_name as **read-only label** from profile; user only fills **value** | `gui/tabs/profiles_tab.py` |
| 8 | profile probe | Probe should hard-fail on missing key, not silent success / mock fallback | `cli/profile.py` + probe code path |
| 9 | PromptTab auto-jump | When IPC preview event arrives, auto-`notebook.select(prompt_tab)` AND auto-set `batch_combo.set(batch_id)`. Right now user must manually pick from dropdown. Also: plan落盘 should trigger watcher → `_load_plans()` reload | `gui/app.py` + `gui/tabs/prompt_tab.py` |
| 10 | PromptTab side panel | 术语子集 + DNT panels show empty title + empty body when no preview active → confusing. Either populate from in-flight batch's `glossary_subset` field, or remove the side panel until preview-active | `gui/tabs/prompt_tab.py` |

## Suggested next-session fix dispatch

Three parallel fixers (after compaction):

### Fixer Q1: Bug 5 (events + runs/batches persistence)
- `pipeline/runner.py`: INSERT runs row at run start; INSERT batches rows per batch; UPDATE both at end
- `pipeline/runner.py`: `event_queue.get_bridge().emit(GuiEvent(kind='batch.start'/'batch.progress'/'batch.complete'/'batch.failed'/'cost.update', ...))` at appropriate hooks
- `core/memory.py`: ensure INSERT helpers exist (`insert_run`, `insert_batch`, `update_batch`, `update_run`) and are called
- Tests: synthetic LLM run → assert runs table has 1 row + batches table has N rows + event_queue captures expected event sequence

### Fixer Q2: Bug 4 mitigation + UI todos 7/8/6 (Profile/probe/API-key UX)
- `pipeline/validator.py`: gate 9 empty-dest non-empty-source → fail
- `pipeline/clients/openai_compat_cc.py`: emit warning when content empty; set `LLMResponse.empty_completion=True`
- `gui/tabs/profiles_tab.py`: Set API key dialog refactor (read-only env_name label, user fills value)
- `cli/profile.py`: probe must dispatch a real test call; if it returns error / 401 / 403 → hard fail with envelope `ok:false`
- `gui/tabs/profiles_tab.py` + `cli/profile.py`: base_url auto-strip endpoint helpers + helper text in dialog

### Fixer Q3: UI polish — todos 1, 2, 3, 4, 5, 9, 10
- `gui/tabs/glossary_tab.py`: scope-aware empty-state messaging + Add dialog with field tooltips + sample helpers
- `gui/tabs/entries_tab.py`: detail pane refactor to vertical split with scrollbars per side
- `gui/tabs/prompt_tab.py`: auto-jump on preview event; remove or fill side panel; add preview-required toggle
- `gui/i18n/zh_CN.po`: nav labels update
- Plan-watcher: `gui/app.py` add filesystem watcher on `<project>/batches/*/plan.json` → call `prompt_tab._load_plans()` on change

## File:line cheat sheet for next session

```
pipeline/runner.py:BatchRunner.run            ← where to add INSERT runs + emit run-level events
pipeline/runner.py:BatchRunner._process_batch ← where to add INSERT batches + per-item progress events
core/memory.py                                 ← add insert_run / insert_batch / update_run / update_batch helpers
core/event_queue.py:GuiEventKind               ← already has all relevant kinds incl 'prompt.preview_request', 'batch.start' etc
gui/tabs/batches_tab.py:_on_event              ← already subscribes — just needs events to actually flow
gui/app.py:_build_tab/_handle_preview_request  ← integration wiring already in place
gui/tabs/profiles_tab.py:set_api_key_dialog    ← refactor to value-only with read-only env_name
cli/batch.py:87                                ← KBGlossaryReader already wired
cli/batch.py:_request_preview                  ← Bug 1 specific catches already in place
pipeline/validator.py                          ← add gate 9 empty-dest
pipeline/clients/openai_compat_cc.py           ← add empty-completion detection
```

## What works end-to-end (don't regress)

- `xtl project init` against adwryos.esm → 665 units, 14 sigs
- `xtl project export --format sst` → 9 SST files (Starfield 9-fill)
- `xtl batch plan` → 3 batches, correct token est, real glossary
- `xtl batch run` → IPC preview to GUI, user approve, DeepSeek dispatch, memory.sqlite UPDATE, audit artifacts written
- GUI launch with native chrome stripped + AmberTitlebar + 8-zone resize handles + AmberCheckbox + AmberScrollbar
- All 4 sdk_kinds clients structurally implemented; openai-compat path tested live with OpenRouter

## What COST so far

Live testing: ~$0.027 across 3 batch runs against OpenRouter. Cheap enough to keep iterating with DeepSeek.

## Cost-aware re-run policy

For each future fixer round verification: ~$0.008 per run. Affordable. Recommend always pair fix + verify-via-real-run to catch silent failures (the audit-dir-confusion above shows static review isn't enough).
