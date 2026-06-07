# PRD Amendments

This file consolidates updates to the v1 PRD from Chunk A verification spikes (2026-06-07) and any subsequent execution-time discoveries. Downstream chunks MUST read this file in addition to the original PRD; in case of contradiction, AMENDMENTS wins.

Source of truth ranking (per README §"Source-of-truth ranking") updated:
1. This `AMENDMENTS.md` (amendments win over original PRD)
2. The 15 original PRD files (`00-overview.md` through `14-open-questions.md`)
3. Code (when implementation begins)
4. Earlier conversation transcripts (clarification only)

---

## Amendment 1 — Morrowind output format: ESP-ESM XML, NOT SST

**Source**: Spike 1, `docs/spikes/spike-findings.md` §1.

**Original assertion** (`00-overview.md`, `02-parser-and-coverage.md`, `03-sst-output.md`): SST is sole deliverable across all 9 BGS games.

**Amendment**: Morrowind is excluded. SST is the deliverable for 8 games (Oblivion, Skyrim LE/SE/AE/VR, FNV, FO3, FO4, FO76, Starfield — TES4-family). Morrowind exclusively emits **ESP-ESM Translator's native XML database format** (`.xml` or `.eet`-as-XML interchange).

**Rationale**: xTranslator does not support TES3, so SSTs with TES3 signatures (`NAME`, `FNAM`, `DESC`, `BNAM`) do not exist in the wild. ESP-ESM Translator's 2017-vintage SST reader was tested only against TES4-family schemas. The entire Morrowind translator community works in `.eet`/`.xml` formats.

**Affected chunks**:
- Chunk E (TES3 Morrowind parser) — adds sub-task "ESP-ESM XML writer"
- Chunk F (SST writer) — explicitly scoped to TES4-family only

**Format reference**: ESP-ESM Translator stores dictionaries as XML with TES3-shaped keys (`NAME`, `FNAM`, `DESC`, `BNAM`, `RNAM`, `ANAM`, `INDX`, `SCPT`, `INFO`, `CELL`, `DIAL`, `GMST`, `TEXT`). Reference dictionaries: `BDD_Morrowind_*` series on Nexus. Chunk E owner will inspect a real `.eet`-as-XML file to derive exact schema.

---

## Amendment 2 — SST byte layout: authoritative source confirmed

**Source**: Spike 2, `docs/spikes/spike-findings.md` §2.

**Original PRD** (`03-sst-output.md`) had multiple "unverified" hedges. Now resolved.

### 2.1 SSU magic constants (CONFIRMED)

From `TESVT_Const.pas`:
```pascal
VocabUserHeader:  cardinal = $32555353; // SSU2
VocabUserHeader2: cardinal = $33555353; // SSU3
VocabUserHeader3: cardinal = $34555353; // SSU4
VocabUserHeader4: cardinal = $35555353; // SSU5
VocabUserHeader5: cardinal = $36555353; // SSU6
VocabUserHeader6: cardinal = $37555353; // SSU7
VocabUserHeader7: cardinal = $38555353; // SSU8
VocabUserHeader8: cardinal = $39555353; // SSU9 ← current emit target
```

Reader must accept SSU2–SSU9. Writer emits SSU9 only.

### 2.2 Header byte layout (CONFIRMED)

```
+0   (4 bytes)    magic        UInt32 LE = $39555353 ("SSU9")
+4   (1 byte)     flag         byte = 0 (legacy placeholder, always 0 on write)
+5   (4 bytes)    masterCount  Integer LE
+9   per-master  (masterCount times):
       (4 bytes)  byteSize     Integer LE = length(name) * sizeof(char) = bytes
       (N bytes)  master_str   UTF-16LE (no null terminator)
+M   (4 bytes)    colabCount   Integer LE
     per-colab  (colabCount times):
       (4 bytes)  colabId      Integer LE
       (4 bytes)  byteSize     Integer LE
       (N bytes)  label_str    UTF-16LE
+E   entries (until EOF — NO entry-count field)
```

Writer pseudocode in `03-sst-output.md` §6 must be rewritten to follow this order exactly.

### 2.3 Per-entry byte layout (CONFIRMED for fixed-size portion)

```
+0   (1 byte)     listIndex    byte (0 translated, 1 partial, 2 source-only/protected)
+1   (24 bytes)   rEspPointerLite struct (opaque to writer; CopyMemory'd from sk.esp)
+25  (1 byte)     colabId      byte
+26  (1 byte)     sParams      sStrParams (Pascal SET ≤8 elements packed in 1 byte)
+27  (4 bytes)    src_size     Integer LE = byte count of src
+31  (src_size)   src          UTF-16LE
     (4 bytes)    dst_size     Integer LE
     (dst_size)   dst          UTF-16LE
```

Fixed-size per entry = 31 bytes. No padding, no separator.

### 2.4 rEspPointerLite struct internal layout (EMPIRICAL — Pascal declaration not yet found)

24 bytes total, decoded by triangulation against entries in `srb_showreadbooks_en_zhhans.sst`:

| Struct offset | Width | Content |
|---|---|---|
| 0–7 | 8 bytes | unknown (record-pointer / flags / index — values like `00 00 00 00 00 08 00 02` observed) |
| 8–11 | 4 bytes | record signature ASCII (e.g., "PERK", "TES4") |
| 12–15 | 4 bytes | subrecord type ASCII (e.g., "EPF2", "CNAM") |
| 16–19 | 4 bytes | FormID UInt32 LE |
| 20–23 | 4 bytes | rHash UInt32 LE (string hash of EditorID; observed identical across two PERK entries sharing edid) |

**Chunk F owner action**: continue Pascal-source hunting for `rEspPointerLite` declaration (likely in `TESVT_Typedef.pas`, not yet located in repo root listing) before final implementation. If unobtainable, fit the 8 leading bytes empirically by generating xTranslator's own output for known inputs and diffing.

### 2.5 sParams width: 1 byte (CONFIRMED)

Pascal `sStrParams` is a Set type with 6 observed elements (`pending`, `translated`, `lockedTrans`, `incompleteTrans`, `validated`, `oldData`). Delphi packs sets of ≤8 elements into 1 byte. The writer strips `validated` before persistence (`tmpParams := sk.sparams - [validated]`).

PRD §1.1 "1 byte or 4 bytes" hedge → resolved to **1 byte**. The `{$MINENUMSIZE}` directive only affects enums, not sets.

### 2.6 stringHash algorithm: TBD

Function body not yet located in fetched units (`TESVT_SSTFunc.pas`, `TESVT_Const.pas`, `TESVT_FastSearch.pas`, `TESVT_Utils.pas`, `TESVT_EspStruct.pas` all checked). Likely candidates remaining: `TESVT_Codepage.pas`, `TESVT_Streams.pas`, `TESVT_TranslateFunc.pas`, or an unlisted `TESVT_Typedef.pas`.

**Chunk F owner action** — pick whichever is cheaper:
- (a) Continue searching the Pascal source for `function stringHash(`. Reference: https://github.com/MGuffin/xTranslator
- (b) Empirical fit: pick a known EditorID, find corresponding SST entry, read rHash bytes at struct offset 20–23, test candidate algorithms (FNV-1a, CRC32, djb2, BKDR, Pascal `THashBobJenkins`, Adler32) against observed rHash. Iterate until match.

### 2.7 sanitize_formid behavior: TBD

`TESVT_Const.pas` references `bApplySstOldMasterFix: boolean = true; // Normalize FormiD in dictionaries for record without Edidname (typically: INFO:NAM1)`. The actual function lives in a non-fetched unit. Likely behavior: `formid AND $00FFFFFF` (strip master-index high byte), but conditional on EditorID absence.

**Chunk F owner action**: same as 2.6 — search Pascal source OR empirically test against an SST entry whose FormID has master-index ≥ 0x01.

### 2.8 No entry-count field (CONFIRMED)

The writer streams entries directly after the colabLabel section. The reader must scan until EOF to know how many entries exist. PRD §1 had assumed an implicit count; correction: no count is written; EOF-terminated entry stream.

---

## Amendment 3 — Provider matrix corrections

**Source**: Spike 4, `docs/spikes/spike-findings.md` §4.

Affected file: `09-providers-and-keys.md`.

### 3.1 OpenAI Responses API uses `text.format` envelope

Original PRD §6.3 implied `response_format: json_schema`. **Wrong**: that's chat-completions syntax. Responses API uses `text.format: {type: "json_schema", name, schema, strict: true}`. Any client code that sets `response_format` for the `openai` sdk_kind is bugged.

### 3.2 OpenRouter `usage: {include: true}` is deprecated

PRD assumed opt-in. Reality: `usage` with `cost` + `cost_details` is now always returned. Any code that sets `usage: {include: true}` or `stream_options: {include_usage: true}` for OpenRouter is dead code.

### 3.3 Anthropic prompt-caching minimum varies by model

PRD hardcoded "min 1024 tokens." Reality:
- 1024: Sonnet 4.5/4.6, Opus 4.8
- 2048: Haiku 3.5
- 4096: Opus 4.5/4.6/4.7, Haiku 4.5, Mythos Preview

Implementation: probe at runtime; don't hardcode the threshold in client code.

### 3.4 DeepSeek hard guard: no `json_schema` mode

DeepSeek does NOT support `response_format: json_schema`. Profile loader must refuse load if `base_url` matches `api.deepseek.com` AND `json_mode = "json_schema"`. Force `json_mode = "json_object"`.

### 3.5 OpenRouter cost denominated in credits

Relabel any field claiming "usd" — OpenRouter `usage.cost` is credits. For non-BYOK accounts it's 1:1 USD; for BYOK accounts, `usage.cost_details.upstream_inference_cost` is the source-of-truth USD.

### 3.6 Rate-limit header parsing is per-`sdk_kind`

- OpenAI: `x-ratelimit-*`
- Anthropic: `anthropic-ratelimit-*` + `retry-after`
- Gemini: no documented headers (per-project quota only)
- DeepSeek: no documented headers; concurrency-based throttling
- OpenRouter: no documented headers (URL `/docs/api-reference/limits` → 404)

The dispatcher's rate-limit observer must dispatch per `sdk_kind` to the correct header-parsing path. Gemini / DeepSeek / OpenRouter probes return `rate_limit_headers_observed: false`; the probe still measures effective ceilings via test requests.

### 3.7 Cancellation billing semantics not documented

No provider documents what happens when the client closes the connection mid-flight (whether the in-flight tokens are billed). `09-providers-and-keys.md` §6.2 `cancellation_clean: true` capability is a runtime-only observation; the probe must measure it (does the provider return a partial response, or is the request dropped silently?).

---

## Amendment 4 — bgs-kb integration filename + readiness

**Source**: Spike 5, `docs/spikes/spike-findings.md` §5.

Affected file: `05-glossary-and-kb.md`.

### 4.1 SQLite filename: `kb.sqlite` (not `store.sqlite`)

PRD §4.1 referenced `packs/*/store.sqlite`. The actual build output is `kb.sqlite`. Translator's direct-SQLite reader must glob the correct name.

### 4.2 bgs-kb-side prep is a hard prerequisite for Chunk G

Translator Chunk G (KB glossary integration) cannot ship without bgs-kb-side changes landing first:

1. `record.schema.json` — extend `kind` enum to include `glossary-entry`; add optional `glossary` block under root (currently `additionalProperties: false`); add `if/then` schema requiring `glossary` iff `kind === "glossary-entry"`.
2. `tools/bgs-kb-mcp/src/types/enums.ts` — add `localization` (or `glossary`) to `DOMAIN_VALUES` (currently closed enum with no localization-flavored value).
3. `tools/bgs-kb-mcp/src/build/types.ts` — add `kind` and `glossary` to `SourceRecord`.
4. `tools/bgs-kb-mcp/src/build/sqlite.ts` — add `kind TEXT` column to `records`; add `glossary_entries` and `glossary_aliases` tables with case-folded index on `(alias)`.
5. `tools/bgs-kb-mcp/src/tools/query.ts` — wire the `kinds` filter into the SQL WHERE clauses (currently declared in Zod but a no-op in SQL).
6. `tools/bgs-kb-mcp/src/tools/get.ts` — surface `kind` and `glossary` in returned record shape.
7. Tests across `tests/unit/enums.test.ts`, `validate-records.test.ts`, `build-pack.test.ts`, `sqlite.test.ts`, `tool-query.test.ts`, `tool-get.test.ts`, `manifest.test.ts`.
8. Seed pack `bgs-kb-l10n-skyrim-en-zhcn` with 5–10 example glossary entries.

Latent bug discovered along the way: the existing `kind` field is declared in YAML frontmatter and validated, but is NOT persisted to SQLite and NOT applied as a filter in `bgs_kb_query`. Adding `glossary-entry` exposes this gap; the fix (column + SQL clause + getter) lands as part of the bgs-kb-side prep PR.

### 4.3 Translator Chunk G can develop in parallel against fixture SQLite

Until bgs-kb prep lands, Chunk G builds against a stub SQLite shaped per the proposed `glossary_entries` + `glossary_aliases` schema. Switch to real `kb.sqlite` after prep merges. Translator v1.0 release blocked on the seed pack being published.

---

## Amendment 5 — Implementation chunks updated

**Source**: implied by amendments 1–4.

Affected file: `12-implementation-chunks.md`.

### 5.1 Chunk E expanded

Original Chunk E was TES3 parser only. Now includes:
- 1. TES3 record / subrecord walker (unchanged)
- 2. Morrowind schema (`parsers/schemas/morrowind.py`) (unchanged)
- 3. Inline-string extraction (no STRINGS file) (unchanged)
- **4. ESP-ESM XML writer** (NEW — `output/eet_xml/writer.py`)
- **5. ESP-ESM XML reader** (NEW — for round-trip validation against existing community dictionaries)

Done-when adds: emitted XML loads in ESP-ESM Translator 4.35 without warning; entries visible in dictionary view; Finalize produces working Morrowind translation.

### 5.2 Chunk F scope clarified

Original Chunk F was SST writer/reader. Now explicit:
- Scope: **TES4-family games only** (Skyrim LE/SE/AE/VR, FNV, FO3, FO4, FO76, Starfield). Oblivion was incorrectly included in "TES4-family for SST" — needs verification (xTranslator README claims Oblivion not supported, but PRD treated as TES4-family for some reason; check spike-findings Spike 1 evidence chain).
- Sub-task added: empirical `stringHash` reverse-engineering against fixture SSTs (Amendment 2.6).
- Sub-task added: empirical `sanitize_formid` verification (Amendment 2.7).
- Sub-task added: `rEspPointerLite` 8-byte leading-junk decoding (Amendment 2.4).

### 5.3 Chunk G dependency surfaced

Chunk G is blocked on bgs-kb-side prep PR (Amendment 4.2). Translator can develop against fixture stub in parallel; switch to real pack after prep merges. v1.0 release gate: bgs-kb prep merged + seed l10n pack published.

### 5.4 Oblivion SST coverage question

xTranslator does not support Oblivion per its own README ("not supported"). Original PRD treated Oblivion as TES4-family for SST emission. **Open question for Chunk D**: confirm whether ESP-ESM Translator (which DOES support Oblivion) reads xTranslator-format SSTs with Oblivion record signatures. If yes, SST is fine for Oblivion. If no, Oblivion follows the Morrowind path and emits ESP-ESM XML.

Working assumption pending Chunk D verification: Oblivion emits XML (safer fallback). Revisit if cross-tool test confirms SST works.

---

## How to use AMENDMENTS in subagent dispatch

When dispatching a fixer / implementer subagent for any chunk:

1. Include `AMENDMENTS.md` as required reading alongside the chunk's referenced PRD sections.
2. State: "If AMENDMENTS contradicts the PRD, AMENDMENTS wins."
3. New discoveries during施工 land here first; then promoted to the corresponding PRD file once the chunk closes.

When closing a chunk, audit the chunk's discovered amendments and decide whether to:
- Land them in the original PRD file (if architectural / structural).
- Leave in AMENDMENTS (if execution-time tuning that the original PRD intentionally left open).

---

## Changelog

- **2026-06-07** Initial AMENDMENTS file from Chunk A spike findings (Amendments 1–5).
