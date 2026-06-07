# 01 — Architecture

## Component diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            bgs-translator (Python)                            │
│                                                                               │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐ │
│  │    CLI     │  │  Tk Control  │  │     Agent      │  │   File watch    │ │
│  │   (xtl)    │  │     Panel    │  │   Interface    │  │   / log tail    │ │
│  └─────┬──────┘  └──────┬───────┘  └────────┬───────┘  └─────────────────┘ │
│        │                │                    │                                │
│        └────────────────┴────────────────────┘                                │
│                         │                                                     │
│                         ▼                                                     │
│            ┌────────────────────────────────────┐                             │
│            │     Project / Session Service      │                             │
│            │  (single asyncio loop, background  │                             │
│            │   thread when GUI is present)      │                             │
│            └──┬───────────────┬─────────────────┘                             │
│               │               │                                               │
│      ┌────────┴──────┐  ┌─────┴───────────┐    ┌──────────────────────┐     │
│      │  Parser / IO  │  │  AI Pipeline    │    │   Storage / TM       │     │
│      │               │  │                 │    │                      │     │
│      │  TES3 walker  │  │  extract        │    │  SQLite per project  │     │
│      │  TES4 walker  │  │  mask           │    │  SST emitter (SSU9)  │     │
│      │  per-game     │  │  batch + plan   │    │  XML emitter (opt)   │     │
│      │  schemas      │  │  LLM clients    │    │  parse cache binary  │     │
│      │  STRINGS read │  │  unmask         │    │                      │     │
│      │  SST reader   │  │  validate       │    │                      │     │
│      │  SST writer   │  │  retry          │    │                      │     │
│      └───────┬───────┘  └─────────┬───────┘    └─────────┬────────────┘     │
│              │                    │                       │                   │
│              └────────────────────┴───────────────────────┘                   │
│                                   │                                           │
│                                   ▼                                           │
│              ┌─────────────────────────────────────────┐                      │
│              │   KB Reader (read-only SQLite client    │                      │
│              │   against bgs-kb pack stores)           │                      │
│              └─────────────────────────────────────────┘                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                ┌─────────────────────────────────────────┐
                │  bgs-kb pack store on disk              │
                │  ~/.bgs-modding-superpowers/kb/         │
                └─────────────────────────────────────────┘

External callouts:
  - LLM providers (OpenAI / Anthropic / Gemini / openai-compat) via HTTPS
  - Filesystem only otherwise (no network calls except provider HTTPS)
```

## Process model

Single OS process. The threading shape depends on invocation mode.

### CLI invocation (`xtl <command>`)

| Thread | Owns |
|---|---|
| Main | argparse, asyncio.run(coro), exit |

One coroutine drives the command to completion. Process exits.

### GUI invocation (`xtl gui`)

| Thread | Owns |
|---|---|
| Main (Tk) | Tk event loop, all GUI widget state, user input |
| Background | asyncio event loop, LLM HTTP clients, file IO, parser, validator |
| (optional) IPC | Named pipe / Unix socket server for CLI ↔ GUI prompt-preview round-trip |

Cross-thread communication:
- GUI → backend: `loop.call_soon_threadsafe(asyncio.create_task, coro)`
- Backend → GUI: `queue.Queue` polled by `root.after(50, drain_queue)` callback
- Each batch emits progress events (`BatchEvent`) into the queue; GUI translates events into widget updates

### CLI-to-GUI handoff (prompt preview)

When the user has enabled "Always preview prompts before dispatch" in the Tk panel, the CLI command `xtl batch run` checks whether the GUI process is alive (PID file under `~/.bgs-modding-superpowers/translator/<runtime>.pid`):

- GUI alive: CLI opens the named pipe / socket, sends the rendered prompt, awaits the user's "approve" or "edit and approve" or "discard". On edit, the GUI returns the edited prompt body; CLI uses it for dispatch.
- GUI not alive: CLI proceeds without preview (logs a warning in the run log).

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | **Python 3.12+** | Matches MO2 control plane stack; gives us `tomllib`, structural pattern matching, modern asyncio |
| Async runtime | `asyncio` + `httpx` (async) | All HTTP through httpx for clean cancellation behavior |
| GUI | `tkinter` + `ttk` | Built-in, no extra runtime dependency, works on Win/Linux/Mac without bundling |
| GUI theming | Custom `ttk.Style` configurator | Three themes: `amber` / `green` / `mono` |
| i18n | `gettext` + `.po/.mo` files | English + Simplified Chinese; toggle via `config/settings.toml` or top status bar |
| Storage | `sqlite3` (stdlib) | Per-project memory DB + bgs-kb read-only access |
| Config files | `tomllib` (stdlib 3.11+) read, `tomli-w` write | TOML everywhere for user-editable config |
| LLM SDKs (native) | `openai`, `anthropic`, `google-genai` | No LiteLLM dependency in core path |
| Env var loading | `python-dotenv` | Only invoked inside LLM-dispatch code path |
| Schema validation | `pydantic` v2 | LLM structured output validation, profile config validation |
| Logging | stdlib `logging` + JSONL file rotation | Daily rotation, kept 30 days |
| CLI framework | `typer` | Good defaults for subcommand trees, type-hint driven |
| Packaging | PEP 517 (`pyproject.toml`) | `pipx install bgs-translator` |
| Tests | `pytest` + `pytest-asyncio` | Fixtures stored under `tests/fixtures/` |

**No Rust, no FFI, no native dependencies.** Single `pip install` story.

## Module layout (Python package)

```
bgs_translator/
├── __main__.py                  # python -m bgs_translator → CLI
├── cli/
│   ├── app.py                   # Typer root
│   ├── project.py               # xtl project ...
│   ├── inspect.py               # xtl inspect ...
│   ├── edit.py                  # xtl edit ...
│   ├── batch.py                 # xtl batch ...
│   ├── profile.py               # xtl profile ...
│   ├── validate.py              # xtl validate ...
│   ├── config.py                # xtl config ...
│   ├── gui_launcher.py          # xtl gui
│   └── envelopes.py             # JSON envelope shape, exit code mapping
├── core/
│   ├── project.py               # Project model, lifecycle, project.toml IO
│   ├── session.py               # Shared asyncio session/service for GUI mode
│   ├── memory.py                # SQLite-backed translation memory
│   ├── ipc.py                   # Named pipe / Unix socket for CLI ↔ GUI prompt-preview
│   └── runtime_pid.py           # Track GUI alive state via PID file
├── parsers/
│   ├── tes3.py                  # Morrowind walker
│   ├── tes4_family.py           # Oblivion → Starfield shared walker
│   ├── schemas/
│   │   ├── _base.py             # Per-game schema base class
│   │   ├── oblivion.py
│   │   ├── fo3.py
│   │   ├── fnv.py
│   │   ├── skyrim_le.py
│   │   ├── skyrim_se.py         # Also covers AE and VR (binary-identical)
│   │   ├── fo4.py
│   │   ├── fo76.py
│   │   └── starfield.py
│   ├── strings_io.py            # .STRINGS / .DLSTRINGS / .ILSTRINGS read
│   └── form_versions.py         # Game detection from TES4 header form version
├── sst/
│   ├── reader.py                # Read xTranslator .sst (SSU2..SSU9, accept all read SSU9 write)
│   ├── writer.py                # Emit SSU9 (see 03-sst-output.md)
│   ├── hash.py                  # stringHash + sanitizeFormID (ported from TESVT_Const.pas)
│   ├── status.py                # Status flag bitset semantics + UI color mapping
│   └── envelope.py              # Magic constants, version detection
├── pipeline/
│   ├── extractor.py             # Walk plugin → TranslationUnit
│   ├── mask.py                  # Protected-span tokenization
│   ├── batcher.py               # Grouping + BatchPlan assembly
│   ├── prompt.py                # System prompt template rendering
│   ├── clients/
│   │   ├── base.py              # LLMClient protocol
│   │   ├── openai_responses.py  # sdk_kind=openai (Responses API)
│   │   ├── anthropic_messages.py  # sdk_kind=anthropic (Messages + tool use)
│   │   ├── gemini_generate.py   # sdk_kind=gemini (generate_content)
│   │   └── openai_compat_cc.py  # sdk_kind=openai-compat (chat completions, honest)
│   ├── validator.py             # 8 post-LLM gates
│   ├── retry.py                 # Corrective-feedback retry layer
│   └── runner.py                # Batch lifecycle, cancellation, event emission
├── kb/
│   ├── reader.py                # Direct SQLite reader over bgs-kb pack stores
│   └── glossary.py              # 4-layer composition logic (compose, not stop-at-first)
├── gui/
│   ├── app.py                   # Tk root, theme loader, i18n setup
│   ├── close_handler.py         # Two-stage close confirmation + unsaved-work check
│   ├── tabs/
│   │   ├── project_tab.py
│   │   ├── entries_tab.py
│   │   ├── batches_tab.py
│   │   ├── prompt_tab.py
│   │   ├── profiles_tab.py
│   │   ├── glossary_tab.py
│   │   └── logs_tab.py
│   ├── widgets/
│   │   ├── scrollable_frame.py
│   │   ├── status_bar.py
│   │   ├── progress_cell.py
│   │   └── secret_input.py      # API key field with Show/Hide toggle
│   ├── themes/
│   │   ├── amber.py
│   │   ├── green.py
│   │   └── mono.py
│   ├── i18n/
│   │   ├── en.po
│   │   ├── zh_CN.po
│   │   └── _coverage_check.py   # CI script: refuses build if zh_CN missing keys
│   └── dpi.py                   # SetProcessDpiAwareness + tk scaling
├── config/
│   ├── paths.py                 # ~/.bgs-modding-superpowers/ + $BGS_MODDING_SUPERPOWERS_HOME
│   ├── profiles.py              # ProviderProfile load/save
│   ├── settings.py              # Global settings (theme, lang, defaults)
│   └── pricing.py               # Per-model price table for cost estimation
└── observability/
    ├── logging.py
    ├── cost_tracker.py
    └── rate_tracker.py
```

## Data flow (one batch end-to-end)

```
1. Agent: xtl batch plan ...
   → ToolService.plan_batch(project, args)
   → returns BatchPlan: plan_id, batch_count, est_tokens, est_cost, full sample prompt

2. (optional, when GUI present + preview flag on)
   GUI Prompt tab pops up, shows full system prompt
   user reviews / edits / approves
   → IPC returns approved prompt body (or "approve all remaining")

3. Agent: xtl batch run --plan <id>
   → ToolService.run_batches(plan_id) returns run_id immediately
   → background asyncio: for each batch concurrently (up to profile.max_concurrency):
        a. mask:       items → MaskedUnit list + mask_map per unit
        b. assemble:   system prompt + structured output schema + items JSON
        c. dispatch:   LLM client (per profile.sdk_kind) as asyncio task
        d. await:      complete JSON response (no streaming)
        e. unmask:     LLM output strings → restore placeholders + MCM tokens
        f. validate:   8 validation gates in order
        g. retry:      if soft fail, corrective-feedback retry (max 2x)
        h. persist:    write TranslatedUnit to project memory.sqlite
        i. emit event: progress event into GUI queue + log

4. All batches done → run status = complete
   → Tk Batches tab shows final cost, token counts, success/fail breakdown

5. Agent: xtl project export --format sst
   → SST writer reads memory.sqlite, emits .sst per 03-sst-output.md
   → For Starfield projects with starfield_dummy_fill=true, emits 9 .sst files

6. User: opens .sst in xTranslator or ESP-ESM Translator, hits Finalize
```

## Distribution

- **Public package on PyPI**: `pipx install bgs-translator` (recommended) or `pip install bgs-translator`
- **Auto-detection on first run**: checks `~/.bgs-modding-superpowers/`, offers to migrate older `bgs-kb` cache if found at the legacy path (see `08-persistence-and-paths.md`)
- **Not bundled with `bgs-modding-superpowers` plugin**. Separate optional install. The bundled `using-bgs-translator` skill instructs `pipx install bgs-translator` when the CLI is not on PATH.
- **Versioning**: semver. PRD locks v1.0 design contract. Bumps to PRD version on architecture-level changes; bumps to package version on any code change.
- **Cross-platform**: Windows / Linux / macOS supported equally. Tk is the bottleneck for visual consistency; documented as "looks slightly different per OS" rather than fought.

## Why these architecture choices

| Choice | Why |
|---|---|
| Python | LLM SDK ecosystem maturity dominates the choice; matches existing MO2 control plane |
| Native LLM SDKs (no LiteLLM) | Provider-specific features (prompt caching, exact cost reporting via OpenRouter, rate-limit headers) get hidden by LiteLLM abstraction layer |
| Single asyncio loop in background thread | Standard pattern for Tk + asyncio; no `tkinter.async` shenanigans |
| No streaming | Translation output is bounded; streaming complicates JSON-schema validation and per-batch atomicity |
| SQLite per project (not global) | Projects are independent; project portability is a feature; locking concerns vanish |
| TOML everywhere user-editable | Comments + human-friendly + stdlib reader |
| Tk over PyQt / web UI | Zero install dependency, ships with Python; good enough for config + monitoring; not a translation editor |
| One agent skill, not many | Translation is one workflow with submodes; multiple skills would fragment the agent's mental model |
