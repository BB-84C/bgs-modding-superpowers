# bgs-translator Web Rewrite — Document Index

> **One-line summary**: Replace the Tk control panel of `bgs-translator` with a NiceGUI-powered browser surface so the agent can self-verify via Playwright, and structurally fix the cross-process event bug (Bug C) by construction. Tk is deleted once feature + acceptance parity is reached.

## Read in order

1. **`00-spec.md`** — what we're building and why. Intent, scope, hard contract on Tk removal, non-goals, success criteria. Read first.
2. **`01-architecture.md`** — how it's wired. Process topology, IPC redesign, event bridge redesign, theming, Playwright integration. Decision log (D-1..D-10) locked in by this doc.
3. **`02-phases.md`** — execution plan. 12 phases, ~9.25 dev-days (12 with buffer). Each phase has explicit tasks with file targets and verification commands.
4. **`03-acceptance.md`** — semantic acceptance criteria per phase + Playwright marker conventions + risk register. Owner of the "is this phase done?" question.

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
Phase 11: Cut-over: --backend web becomes default (0.25d)  ← user signoff required
Phase 12: Delete Tk tree (0.5d)                            ← user signoff required
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

The migration completes when **Phase 12 acceptance** passes:

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
