# 12 — Implementation Chunks

This document breaks the work into dependency-ordered chunks. **No time bindings.** Each chunk is a chunk of substrate that lets later chunks build on it.

Chunks are independently testable. A chunk's "done" criterion is its own acceptance, not the whole tool's acceptance.

Per project memory rule (`30-operational-continuity-and-state-hygiene.md`): prefer multiple small commits. Each chunk maps to one or more PRs.

---

## Chunk A — Verification spikes (block 0)

**Purpose**: resolve the unknowns documented in `11-acceptance-and-spikes.md` §1 before touching architecture.

Run Spikes 1, 2, 4, 5. (Spike 3 is full end-to-end; deferred to chunk K.)

**Output**:
- Resolved values for `sParams` width, `stringHash` algorithm, `sanitize_formid` behavior (Spike 2)
- TES3 SST verdict for Morrowind path (Spike 1)
- Per-provider capability matrix (Spike 4)
- bgs-kb integration verified (Spike 5)

**Done when**: each spike's pass criteria are met (or fail action has updated the PRD).

**Dependencies**: none.

---

## Chunk B — Repository skeleton and packaging

**Purpose**: scaffold the Python package, CI, distribution.

Tasks:
1. Create `bgs_translator/` package with empty modules per `01-architecture.md` §module layout
2. Set up `pyproject.toml` with deps, entry points (`xtl`, `python -m bgs_translator`)
3. Set up `pytest` + `mypy` + `ruff` CI
4. Set up i18n scaffolding: `.po` extraction, `.mo` build, coverage check stub
5. Set up `pipx install`-able from local
6. Stub `xtl version` command (returns hardcoded version + capability matrix)

**Done when**: `pipx install -e .` works on Win/Linux/Mac, `xtl version` returns expected JSON.

**Dependencies**: none.

---

## Chunk C — Persistence and path layer

**Purpose**: implement the unified root + KB migration logic.

Tasks per `08-persistence-and-paths.md`:
1. `config/paths.py` — resolve `~/.bgs-modding-superpowers/`, override via env, create dirs on demand
2. KB cache migration with user-prompt UX (Spike 5's prep)
3. `settings.toml` reader/writer
4. `pricing.toml` reader/writer
5. `xtl config show` / `xtl config set` commands
6. Skip-migration escape hatch

**Done when**:
- `xtl config show` returns settings
- KB migration detects legacy paths and prompts (smoke test via fixture)
- Permission check on `profiles/.env` works on POSIX and Windows

**Dependencies**: B.

---

## Chunk D — Parser (TES4-family) + per-game schemas

**Purpose**: walk TES4-family plugins, extract TranslationUnits.

Tasks per `02-parser-and-coverage.md`:
1. TES4 record/group/subrecord walker (with zlib decompression, XXXX overflow)
2. Form version detection
3. ESL flag handling
4. Localized flag handling (read STRINGS for unit.source)
5. STRINGS / DLSTRINGS / ILSTRINGS reader
6. Encoding fallback chain (per-game per-locale table)
7. Per-game schema modules:
   - Extract cpTranslate slices via `scripts/extract_cptranslate.py` from xEdit `wbDefinitions<GAME>.pas` sources
   - Generate YAML manifests under `parsers/schemas/data/`
   - Implement schema classes for SkyrimSE, FO4, Starfield (priority order)
   - Then Oblivion, FO3, FNV, Skyrim LE, FO76
8. `xtl project init` command (parse + cache write + memory.sqlite seed)
9. `xtl inspect plugin/signatures/entries/entry/orphans` commands

**Done when**:
- adwryos.esm walk completes; counts match xTranslator's view
- Skyrim SE test plugin walk produces expected entries
- All 8 covered TES4-family games have schema modules

**Dependencies**: C (for memory.sqlite location).

---

## Chunk E — Parser (TES3) for Morrowind

**Purpose**: separate Morrowind walker.

Tasks:
1. TES3 record / subrecord walker
2. Morrowind schema (`parsers/schemas/morrowind.py`)
3. Inline-string extraction (no STRINGS file)

**Done when**: Morrowind test plugin walk produces expected entries.

**Dependencies**: D (for memory.sqlite + path conventions).

---

## Chunk F — SST writer + reader

**Purpose**: emit SSU9 files; optionally read user-supplied SSTs.

Tasks per `03-sst-output.md`:
1. `sst/hash.py` — port `stringHash` + `sanitize_formid` per Spike 2 results
2. `sst/writer.py` — emit SSU9 per byte layout
3. `sst/reader.py` — read SSU2..SSU9 (best-effort for older versions)
4. `sst/status.py` — bitset semantics + UI color mapping
5. `xtl project export --format sst` command
6. Starfield 9-fill default behavior

**Done when**:
- Spike 3 (full round-trip) passes
- Emitted SSTs load in xTranslator v1.6.0 without warning
- Round-trip read→write produces bytewise-identical output

**Dependencies**: D (for memory.sqlite contents).

---

## Chunk G — KB integration

**Purpose**: read glossary records from bgs-kb pack stores.

Tasks per `05-glossary-and-kb.md`:
1. **bgs-kb side prep** (separate workstream owned by bgs-kb team):
   - Add `glossary-entry` to record kind enum
   - Schema documentation
   - Ship seed `bgs-kb-l10n-skyrim-en-zhcn` pack with 5-10 example entries
2. `kb/reader.py` — direct SQLite read of pack stores
3. `kb/glossary.py` — 4-layer composition (not stop-at-first)
4. Manifest discovery via `bgs_kb_status` (one-time at startup, then cached)
5. User-pack overlay (`$BGS_KB_USER_PACKS`)
6. Tk Glossary tab read-write surfaces (player + DNT scopes)

**Done when**:
- Spike 5 passes
- Glossary subset rendered correctly in system prompts
- User can add player/DNT entries via Tk and they persist

**Dependencies**: C (for paths). bgs-kb-side prep work is a hard prerequisite.

---

## Chunk H — AI pipeline core (mask + batcher + validator)

**Purpose**: implement extract → mask → batch → validate stages (LLM dispatch deferred to Chunk I).

Tasks per `04-ai-pipeline.md`:
1. `pipeline/extractor.py` — walk units, dedup, filter
2. `pipeline/mask.py` — protected-span tokenization, all mask kinds
3. `pipeline/batcher.py` — group key, sizing, BatchPlan assembly
4. `pipeline/prompt.py` — template rendering with required slot validation
5. `pipeline/validator.py` — 8 gates
6. `pipeline/retry.py` — corrective-feedback retry logic (still no LLM dispatch — gates fail directly)
7. Synthetic LLM client for testing (`pipeline/clients/synthetic.py` — returns source verbatim)
8. `xtl batch plan` command

**Done when**:
- BatchPlan assembly produces correct structure for adwryos fixture
- Mask round-trip identity test passes (mask → unmask returns source)
- Validator gates correctly classify synthetic violations
- Prompt rendering produces expected text

**Dependencies**: D, G.

---

## Chunk I — LLM provider clients

**Purpose**: four sdk_kinds dispatching real LLM calls.

Tasks per `09-providers-and-keys.md`:
1. `config/profiles.py` — load profiles.toml, .env, validation
2. Permission check on .env
3. `pipeline/clients/base.py` — protocol + LLMResponse normalization
4. `pipeline/clients/openai_responses.py`
5. `pipeline/clients/anthropic_messages.py`
6. `pipeline/clients/gemini_generate.py`
7. `pipeline/clients/openai_compat_cc.py`
8. `observability/rate_tracker.py` — 3-layer rate limit
9. `observability/cost_tracker.py` — per-profile + per-project caps
10. `pipeline/runner.py` — batch lifecycle, asyncio task management, cancellation
11. `xtl profile add/list/show/edit/activate/probe` commands
12. `xtl batch run/status/cancel/logs` commands

**Done when**:
- Spike 4 capability probe matrix matches expected
- Real batch against adwryos fixture completes with each provider (smoke)
- Cancellation responsive
- Cost tracking accurate to within tolerance
- Rate limit observation kicks in correctly

**Dependencies**: A (Spike 4 results), H.

---

## Chunk J — Edit and validate commands

**Purpose**: Mode B operations + SST validation.

Tasks per `06-cli-surface.md` §3.3, §3.6:
1. `xtl edit entry/bulk/status/revert` commands
2. `xtl validate project` command
3. `xtl validate sst` command (round-trip diff)

**Done when**:
- Single edit roundtrip via JSONL works
- Validate project surfaces any orphans, partial, validator failures
- Validate sst diffs cleanly against reference

**Dependencies**: D, F.

---

## Chunk K — End-to-end smoke + Starfield Spike 3

**Purpose**: prove the full user story works.

Tasks:
1. Run Spike 3 (the full end-to-end round-trip) against adwryos.esm with a real LLM (preferably OpenAI or OpenRouter for cost reporting)
2. Verify all six steps from Spike 3 pass criteria
3. Document any gaps as PRD updates or Chunk-N items
4. Run Spike 1 (ESP-ESM Morrowind path) if not already done
5. Cross-tool test: emit SSTs for a Skyrim SE plugin, load in `sseTranslator`

**Done when**: end-to-end story works. User can actually translate a mod.

**Dependencies**: F, I, J. (G needed for glossary to be meaningful, but smoke can run with empty glossary.)

---

## Chunk L — Tk control panel (build out)

**Purpose**: implement the GUI per `07-tk-control-panel.md`.

Tasks:
1. App scaffold, theme system, i18n setup
2. Status bar
3. Nav tree
4. Project tab
5. Entries tab (read-only)
6. Batches tab with real-time updates
7. Prompt tab with editable preview
8. Profiles tab (CRUD)
9. Glossary tab
10. Logs tab
11. Two-stage close handler
12. DPI awareness
13. IPC for prompt preview round-trip with CLI

**Done when**:
- All 7 tabs functional
- All 3 themes render at all tested DPI scalings
- Both languages (en, zh-cn) complete in .po files
- Smoke test of full GUI interaction passes

**Dependencies**: I (for batch monitoring), J (for entries view), G (for glossary).

---

## Chunk M — Agent skill `using-bgs-translator`

**Purpose**: write the agent skill per `13-agent-skill-outline.md`.

Tasks:
1. Skill SKILL.md authored
2. Skill registered with the bgs-modding-superpowers plugin
3. Tested by routing a real "translate this mod" task through the orchestrator
4. Cross-references from `using-bgs-modding-superpowers` bootstrap added
5. Mention in `setting-up-bgs-modding-environment` (optional pipx install)

**Done when**:
- Agent invoked on a translation task successfully drives `xtl` to completion
- Skill correctly steers agent into the .env access boundary
- Skill correctly handles the prompt-preview flow

**Dependencies**: J (Mode B), I (Mode A), L (preview UX).

---

## Chunk N — Polish, documentation, release prep

**Purpose**: prepare for v1.0.0.

Tasks:
1. README and user docs in repo
2. PyPI listing prep
3. CHANGELOG.md
4. Verify all `11-acceptance-and-spikes.md` §5 criteria met
5. Final integration test against fixture
6. Pre-release tagging (v0.9, v0.9.1 ... v1.0.0-rc1)
7. Release publication

**Dependencies**: All prior chunks.

---

## Dependency graph

```
A ── B ── C ── D ── F ── J ── K ── N
         │    │    │
         │    ├────G───→ H ── I ── L ── M ──┘
         │    │    │
         │    └────E (TES3, parallel to F/G/H)
         │
         └── (Spike 5 prep includes bgs-kb-side work, external workstream)
```

A is the only chunk that can run before B. B and C must complete before D. D is the bottleneck before F, G, E.

H and G can be parallel after D.

I depends on H.

J depends on D and F (no LLM).

K is the integration after F, I, J.

L is the GUI build-out, depends on I and G.

M (skill) depends on L (preview UX).

N is final polish.

---

## Notes for the orchestrator that runs施工

- Each chunk is bounded enough to dispatch as a single fixer-tier task with the matching PRD file(s) as input. Larger chunks (D, I, L) probably want a senior agent.
- Do not pre-bind chunks to time. Treat them as discrete deliverables; ship each separately.
- Verification spikes (Chunk A) gate substantive work. Skipping them risks late-stage rework.
- bgs-kb-side prep work for Chunk G is on a separate codebase; coordinate before starting H.
- Code review per `requesting-code-review` skill applies between every chunk's PR and merge.
