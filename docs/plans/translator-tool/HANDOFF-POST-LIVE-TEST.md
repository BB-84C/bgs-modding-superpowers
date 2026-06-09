# Handoff — Post Live-Test (2026-06-08)

> **STATUS 2026-06-08 (post-Q1/Q2/Q3 + live acceptance round 1)**: Q1/Q2/Q3 landed (15 commits 3deff7f..ff5ec95). Plus `ccd68ff` for approve race. Live acceptance run executed (~$0.01) and surfaced more bugs that landed Tk-replacement decision; see "Live acceptance round 1 — open bugs" section below. Final test sweep before live: 312 passed, 3 skipped, 1 pre-existing flake (`test_drag_start_from_maximized_restores_with_proportional_cursor_anchor` — passes 3/3 in isolation, only fails under full-sweep Tk geometry contamination introduced in earlier commit `4a93ab2`). Ruff + mypy clean. Next decision = whether to rewrite GUI from Tk to a browser-rendered surface so the agent can self-verify via Playwright (see decision doc once written).

## Live acceptance round 1 — open bugs (2026-06-08)

User ran the GUI + a 67-item / 10-batch DeepSeek-via-OpenRouter live batch with full mod context (`plan_id=9bde9f04-bf3d-4d2c-be05-93aed9d2c90f`). Found:

| # | Severity | Bug | Status |
|---|---|---|---|
| A | HIGH (live blocker) | Approve action row hidden by `_focus_prompt_preview` → `refresh_for_batch` → `render_prompt_for_batch:142` race; CLI worker blocked in `IPC.wait()` forever. | **FIXED `ccd68ff`** with regression test (`tests/gui/test_app_prompt.py::test_preview_event_shows_approve_action_row`) |
| B | HIGH | Glossary subset in plan.json only carried 1 entry (`UC → 联殖`), DNT empty, despite user player + DNT glossary layers having content. Root cause: the collector only source-matched every scope, so user-maintained player/DNT overlays were dropped unless the exact term appeared in the current batch text. | **FIXED on `feat/translator-web-rewrite`**: user-pack `player` and `do_not_translate` entries now merge into every batch as high-priority user preferences; vanilla/mod packs remain source-matched. Regression tests cover reader, composer, Web API -> CLI plan path, and real RYOS replanning. |
| C | HIGH | Batches tab still shows `[尚无运行]` mid-flight and after completion on the Tk surface because the old `EventQueueBridge` is process-local. | **CLOSED ON WEB PATH**: sqlite-backed events + web Batches readback work. Preserved in-app Browser live-render screenshots/readback now exist under `.opencode/artifacts/web-rewrite-acceptance/phase-11/live-render-iab/`. |
| D | MEDIUM | Entries detail pane: only bottom 译/Dest half rendered; top 源/Source half missing on the Tk surface. | **CLOSED ON WEB PATH / SKIPPED ON TK**: web Entries has source + dest panes; Tk is pending removal and not being repaired. |
| E | LOW (cosmetic) | `cli/batch.py:plan_batch` passed the same `--game-lore` value to both `game_lore_world` and `game_context_lore_summary` prompt slots → header text duplicated in sample_system_prompt. | **FIXED on `feat/translator-web-rewrite`**: added `--game-lore-world` + `--game-lore-summary`, kept `--game-lore` as compatibility alias. |

### Web rewrite implementation note (2026-06-08)

Initial browser-GUI slice is in progress on `feat/translator-web-rewrite`:

- Added project-scoped sqlite `events` table and `EventPublisher(project=...)`; runner GUI events now persist to the project's `memory.sqlite` even when no GUI listener is present.
- Added `xtl gui --backend web` NiceGUI shell with Tk/Fallout-TUI visual inheritance, Chinese-first labels, left tree, top status bar, tab strip, Prompt workbench, Entries source/dest split, Batches/Project/Profiles views, and Glossary/Logs placeholders backed by local project reads where available.
- Added HTTP preview IPC with composite `(run_id, batch_id)` respond route; Browser TDD verified request → WebSocket render → click confirm → HTTP response `op=approved`.
- Added pending-preview polling fallback (`/api/preview/pending`) because live CLI runs can miss a websocket-only render during process/tab timing. Browser TDD verified CLI dry-run preview recovery and approval after the fallback.
- Prompt tab can browse recent planned batches from `plan.json`, sorted by mtime, so the newest RYOS plan is first instead of an older lexicographic directory.
- Batches tab now reads sqlite-as-truth runs/batches/events, renders run summary metrics, per-batch progress bars, and a live/reconciled event stream. Browser TDD verified default latest-run selection, manual run switching, OpenRouter run readback, and resized-desktop layout.
- Fixed a Phase 4 data model bug found during Browser TDD: `batches.batch_id` alone is not unique across repeated runs of the same plan. `batches` now migrates to composite `(run_id, batch_id)` primary key; runner updates pass `run_id`; Batches API falls back to persisted events for historical rows already overwritten by the old schema.
- Entries tab now has sqlite-backed filtering, row selection, source/dest split panes, manual-save API, and ordinary-player copy explaining that saves write project memory only, not original MOD files. Manual saves reuse the existing `edit` audit trail under `batches/manual-edits/`.
- Profiles tab now has REST-backed list/save/delete/activate/key/probe flows. It preserves the Tk profile fixes: base URLs auto-strip endpoint suffixes, API key env names are read-only when writing key values, key values never echo in API/page text, and probe hard-fails before dispatch when the key is missing. Browser TDD verified a temporary profile save/delete, dummy key save with no page echo, missing-key probe messaging, active-profile preservation, resized-desktop layout, and a real OpenRouter-DeepSeek probe success.
- Blind-context usability review requested ordinary-player wording and called out Profiles jargon. Follow-up UX pass added a four-step setup guide, grouped provider/internal fields under a visible "advanced settings" section, changed raw `openai-compat` display to "OpenRouter / DeepSeek 通用接口", made the profile key location read-only/auto-derived from profile name, removed the duplicate visible key-location field from advanced settings, added delete confirmation copy, and clarified that connection checks may consume a tiny amount of quota.
- Glossary tab now has REST-backed scope reads plus writable player / do-not-translate overrides. Vanilla/mod scopes are read-only and tell ordinary players that those layers are normally organized automatically by the tool; player/DNT scopes expose add/edit/delete with field helpers. Browser visual QA caught and fixed a desktop layout bug where glossary table text overflowed the panel: the table now uses relative column widths, short player-facing source labels, non-repeated CSS injection, and a 1280px desktop screenshot check with no detected overflow. Mobile is not part of the acceptance target for this workflow.
- Logs/theme/language slice now has REST-backed run-log APIs (`status.toml`, `validator-failures.jsonl`, root-level run files), a Logs page with recent events plus per-run file viewer, class-scoped amber/green/mono CSS variables, and header selectors for theme/language. Browser desktop QA verified `results.json` opens in the viewer, green theme changes the active CSS variable, English changes tab labels, settings restore to `amber`/`zh-cn`, and the Logs page has no detected desktop overflow or 7847 console errors.
- Phase 9 parity slice: `tests/web_e2e` now has 41 desktop/web contract tests covering all top-level page markers, Prompt/Profiles/Glossary/Logs markers, settings API validation, safe log-file rejection, sqlite event reconciliation, keyboard-shortcut script coverage, player-facing Prompt/Batches/Logs labels, Project SST/reload safety copy, Prompt visible response status, Batches cancel-run parity, desktop-only glossary table layout, blind-context UX regressions, and the user requirement that Profiles advanced settings stay visible instead of folded. Invalid theme/language saves now return HTTP 400 instead of leaking a server error. Browser desktop QA verified Glossary read-only default, switching to player scope, Escape closing the glossary editor, `Ctrl+B` navigation to Batches, `Ctrl+7` navigation to Logs, no desktop horizontal overflow on the tested pages, and no current 7847 console errors.
- Blind-context UX review (ordinary Chinese player, no provider/BGS internals knowledge) found the highest risks were raw batch/run IDs, raw event names, raw log filenames, provider jargon, and unclear SST/reload copy. Follow-up changed planned/live prompt labels to "第 N 批 / X 条待翻译" style, changed Batches/Logs run and event labels to Chinese summaries while retaining short IDs/tooltips for technical traceability, changed log file buttons to player-facing names, changed Profiles provider/JSON labels, removed the `<details>` folding control from advanced settings while keeping the section visible, and added Project copy explaining that SST is an xTranslator import file, not the MOD itself.
- Earlier blind-context usability review requested ordinary-player wording; visible text now avoids `DNT`/`Profile`/`批准本批次` where possible and explains that preview does not modify the original MOD file.
- Layout acceptance is desktop-only: major panels use proportional grid tracks, `clamp()` widths, and scroll containers for resized desktop windows. Mobile/tablet breakpoints are intentionally not part of this translator control panel.

### Web rewrite RYOS TDD evidence (2026-06-08)

- Fixture context came from `xtl inspect` sampling of `adwryos.esm`: MESG/FULL examples include `New Beginnings`, `RYOS Main Menu`, `Custom Game Starting Credits`, `Select Crew Member`, `Configuration Options`, `Main Quest Start Options`, `Gearing Up`, `Ship Requirements Met`; MESG/DESC examples include Unity/Starborn/Guardian Starship, Freestar Militia Impound Facility on Montara Luna, pedestrian starts, ship starts, NG+ options, autopilot, crew/day-room, and impound story text.
- External context checked: RYOS is a paid Starfield Creation by Wynterhawk/adwryos focused on alternate starts. The test prompt includes detailed Starfield 2330 Settled Systems lore plus RYOS-specific Montara Luna/Freestar Impound/custom-start context.
- Plan `51be614a-06f1-43d5-bf03-863edff61050` (`run seed 8419c038...`) generated 7 MESG:FULL items / 3 batches with split `--game-lore-world` and `--game-lore-summary`.
- Browser dry-run `rn_0cc274b908e9`: 3 preview confirmations through the web Prompt page, 7/7 succeeded, prompt-preview events persisted.
- OpenRouter live smoke `rn_f7c9a28e9a04`: first preview confirmed with "后续都按这样继续", 7/7 succeeded, 0 retry/manual_review/cancelled, exact cost `$0.00290636`; sample writes include `Into the Starfield → 进入星空`, `Pedestrian Starts → 步行开局`, `NG+ Universe Variant → NG+宇宙变体`, `Autopilot Engaged → 自动驾驶已启动`.
- Safety note: earlier live attempt `rn_e7a1823b37ab` intentionally failed closed when a retry preview was not attended; `prompt_preview_required=true` raised instead of silently dispatching.
- Batches-tab live stream smoke `rn_621df4022857`: dry-run with web preview request approved through `/api/preview/respond`, 3 batch rows visible, progress 1/1 + 5/5 + 1/1, `run.complete` visible in event panel. Historical OpenRouter run `rn_f7c9a28e9a04` also displays 3 reconstructed batch rows from events after the composite-key migration.
- Entries-tab Browser TDD: searched `Pedestrian Starts`, selected `adwPedestrianPriceRatioMenu`, saved temporary `Web QA 临时译文`, verified sqlite + audit write, then saved the original Chinese translation back. Resized-desktop viewport had no horizontal overflow and retained source/dest/save controls.
- Profiles-tab Browser TDD: temporary `Web-QA-Temp` profile saved from a pasted `/chat/completions` URL and displayed normalized `https://openrouter.ai/api/v1`; missing-key probe showed `缺少 API Key`; dummy key save cleared the input and did not echo the value; temp profile and temp `.env` var were cleaned up; active profile remained `OpenRouter-DeepSeek`; real OpenRouter probe eventually returned `连接成功`. Post-blind-review pass verified four-step guide, visible advanced settings section, single visible key-location field, friendly provider label, no desktop horizontal overflow, and no 7846/7848 console errors/warnings.
- Glossary-tab Browser TDD: vanilla/mod add buttons are disabled with AI-agent guidance; player/DNT add buttons are enabled; the add/edit form shows ordinary-player helpers for source term, target, aliases, category, and notes. API TDD added `Starborn → 星生子` in the player scope and verified the next batch plan includes it in the prompt glossary subset. Desktop visual QA on `http://127.0.0.1:7847/glossary` checked the player scope with editor open at 1280px and default desktop width; `documentElement.scrollWidth == window.innerWidth`, no detected clipped text, and screenshots show no panel overflow.
- Logs/theme/language Browser TDD: `http://127.0.0.1:7847/logs` loads the latest run event stream and file viewer; `status.toml`, `validator-failures.jsonl`, `results.json`, `system-prompt.md`, and `plan.json` are exposed as safe root-level file buttons; clicking `results.json` loads its JSON into the viewer. Switching theme `amber → green` produced `.theme-green` with `--xtl-text: #8dff9b`; switching language `zh-cn → en` changed the Logs tab label to `Logs`; final restore returned to `.theme-amber` / `zh-cn`. Desktop overflow detector returned empty and 7847 console warnings/errors were empty.
- Phase 9 Browser TDD: `http://127.0.0.1:7847/glossary` starts on read-only game glossary with add disabled; player scope enables add/edit; Escape closes the editor. `Ctrl+B` navigates to `/batches` and exposes `#xtl-refresh-batches`; `Ctrl+7` navigates to `/logs` and exposes `#xtl-log-refresh`. Prompt/Logs/Profiles/Project desktop checks confirmed the player-facing labels and visible non-folded advanced settings are rendered in the browser. Tested pages reported no desktop horizontal overflow. Current 7847 console warning/error filter returned empty.
- Phase 9 full synthetic acceptance: `tests/web_e2e/test_full_acceptance.py` starts a real local web server, writes `gui.port/gui.secret/gui.pid`, runs `xtl batch run --dry-run` through the web preview HTTP path, auto-approves 3 pending previews, and verifies 3/3 success, Batches API rows, sqlite events, and audit artifacts.
- Phase 9 Tk-to-web mapping doc added at `docs/plans/translator-tool/web-rewrite/09-tk-to-web-mapping.md`: every Tk tab/runtime flow is mapped to a web counterpart or explicit deferral. Known deferred web gaps before cut-over are now browser close/export confirmation, default flip, and Tk deletion.
- Phase 10 live OpenRouter acceptance: primary run `rn_ea036975f0de` used plan `0b68a525-d621-45bc-9fc6-8690d51685b6` against `OpenRouter-DeepSeek`, translating 18 `MESG:DESC` items in 7 batches. Browser Prompt showed the live 4-item preview and Approve-all was clicked in Browser; Batches tab live-updated rows/progress/cost and showed `全部完成`. CLI summary was 18 succeeded / 1 retried / 0 manual_review / 0 cancelled, exact cost `$0.028014936999999997`; audit artifacts included `plan.json`, `system-prompt.md`, `responses/*.raw.json`, `responses/*.normalized.json`, `results.json`, `status.toml`, `validator-failures.jsonl`, and retry artifacts.
- Phase 10 bug found/fixed: primary live run exposed that a retry-success batch could remain `failed` in `batches.status` because `_batch_status()` treated historical validation failures as final failure. Fixed by making final batch status follow the final outcome (`succeeded` with no final manual_review/cancelled => `complete`) and by persisting `batches.retry_count` in `update_batch()`. Regression: `tests/test_runner_persistence.py::test_retry_success_marks_batch_complete`.
- Phase 10 post-fix smoke: run `rn_751060ff33f2` used plan `d2817429-41ee-4e5a-b4e8-4660528b4664` against `OpenRouter-DeepSeek`, translating the remaining `MESG:FULL` item. CLI summary was 1 succeeded / 2 retried / 0 manual_review / 0 cancelled, exact cost `$0.002945904`. Browser Batches final readback showed status `已完成`, 1 batch, 1 complete, row `已完成 1/1`, event stream `批次完成` + `全部完成`, no desktop overflow, and no current 7847 console errors. Phase-10 summary and sqlite/artifact readback are saved under `.opencode/artifacts/web-rewrite-acceptance/phase-10/SUMMARY.md` and `.opencode/artifacts/web-rewrite-acceptance/phase-10/READBACK.md`.
- Phase 10 follow-up Browser/TDD pass: Prompt approval buttons now show visible status if there is no current pending preview or if response POST fails, using the select's stored `run_id/batch_id` as a fallback when page state is stale. Batches now exposes `请求停止` and POSTs `/api/projects/{project}/runs/{run_id}/cancel`, writing the CLI-compatible `cancel.requested` marker with a cost warning. Desktop layout CSS removed the mobile table-card breakpoint; glossary stays a real table and uses proportional widths. Browser checks at the current desktop window and 1200x800 desktop viewport found no glossary/batch cell overflow, no current 7847 console errors, and Prompt no-pending click displayed `当前没有等待确认的批次。`.
- Project close/export parity slice: Project page now exposes `导出 xTranslator 文件`, `打开导出目录`, a close-risk summary, and browser close warning when there are running batches or manual edits newer than the latest export. Browser desktop QA verified the controls render without overflow and no current 7847 console errors. This is the browser-constrained replacement for Tk's two-stage close/export flow.
- Bug B glossary collector fix: `KBGlossaryReader.query_user_scope_entries()` now reads user-pack `player` and `do_not_translate` scopes as global user preferences, while keeping vanilla/mod source-matched. RYOS re-plan `62b417b6-8510-4e58-8e00-90f2930dc8d1` (`e3ceb02da5204e7d9c89177d4090633a/plan.json`) produced 24 batches / 446 items; every batch has exactly 3 glossary entries: `FC` (`do_not_translate`), `Starfield → 星空` (`player`), and `UC → 联殖` (`player`); every batch's DNT list contains `FC`.
- Phase 11 performance/readback slice: internal route links now force full document navigation so NiceGUI does not leave old route scripts running, and page scripts execute through NiceGUI client hooks rather than inert dynamic `<script>` tags. Batches exposes hidden `window.__xtlBatchMetrics` for browser/readback evidence. Phase-11 artifact `.opencode/artifacts/web-rewrite-acceptance/phase-11/SUMMARY.md` records first-byte max 36.829 ms and Batches event render 232.525 ms backend emit-to-DOM / 7.4 ms WS-to-render. In-app Browser direct `goto()`/new-tab remained unreliable after restarts, so the perf readback used installed Playwright Chromium as a documented fallback.
- Phase 11 in-app Browser live-render evidence: real OpenRouter run `rn_8b27744611c1` used plan `03b402c5-164e-485b-b210-707cd16f08ad`, translated 2 items / 2 batches with `approve_all`, and completed 2 succeeded / 0 retry/manual_review/cancelled at exact local provider cost `$0.00134068`. Evidence is preserved under `.opencode/artifacts/web-rewrite-acceptance/phase-11/live-render-iab/` with screenshot sequence `iab-batches-00.png`..`09.png`, `iab-live-run-readback.json`, and `SUMMARY.md`. This evidence was captured before the later layout overflow correction, which is separately verified.
- Phase 11 layout correction after in-app Browser review: user caught Batches text/UI overflow. First root cause was a global `min-width: 64rem`, nowrap status bar, and batch table/progress minimums. Fixed by making the shell a proportional three-row grid, letting the status bar wrap, keeping Batches columns relative/table-fixed, and allowing progress bars to shrink. User then caught a second overflow risk: the Batches table used percentage columns but its parent workbench still imposed fixed `rem` column floors, so resized desktop windows could still squeeze/overflow. A follow-up changed the workbench and toolbar to proportional shrinkable tracks and allowed status/cost/event text to wrap or ellipsize. After a later user review, the shared workbench/layout grids were changed again to desktop `auto-fit` tracks (`minmax(min(100%, ...), 1fr)`), so narrow desktop panes stack panels vertically instead of forcing unreadably compressed two-column UI. Profiles, Glossary, Logs, metric cards, setup steps, compact forms, and helper cards received the same pattern. Final shell follow-up made the global status bar and tab strip wrap instead of clipping in the Codex in-app Browser pane. In-app Browser evidence is saved under `.opencode/artifacts/web-rewrite-acceptance/phase-11/layout-overflow/`; latest Batches screenshot/metrics are `iab-batches-after-shell-wrap.png` and `iab-batches-after-shell-wrap-metrics.json`. A cross-page audit under `.opencode/artifacts/web-rewrite-acceptance/phase-11/cross-page-layout/` checked `/project`, `/entries`, `/batches`, `/prompt`, `/profiles`, `/glossary`, and `/logs` at the current 832px in-app Browser desktop-pane width with no sampled horizontal overflow. CSS/HTML regression guards live in `test_desktop_layout_css_keeps_tables_as_tables` and `test_shell_status_summary_wraps_in_narrow_desktop_panes`.
- Phase 11 ten-batch synthetic readback: `.opencode/artifacts/web-rewrite-acceptance/phase-11/ten-batch-synthetic/` preserves a 10-batch local synthetic run through the real web preview HTTP path. Run `rn_f155447ddfc1` completed 10 succeeded / 0 manual_review / 0 cancelled with 10 approvals, 10 complete batch rows, 10 `batch.complete` events, duration 15539.4 ms, and Batches API max latency 211.702 ms. This strengthens no-stutter evidence but does not replace the 4-hour browser memory gate.
- Phase 11 blind-context UX follow-up: Bernoulli reviewed the UI as an ordinary Chinese player and initially blocked user trial on P0 issues: ambiguous running/cost status, Prompt history IDs mixed into current confirmation, and approve-all lacking a cost-warning confirmation. Follow-up fixed real status copy, Project stop-task path, current-vs-history Prompt separation, approve-all confirmation, Entries player-facing labels/no visible internal IDs, Entries dangerous-action confirmations, and Glossary "AI agent" wording. Second Bernoulli pass after the Batches layout correction found no new P0; P1 issues were fixed by preferring running tasks in the selector, disabling stop on finished runs, explaining stop scope, and hiding run/batch IDs from default labels. Final cut-over UX follow-up added a global status action `查看/停止运行中任务`, moved Batches `请求停止` before the selector, changed primary Batches/Prompt wording to `文本组`, disabled Prompt send controls when only history is shown, changed `内部 ID` to `条目编号`, and kept OpenRouter/Glossary guidance visible after hydration. In-app Browser evidence is under `.opencode/artifacts/web-rewrite-acceptance/phase-11/blind-ux-followup/`; final `/batches`, `/prompt`, `/profiles`, and `/glossary` probes/screenshots report required UX copy/no horizontal overflow at the tested 832px desktop-pane width.
- Phase 11 cut-over state: user approved shipping cut-over. `xtl gui` defaults to the browser control panel; `xtl gui --backend tk` remains available. Tk deletion is explicitly not in current construction/goal scope. The 4-hour Browser memory monitor runs in a separate PowerShell and its result verification is explicitly outside current scope.
- Current verification after the cut-over UX follow-up: `py -3.12 -m pytest tools/bgs-translator/tests/web_e2e -q` => 44 passed / 3 warnings. `py -3.12 -m pytest tools/bgs-translator/tests/web_e2e tools/bgs-translator/tests/cli/test_gui_launcher.py tools/bgs-translator/tests/test_runner_persistence.py tools/bgs-translator/tests/cli/test_profile.py tools/bgs-translator/tests/test_profile_cli.py tools/bgs-translator/tests/test_batch_plan_cli.py tools/bgs-translator/tests/test_kb_reader.py tools/bgs-translator/tests/test_glossary_composer.py tools/bgs-translator/tests/test_batcher.py tools/bgs-translator/tests/test_event_publisher.py -q` => 83 passed / 3 warnings; `ruff check tools/bgs-translator/bgs_translator/web/app.py tools/bgs-translator/tests/web_e2e/test_parity_contracts.py` clean; `py -3.12 -m mypy bgs_translator` clean across 120 source files.

Not done yet:

- Phase 9 acceptance items are now covered: >=30 web_e2e tests, full web suite green, Tk-to-web mapping doc present, and full synthetic web preview round trip present. Remaining items are cut-over/signoff/evidence gates, not Phase 9 blockers.
- Phase 10/11 live OpenRouter acceptance has run and produced readback evidence. Local sqlite/artifact readback is preserved in `.opencode/artifacts/web-rewrite-acceptance/phase-10/READBACK.md`, copied run files are under `.opencode/artifacts/web-rewrite-acceptance/phase-10/run-artifacts/`, sqlite/event export is under `.opencode/artifacts/web-rewrite-acceptance/phase-10/sqlite-readback.json`, OpenRouter-side generation cost readback is under `.opencode/artifacts/web-rewrite-acceptance/phase-10/openrouter-generation-readback/`, and in-app Browser live-render screenshots/readback are under `.opencode/artifacts/web-rewrite-acceptance/phase-11/live-render-iab/`. The previous independent cost evidence gap is closed: OpenRouter `total_cost` exactly matches local `usage.cost` sums for both Phase 10 live runs. Remaining interpretive risk: a post-fix multi-batch live rerun may be requested if Phase 10 is interpreted as needing the full scenario repeated after the retry-status fix.
- Phase 11 local timing gates for first byte, event-to-render, and synthetic 10-batch no-stutter are now measured in `.opencode/artifacts/web-rewrite-acceptance/phase-11/`. The 4-hour browser memory gate exists in `web-rewrite/00-spec.md` §6.3, but the user moved it out of current result-verification scope; a separate PowerShell monitor is running under `.opencode/artifacts/web-rewrite-acceptance/phase-11/browser-memory-4h/run-cutover-2026-06-08-220417/`.
- Phase 11 cut-over: user approved shipping cut-over on 2026-06-09. `xtl gui` now defaults to the browser backend; `xtl gui --backend tk` remains available. Tk deletion is not part of the current construction/goal scope and must not be bundled into this cut-over.
- Bug B glossary collector is fixed and verified against both focused tests and a real RYOS re-plan. It no longer blocks cut-over.
- Tk is not removed; `xtl gui --backend tk` remains the explicit fallback. Do not delete Tk or remove the backend flag in this cut-over scope.

### Live run evidence (`rn_<TBD>` from plan `9bde9f04`)
- Cost: ~$0.01 (DeepSeek via OpenRouter, exact)
- Item count: 67 MESG:DESC items in 10 batches
- All 10 batches approved (some via Approve-all-remaining)
- audit artifacts written under `batches/<run-id>/` (validates Q3 audit-write fix from prior round still holds)
- memory.sqlite `units.dest` populated (validates Bug 3 unit-update persistence still holds)
- `runs` / `batches` table state: NOT YET CAPTURED — needed for Bug C diagnosis next session

### Pending investigation order (when ready to resume on Tk surface)
1. Bug C — runs/batches table state + event_queue trace. **Oracle root-caused this during web-rewrite review**: `EventQueueBridge` singleton is process-local; `BatchRunner` runs in CLI process; GUI process has a different singleton; events never cross processes. Q1's `test_runner_persistence.py` passed because emit + drain were same-process in test. **Bug 5 fix is partial — INSERT-runs/batches works (shared sqlite), but emit-events is a no-op live until cross-process channel exists.** Will be naturally solved by web rewrite.
2. Bug B — KB user-pack resolution. **Fixed on the web-rewrite branch** by making user-pack player/DNT overlays global user preferences in the collector. Current RYOS re-plan verifies all registered user entries appear in every batch.
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
