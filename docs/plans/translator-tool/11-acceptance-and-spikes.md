# 11 — Acceptance and Verification Spikes

This document captures the verification work that must run before any major architectural decision is treated as final, plus the standing acceptance criteria for the tool as a whole.

Per the project's `10-semantic-proof-and-acceptance-design.md` memory: surface proxies (it parsed, the test passed, the script returned 0) are not acceptance. Real semantic acceptance is "the .sst file we emitted opens cleanly in xTranslator v1.6.0, lists the expected entries, lets the user click Finalize, and produces working .STRINGS files."

---

## 1. Verification spikes (run before施工 starts)

These are bounded investigations that resolve genuine unknowns the design has assumed. Each spike has a binary outcome that informs implementation.

### Spike 1: ESP-ESM Translator reads SST containing TES3 record signatures

**Why**: The dual-GUI terminal story (`03-sst-output.md` §4) depends on ESP-ESM Translator handling SSTs that reference Morrowind's TES3-family record/subrecord signatures (`NAME`, `FNAM`, `DESC`, `BNAM`). The 2game.info reference suggests it works; we have not verified.

**Procedure**:
1. Hand-author a minimal SST file (10-20 entries) referencing a real Morrowind plugin
2. Use TES3 signatures: `NAME`, `FNAM`, `DESC`, `BNAM`
3. Set `rHash` per xTranslator convention (`stringHash` of EditorID or `'[xxxxxxxx]'` form)
4. Load into ESP-ESM Translator 4.35

**Pass criteria**:
- ESP-ESM Translator loads the SST without error
- All entries appear in the dictionary view
- Source/dest fields display correctly
- The corresponding Morrowind plugin can be translated using these entries

**Fail action**:
- Drop Morrowind from SST-as-deliverable; use ESP-ESM Translator's native XML format (open, documented) for Morrowind exclusively
- Update `03-sst-output.md` §4 to reflect

### Spike 2: SST byte-level format verification via hex dump

**Why**: Three internals of the SST format are unverified at byte level:
- `sParams` is 1 byte or 4 bytes on disk (Pascal `(size = size of cardinal)` comment implies 4, but `{$MINENUMSIZE}` directive must be confirmed)
- `stringHash` algorithm body (Lane 1 research truncated)
- `sanitizeFormID` exact behavior (assumed `& 0x00FFFFFF`; not source-confirmed)

**Procedure**:
1. Open one of the user-provided fixture SSTs from `D:\SteamLibrary\steamapps\common\Starfield\Tools\xTranslator-313-1-4-5-alpha-1694868294\_xTranslator\UserDictionaries\Starfield\`
2. Hex-dump (xxd or HxD)
3. Identify entry boundaries by listIndex byte (`0x00`, `0x01`, or `0x02` always begins an entry)
4. Measure `sParams` width — count bytes between colabId and `src_size`. Should be 4 if cardinal, 1 if `{$MINENUMSIZE 1}`.
5. For an entry with known EditorID (cross-reference against xTranslator's GUI view), compute `stringHash(edid)` per ported Pascal — confirm `rHash` field matches
6. Test `sanitize_formid` on an entry with high-byte set; confirm hash uses `formid & 0x00FFFFFF`

**Pass criteria**: Computed values match disk bytes exactly.

**Fail action**:
- If `sParams` is 1 byte: update `03-sst-output.md` §1.2 and writer code
- If `stringHash` body differs: capture exact algorithm from `TESVT_Const.pas` implementation section (fetch full file), update `sst/hash.py`
- If `sanitize_formid` differs: update accordingly

### Spike 3: Round-trip emit against adwryos.esm fixture

**Why**: End-to-end validation that our parser + extractor + SST writer produces a file that xTranslator v1.6.0 loads with no warnings and content matching what xTranslator's own extractor would produce.

**Procedure**:
1. Run `xtl project init` against `D:\Starfield MO2\mods\adwryos-cc\adwryos.esm`
2. Run `xtl batch plan` (no actual LLM dispatch — use a stub that returns source verbatim as dest)
3. Run `xtl batch run`
4. Run `xtl project export --format sst`
5. Open `D:\SteamLibrary\steamapps\common\Starfield\Tools\xTranslator-...\` xTranslator
6. Open `adwryos.esm`, then open our emitted SST
7. Verify entry count matches xTranslator's own count
8. Verify per-signature counts (WEAP, ARMO, INFO, BOOK, etc.) match
9. Verify a sampling of entries (10 per signature) have the correct source string
10. Verify Finalize produces valid `.STRINGS` files
11. Load Finalized mod in MO2, launch Starfield, verify no "string not found" errors in any translated UI element

**Pass criteria**: All 11 steps clean. xTranslator gives no warnings on load. Finalize succeeds. In-game text appears correctly.

**Fail action**:
- For per-signature count mismatches: inspect cpTranslate slice; missing signatures = extension to schema
- For source string differences: encoding chain bug; fix encoding table
- For Finalize errors: usually our SST format error; cross-reference Spike 2 results
- For in-game errors: usually SST writer error; full diff against xTranslator's own SST output for the same plugin

### Spike 4: Provider capability probe matrix

**Why**: `09-providers-and-keys.md` §6 defines capability probe behavior, but the actual capabilities for each provider as of implementation date are unverified.

**Procedure**: For each provider (OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter):
1. Acquire a small test key
2. Run `xtl profile probe <name>`
3. Inspect probe result against documented capability claims

**Pass criteria**: Each provider's probe correctly identifies:
- Structured output supported (or json_object only for DeepSeek)
- Rate limit headers presence
- Cost reporting (only OpenRouter)
- Prompt caching (Anthropic only)
- Cancellation behavior

**Fail action**: Adjust per-provider client code in `pipeline/clients/`.

### Spike 5: bgs-kb integration

**Why**: Direct SQLite read against bgs-kb pack stores requires the new `glossary-entry` record kind to be present in pack schemas.

**Procedure**:
1. bgs-kb side: ship a minimal `bgs-kb-l10n-skyrim-en-zhcn` pack with 5-10 example `glossary-entry` records
2. Install via `bgs_kb_install_pack`
3. Translator side: open SQLite read-only, query for entries
4. Verify 4-layer composition logic resolves correctly

**Pass criteria**: Translator reads entries without schema errors. Resolution returns expected layered results.

**Fail action**:
- If schema mismatch: update bgs-kb pack schema or translator reader to align
- If composition logic incorrect: fix `kb/glossary.py`

---

## 2. Standing acceptance criteria (apply continuously during施工)

### 2.1 Parser correctness

For every game in the coverage matrix:
- Walking the canonical test plugin completes without error
- Signature counts match xTranslator's view (where xTranslator supports the game) or ESP-ESM Translator's view (Morrowind/Oblivion/FO3)
- For ESL-flagged plugins, FormIDs are correctly extracted with high-byte preservation

### 2.2 SST emit correctness

For every emitted SST:
- xTranslator v1.6.0 loads without warning (or ESP-ESM Translator 4.35 for non-xTranslator games)
- Entry count matches expected (validator runs over export to confirm)
- Round-trip parse via our reader produces equivalent entries (validator gate)

### 2.3 AI pipeline behavior

For every batch run:
- Every translated entry passes all 8 validator gates OR is in manual-review queue
- No silent skips (every TranslationUnit is accounted for: translated, partial, locked, or orphan)
- Cost tracking accuracy within 5% of provider-reported (for providers reporting exact cost)
- Cancellation is responsive (<200ms from button click to HTTP close)

### 2.4 GUI behavior

- All UI strings present in both en and zh-cn .po
- All three themes render without visual breakage at 100%, 125%, 150%, 200% DPI scaling
- All tabs navigable via keyboard alone
- Two-stage close dialog correctly detects unsaved work

### 2.5 Persistence integrity

- `project.toml` round-trips through TOML write→read with no data loss
- `memory.sqlite` schema migration tested for at least one schema version bump
- KB migration tested with synthetic legacy bgs-kb cache (created via fixture script)

### 2.6 Permission boundaries

- `profiles/.env` permissions verified at startup (POSIX 0600, NTFS user-only ACL)
- CLI rejects `--api-key <value>` (only `--api-key-env <VARNAME>` accepted)
- profiles.toml load rejects any field that looks like a literal key

---

## 3. Fixture inventory

| Fixture | Path | Purpose |
|---|---|---|
| adwryos plugin | `D:\Starfield MO2\mods\adwryos-cc\adwryos.esm` | Starfield parser + SST emit round-trip |
| Starfield xTranslator SSTs | `D:\SteamLibrary\steamapps\common\Starfield\Tools\xTranslator-313-1-4-5-alpha-1694868294\_xTranslator\UserDictionaries\Starfield\` | Reference dictionaries; binary diff target |
| (TODO) Skyrim SE test plugin | TBD | Skyrim parser correctness |
| (TODO) Morrowind test plugin | TBD | TES3 parser + ESP-ESM TES3 SST verification |
| (TODO) BSA-internal test plugin | TBD | Future: BSA extraction handling |

Test fixtures that are not on local disk (Skyrim, FO4, Morrowind plugins) are tracked as known gaps; tool ships with synthetic minimal plugins generated programmatically for CI tests.

---

## 4. Per-PR acceptance gate

Every PR that touches:

| Touches | Required tests |
|---|---|
| `parsers/` | All per-game schema YAML manifests still load. Walk against any local fixture plugin succeeds. |
| `sst/` | Round-trip test against adwryos SST. Hex-dump assertions still pass. |
| `pipeline/` | Mask round-trip test. Validator gates execute against synthetic items. |
| `kb/` | Glossary 4-layer composition test. |
| `gui/` | i18n coverage check. Theme rendering smoke. |
| `cli/` | Envelope shape test (success + each error code). |
| Any | `mypy` clean. `ruff` clean. Test suite green. |

CI runs `pytest -x --cov=bgs_translator` with min 80% coverage gate.

---

## 5. Pre-release acceptance

Before any release tagged as v1.0.0:

1. All 5 verification spikes have passed and their results are checked into `docs/spikes/`
2. The end-to-end user story from `00-overview.md` runs to completion against the adwryos fixture: translation completes, SST loads in xTranslator, Finalize succeeds, Starfield runs the mod with translated text visible.
3. Same end-to-end story tested against at least one Skyrim SE plugin (any community-available test plugin)
4. Tk panel tested on Windows + Linux + macOS (Tk version permitting; macOS Tk has documented quirks)
5. All `14-open-questions.md` items either resolved or explicitly documented as v1.0.x scope-out
6. `13-agent-skill-outline.md` skill is materialized, registered with the `bgs-modding-superpowers` plugin, and tested by routing a real "translate this mod" request through it

A release that doesn't meet all six is not a v1.0.0; it's a v0.x preview.
