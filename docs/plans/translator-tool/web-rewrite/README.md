# bgs-translator Web Rewrite — Document Index

> **One-line summary**: Replace the Tk control panel of `bgs-translator` with a NiceGUI-powered browser surface so the agent can self-verify via Playwright, and structurally fix the cross-process event bug (Bug C) by construction. Tk is deleted once feature + acceptance parity is reached.

## Read in order

1. **`00-spec.md`** — what we're building and why. Intent, scope, hard contract on Tk removal, non-goals, success criteria. Read first.
2. **`01-architecture.md`** — how it's wired. Process topology, IPC redesign, event bridge redesign, theming, Playwright integration. Decision log (D-1..D-10) locked in by this doc.
3. **`02-phases.md`** — execution plan. 12 phases, ~9.25 dev-days (12 with buffer). Each phase has explicit tasks with file targets and verification commands.
4. **`03-acceptance.md`** — semantic acceptance criteria per phase + Playwright marker conventions + risk register. Owner of the "is this phase done?" question.
5. **`09-tk-to-web-mapping.md`** — Phase 9 audit map from every Tk flow to web counterpart or explicit deferral.
6. **`10-cutover-readiness-audit.md`** — current Phase 11/12 readiness map; separates proven work from signoff/external-evidence gates.
7. **`11-post-cutover-backlog.md`** — manual-testing findings and deferred feature/design backlog after the browser cut-over.

## Decision rationale (TL;DR)

Three perspectives consulted 2026-06-08 (saved under `D:\awesome-bgs-mod-master\.opencode\artifacts\web-rewrite-research\`):

- `nicegui-eval.md` — librarian-alpha
- `fastapi-htmx-alpine-eval.md` — librarian-beta
- `architecture-review.md` — oracle (read-only)

Outcome: **NiceGUI** chosen by user.

Reasons:
- Python single-source; FastAPI-native (matches existing stack).
- `app.clients()` replaces `EventQueueBridge` drain without `BatchRunner` rewrite.
- Named-pipe IPC collapses into a single FastAPI endpoint + `asyncio.Future`.
- `.mark()` data-marker attributes + Quasar's ARIA roles make Playwright effective.
- Amber-CRT aesthetic preserved as CSS injection.

## Migration strategy summary

```
Phase 0:  Skeleton + branch + Playwright fixture (0.5d)
Phase 1:  Cross-process event topology fix (1d)        ← structurally closes Bug C
Phase 2:  Server skeleton + --backend web flag (1d)
Phase 3:  Preview handshake end-to-end (1.5d)          ← load-bearing slice
Phase 4:  Batches + Project tabs (live event stream) (1d)
Phase 5:  Entries tab + detail pane (fixes Bug D) (1d)
Phase 6:  Profiles tab + UX 6/7/8 (0.5d)
Phase 7:  Glossary tab + UX 1/2 (0.5d)
Phase 8:  Logs tab + theme + i18n (0.5d)
Phase 9:  Playwright parity suite (1d)
Phase 10: Live LLM acceptance, real OpenRouter run (0.5d)
Phase 11: Cut-over: --backend web becomes default (0.25d)  ← user signoff received 2026-06-09
Phase 12: Delete Tk tree (0.5d)                            ← out of current scope; separate user authorization required
```

Total: **~9.25 dev-days** raw, **~12 dev-days** with rework buffer.

## What stays untouched

These backend modules ship through the rewrite verbatim:

- `bgs_translator/pipeline/runner.py` (only the event-publisher injection changes)
- `bgs_translator/pipeline/clients/*`, `validator.py`, `retry.py`, `batcher.py`, `planner.py`
- `bgs_translator/core/memory.py` (extended with `events` table — additive)
- `bgs_translator/kb/`, `parsers/`, `output/`, `sst/`, `config/`, `observability/`
- All Pydantic models: `BatchPlan`, `Batch`, `MaskedUnit`, `GlossaryEntry`, `ProviderProfile`, `GuiEvent`
- `bgs_translator/gui/i18n/*.po` (loader becomes server-side gettext)

## What gets deleted at Phase 12

- `bgs_translator/gui/` (entire Tk tree)
- `tests/gui/` (Tk widget tests)
- `bgs_translator/core/ipc.py` (named-pipe IPC server)
- `EventQueueBridge` class in `bgs_translator/core/event_queue.py` (the dataclass + enum stay)
- The `--backend tk` flag in `cli/gui_launcher.py`
- `pywin32` dependency

## Open questions deferred to phase start

See `00-spec.md` §11. OQ-1 through OQ-5 are intentionally not decided here; they will be settled at the relevant phase.

## How to execute this plan

Per the writing-plans skill convention, two options:

### Subagent-driven (recommended for parallelizable phases)

Dispatch a fresh fixer subagent per phase, review between phases, fast iteration. Phases 4-8 (per-tab) are especially good candidates because they're largely independent.

### Inline execution

Execute phases in the current session with checkpoints between phases. Good for the load-bearing Phases 1, 3, 10, 12 where context continuity matters most.

A mix is fine: inline for 1+3+10+11+12, subagent for 2+4-9.

## When this plan is "done"

The current cut-over scope completes when **Phase 11 acceptance** passes: `xtl gui` opens the browser panel by default, `xtl gui --backend tk` remains available, and the user has signed off.

The larger migration completes only if a future, separately-authorized **Phase 12 acceptance** passes:

- Tk tree deleted.
- `git grep tkinter` returns zero hits in `tools/bgs-translator/`.
- Full test suite green.
- Final commit lands with title: `refactor(gui): remove Tk control panel; web is the only surface`.
- `docs/dev-log.md` has a migration completion entry.

That commit is the proof of completion. Per `00-spec.md` §9, it's the tertiary success metric.

## Related project docs

- `../HANDOFF-POST-LIVE-TEST.md` — bug list + live-acceptance evidence that motivated this rewrite (esp. Bug C diagnosis).
- `../AMENDMENTS.md` — running amendments to the original PRD; cut-over will be logged here.
- `../00-overview.md` through `../14-open-questions.md` — original 16-file PRD for the Tk implementation. Reference only; the web rewrite supersedes the GUI portion (`07-tk-control-panel.md`).

## Document version

| Date | Change |
|---|---|
| 2026-06-08 | Initial draft. Approved by user. |
| 2026-06-08 | Initial implementation slice started: project-scoped sqlite events, `--backend web` shell, browser-verified preview handshake, Tk-inspired/Fallout-TUI visual inheritance. |
| 2026-06-08 | RYOS TDD slice: planned-prompt browsing, pending-preview polling fallback, desktop CSS pass, dry-run preview approval, and OpenRouter live smoke (`rn_f7c9a28e9a04`, 7/7, exact `$0.00290636`). |
| 2026-06-08 | Phase 4 Batches slice: sqlite-backed run/batch/event browser, per-batch progress bars, latest-run follow, historical event reconstruction, and composite `(run_id,batch_id)` batch key migration. |
| 2026-06-08 | Phase 5 Entries slice: sqlite-backed filters, source/dest split pane, browser save flow, manual-edit audit reuse, and resized-desktop layout check. |
| 2026-06-08 | Phase 6 Profiles slice: REST-backed profile list/save/delete/activate/key/probe flows, endpoint-suffix stripping, read-only key env label, missing-key hard fail, real OpenRouter probe, blind-context UX follow-up, and resized-desktop layout check. |
| 2026-06-08 | Phase 7 Glossary slice: scope-gated REST API, player/DNT add-edit-delete flows, Starborn glossary TDD into the next batch plan, and desktop visual QA fixing table overflow with relative column/layout sizing. |
| 2026-06-08 | Phase 8 Logs/theme/language slice: run-log file APIs, Logs page file viewer, amber/green/mono class-scoped CSS variables, header selectors, PO-backed loader, and desktop Browser QA. |
| 2026-06-08 | Phase 9 parity slice: web_e2e coverage raised to 31 tests including full synthetic HTTP preview round-trip, top-level page markers and keyboard shortcuts covered, invalid theme/language saves now return HTTP 400, blind-context UX review findings partially addressed, Tk-to-web mapping doc added, and Browser desktop QA verified no overflow / no 7847 console errors. Mobile is not an acceptance target for this control panel. |
| 2026-06-08 | Phase 10 live acceptance: real OpenRouter-DeepSeek web run `rn_ea036975f0de` completed 18/18 with exact `$0.028014936999999997` and live Batches updates; it exposed a retry-success batch status bug, fixed by making final batch status follow final outcome and persisting `retry_count`; post-fix live smoke `rn_751060ff33f2` showed Browser Batches status `已完成`, `1/1`, exact `$0.002945904`. |
| 2026-06-08 | Phase 10 follow-up: desktop-only layout contract now keeps glossary as a real table at resized desktop widths, Prompt approval failures show visible status instead of silent no-op, and Batches has web cancel-run parity via `cancel.requested`. |
| 2026-06-08 | Phase 10 readback audit added at `.opencode/artifacts/web-rewrite-acceptance/phase-10/READBACK.md`; copied run files are under `phase-10/run-artifacts/`, sqlite/event export is in `phase-10/sqlite-readback.json`. |
| 2026-06-08 | Cut-over readiness audit added: Phase 11/12 are not yet authorized; remaining gates are measured perf artifacts, independent cost dashboard evidence or waiver, preserved live-render evidence, user signoff, and Tk-removal wait/review. |
| 2026-06-08 | Project close/export parity slice: Project page now exposes SST export, open exports folder, close-risk summary, and browser close warning for running tasks or manual edits newer than latest export. |
| 2026-06-08 | Bug B fixed: user-pack player/DNT glossary entries now merge into every batch as user preferences while vanilla/mod remain source-matched. Real RYOS re-plan `62b417b6-8510-4e58-8e00-90f2930dc8d1` produced 24 batches with `FC`, `Starfield`, and `UC` present in every batch glossary subset. |
| 2026-06-08 | Phase 11 perf/readback slice: route links now force full document navigation, page scripts run through NiceGUI client hooks, Batches exposes hidden perf metrics, and `.opencode/artifacts/web-rewrite-acceptance/phase-11/` records first-byte max 36.829 ms plus Batches event render 232.525 ms emit-to-DOM / 7.4 ms WS-to-render. |
| 2026-06-09 | Phase 11 in-app Browser live-render evidence preserved: real OpenRouter run `rn_8b27744611c1` completed 2/2 with exact local provider cost `$0.00134068`; `phase-11/live-render-iab/` contains screenshots from running to complete plus structured sqlite/event readback. |
| 2026-06-08 | Phase 11 in-app Browser layout correction: removed the browser shell's fixed 64rem minimum width, changed the status bar to wrap, and tightened Batches table/progress sizing. Evidence under `.opencode/artifacts/web-rewrite-acceptance/phase-11/layout-overflow/` shows default in-app width and 1024x768 desktop probes with no horizontal/element overflow. |
| 2026-06-09 | Phase 11 synthetic 10-batch readback preserved: local web preview HTTP path completed 10 approvals / 10 batches / 10 `batch.complete` events in 15539.4 ms; Batches API max latency was 211.702 ms. Four-hour browser memory remains a separate unproven gate. |
| 2026-06-09 | Blind-context UX follow-up: Bernoulli blocked trial on P0 ordinary-player UX risks, then status/cost clarity, Prompt current-vs-history separation, approve-all confirmation, Entries wording/overflow/internal-ID exposure, dangerous-action confirmations, and Glossary "AI agent" wording were fixed. In-app Browser evidence is under `phase-11/blind-ux-followup/`. |
| 2026-06-09 | Post-UX-fix verification: `tests/web_e2e` now passes 44 tests; selected web rewrite regression set passed 83 tests with 3 warnings; ruff clean; mypy clean across 120 source files. |
| 2026-06-09 | Second Batches layout correction after user screenshot review: fixed the parent workbench's fixed `rem` column floors, changed Batches toolbar/workbench sizing to proportional desktop tracks, and added a regression guard so percentage table columns cannot be paired with a fixed-floor parent again. Evidence: `phase-11/layout-overflow/iab-batches-after-relative-layout.png`. |
| 2026-06-09 | Second blind-context Batches pass: Bernoulli found no new P0; Batches now prefers an active running task, disables stop on finished runs, explains stop scope, and hides run/batch IDs from default player-facing labels while preserving hover traces. Evidence: `phase-11/blind-ux-followup/batches-after-p1-ux-fix.png`. |
| 2026-06-09 | OpenRouter provider-side cost evidence added: `GET /api/v1/generation` readback for all Phase 10 `gen-*` ids exactly matched local `usage.cost` sums for both live runs (`delta = 0.0`). Evidence: `phase-10/openrouter-generation-readback/`. |
| 2026-06-09 | Follow-up desktop layout fix: shared workbench/layout grids now use `auto-fit` desktop tracks so narrow desktop panes stack panels instead of crushing text/UI into forced two columns. Profiles, Glossary, Logs, metrics, setup steps, compact forms, and helper cards use the same shrinkable pattern. Regression: `test_desktop_layout_css_keeps_tables_as_tables`; selected web rewrite regression set remains 83 passed / 3 warnings. |
| 2026-06-09 | Four-hour Browser memory evidence was attempted because `00-spec.md` §6.3 lists it as a cut-over performance criterion, but the monitor was stopped after the user questioned the requirement source. Per later user instruction, a separate PowerShell monitor may run independently; result verification is not in the current cut-over scope. |
| 2026-06-09 | Shell layout follow-up: Batches status/header overflow in the in-app Browser pane fixed by giving the status summary its own wrapping flex row and making top tabs wrap instead of using single-line horizontal chrome. Evidence: `phase-11/layout-overflow/iab-batches-after-shell-wrap.png` and `iab-batches-after-shell-wrap-metrics.json`; web_e2e now passes 44 tests. |
| 2026-06-09 | Phase 11 cut-over approved by user: `xtl gui` now defaults to the browser panel, while `xtl gui --backend tk` remains available. Tk deletion and 4-hour memory result review are explicitly outside the current scope. |
| 2026-06-09 | Cut-over UX follow-up: status danger state now links to `查看/停止运行中任务`, Batches puts `请求停止` before the task selector and uses `文本组`, Prompt disables send controls when only history is shown, Entries uses `条目编号`, Profiles keeps OpenRouter guidance visible, and Glossary keeps the AI term-list explanation after hydration. Browser evidence: `phase-11/blind-ux-followup/iab-*.png` and `iab-*.metrics.json`; selected regression remains 83 passed / 3 warnings. |
| 2026-06-09 | Post-cutover manual testing backlog added: plugin import, glossary/DNT hit explanation, vanilla terminology retrieval/RAG design, entry quick translate, and selected-entry batch queue are recorded in `11-post-cutover-backlog.md` and are not part of the current stabilization pass. |
| 2026-06-09 | Post-cutover feature slice implemented: GUI plugin import for readable ESP/ESM/ESL, bundled Starfield official SST -> vanilla KB sync, evidence-backed glossary/DNT retrieval with dedupe/budget caps, Entries quick translate through the active provider, and selected-entry queue artifacts consumable by `xtl batch plan --queue`. Remaining import gap: Starfield Creation Club localized text packed in BA2 archives still needs Strings extraction support. |
| 2026-06-09 | Manual feedback fixes at 150% browser zoom: stale `running` rows now display as `未正常收尾` instead of active billing risk, project links preserve selected project, `.xtl-app` wraps ordinary HTML for real content scrolling, empty export folders warn before opening, and green/mono themes recolor the full terminal surface. Evidence: `phase-11/manual-feedback-fixes/`. |
