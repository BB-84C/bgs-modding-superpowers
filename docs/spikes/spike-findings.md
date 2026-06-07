# Verification Spike Findings — bgs-translator

Date: 2026-06-07
Branch: feat/translator-tool
Scope: Spikes 1, 2, 4, 5 (Spike 3 is full E2E, deferred to Chunk K).

Each spike's result is summarized below with PRD-impacting actions.

---

## Spike 1 — ESP-ESM Translator reads SST with TES3 signatures

**Verdict: NO** — xTranslator does not support TES3, therefore SSTs with TES3 signatures do not exist in the wild, therefore ESP-ESM Translator's 2017-vintage SST reader was tested only against TES4-family schemas.

**Evidence**:
- xTranslator's own README / Nexus pages confirm TES4-family-only scope (Oblivion-Skyrim-FO3-FNV-FO4-FO76-Starfield).
- ESP-ESM Translator v3.10 changelog (2017): "The tool can now open last version of dictionnary file from xTranslator". One line. Never expanded.
- All Morrowind translation workflows (BDD_Morrowind_EET, Tamriel Rebuilt translators, Confrérie des Traducteurs) use `.eet` or `.xml` exclusively.
- Jan 2025 Epervier 666 ↔ Morrowind translator dialogue on Confrérie forum (post-EET v4.35) discusses xml/eet formats only.

**Action**:
- `02-parser-and-coverage.md` and `00-overview.md` must explicitly carve Morrowind out of "SST as sole deliverable".
- Morrowind output format is ESP-ESM Translator's native XML database format.
- Add a "Morrowind XML writer" sub-task to Chunk E.

**Confidence**: HIGH on structural argument. MEDIUM-HIGH on XML recommendation.

**Sources audited**: 17 URLs (GitHub MGuffin/xTranslator, Nexus pages 134/313/921, Confrérie forum, UESP TES3 file format, OpenMW forum, NamuWiki, Fallout Wiki).

---

## Spike 2 — SST byte-level verification via hex dump

**Verdict: PARTIALLY RESOLVED** — header structure fully decoded against authoritative Pascal source from `MGuffin/xTranslator`. Per-entry rEspPointerLite struct (24 bytes) decoded by triangulation against multiple entries. `stringHash` algorithm body remains in an unfetched Pascal unit; must be transcribed during Chunk F or empirically reverse-engineered.

### CONFIRMED (authoritative source: `TESVT_SSTFunc.pas` + `TESVT_Const.pas`)

**SSU magic constants** (from `TESVT_Const.pas`):
```pascal
VocabUserHeader:  cardinal = $32555353; // SSU2
VocabUserHeader2: cardinal = $33555353; // SSU3
VocabUserHeader3: cardinal = $34555353; // SSU4
VocabUserHeader4: cardinal = $35555353; // SSU5
VocabUserHeader5: cardinal = $36555353; // SSU6
VocabUserHeader6: cardinal = $37555353; // SSU7
VocabUserHeader7: cardinal = $38555353; // SSU8
VocabUserHeader8: cardinal = $39555353; // SSU9 ← current
```

PRD §1 magic-version assumption was correct (`53 53 55 39` = "SSU9" LE).

**Header structure** (from `SaveSSTFile` in `TESVT_SSTFunc.pas`):
```
+0   (4 bytes)    magic        UInt32 LE = $39555353 ("SSU9")
+4   (1 byte)     flag         byte = 0 (v4 placeholder)
+5   (4 bytes)    masterCount  Integer LE
+9   per-master:
       (4 bytes)  byteSize     Integer LE = length(name) * sizeof(char) = bytes
       (N bytes)  master_str   UTF-16LE (no null terminator)
     ...
+M   (4 bytes)    colabCount   Integer LE
     per-colab:
       (4 bytes)  colabId      Integer LE
       (4 bytes)  byteSize     Integer LE
       (N bytes)  label_str    UTF-16LE
+E   entries (until EOF — NO entry-count field written)
```

Empirically verified against `srb_showreadbooks_en_zhhans.sst` (354 bytes, 3 masters, 0 colab labels, 3 entries).

**Per-entry structure** (from `SaveSSTFile` writer loop):
```
+0   (1 byte)     listIndex    byte (0 = translated, 1 = partial, 2 = source-only/protected)
+1   (24 bytes)   rEspPointerLite struct (CopyMemory'd; opaque)
+25  (1 byte)     colabId      byte
+26  (1 byte)     sParams      sStrParams (Pascal SET, 1 byte: ≤8 elements)
+27  (4 bytes)    src_size     Integer LE = byte count of src
+31  (src_size)   src          UTF-16LE
     (4 bytes)    dst_size     Integer LE
     (dst_size)   dst          UTF-16LE
```

Fixed metadata per entry = 31 bytes. Then src + 4 + dst.

**sParams width**: **1 byte CONFIRMED** (was unverified in PRD).

Pascal `sStrParams` is a Set type with 6 observed elements (`pending`, `translated`, `lockedTrans`, `incompleteTrans`, `validated`, `oldData`). Delphi packs sets of ≤8 elements into 1 byte. The writer notes `tmpParams := sk.sparams - [validated]` (the `validated` flag is stripped before persistence).

PRD §1 must be updated: `sParams` is **always 1 byte**, regardless of `{$MINENUMSIZE}` directive (which only affects enums, not sets).

**colabId width**: 1 byte CONFIRMED. Loader uses `colabId: byte`.

**listIndex width**: 1 byte CONFIRMED. Reader indexes a 3-slot list via `vlist[l].add(sk)`.

**No entry count field**: CONFIRMED. Writer streams entries directly after colab section; reader must EOF-terminate.

### rEspPointerLite layout (24 bytes, empirically decoded — Pascal record definition not in fetched units)

Triangulated from entries 1 and 2 of `srb_showreadbooks_en_zhhans.sst`:

| Offset within struct | Bytes | Field hypothesis | Evidence |
|---|---|---|---|
| 0–5 | 6 bytes | unknown (record-pointer / flags) | `00 00 00 00 00 08` consistent across entries |
| 6–7 | 2 bytes | unknown | `00 02` consistent across entries |
| 8–11 | 4 bytes | **record signature** ASCII | "PERK" / "TES4" observed |
| 12–15 | 4 bytes | **subrecord type** ASCII | "EPF2" / "CNAM" observed |
| 16–19 | 4 bytes | **FormID** UInt32 LE | `00 00 01 00` / `01 00 01 00` differ between entries; master-index byte plausible at offset 19 |
| 20–23 | 4 bytes | **rHash** UInt32 LE | `6A 8B F1 EF` = 0xEFF18B6A; **identical** across e1 + e2 → likely hash of EditorID (both entries share edid) |

Read-side implication: Chunk F must transcribe `rEspPointerLite` declaration from `TESVT_Typedef.pas` (or wherever the Pascal record lives) before writer can emit byte-exact output. Workaround if source unobtainable: empirically reverse-engineer by generating known inputs through xTranslator and diffing.

### stringHash algorithm — NOT YET FOUND in fetched units

Searched: `TESVT_SSTFunc.pas`, `TESVT_Const.pas`, `TESVT_FastSearch.pas`, `TESVT_Utils.pas`, `TESVT_EspStruct.pas`. Function body absent from all.

Likely candidates remaining: `TESVT_Codepage.pas`, `TESVT_Streams.pas`, `TESVT_TranslateFunc.pas`, `TESVT_Typedef.pas` (not visible in repo root listing — may live in subfolder).

**Action for Chunk F**: continue Pascal-source hunting OR fit empirically. Empirical fit recipe:
1. Take a known EditorID (e.g., "PerkEdid01") from xTranslator GUI.
2. Locate corresponding entry in the SST.
3. Read 4 bytes at rHash position (struct offset 20–23 within rEspPointerLite).
4. Test against candidate algorithms: FNV-1a, CRC32, djb2, BKDR, Pascal's `HashName`, Embarcadero RTL `THashBobJenkins`, Adler32. Compare to observed rHash.

### sanitize_formid behavior — STILL UNVERIFIED

Reference to `bApplySstOldMasterFix` constant found in `TESVT_Const.pas`: "Normalize FormiD in dictionaries for record without Edidname (typically: INFO:NAM1)". Implies normalization exists but is conditional (only when EditorID is absent). The function implementing the normalization is in a non-fetched unit.

Empirical observation needed: when an entry's FormID has a non-zero high byte, does the rHash use raw FormID or `formid AND $00FFFFFF`? Test requires an SST entry with master-index ≥ 0x01 in its FormID AND a known EditorID. Defer to Chunk F.

### PRD updates required

1. `03-sst-output.md` §1.1: replace "sParams width unverified" hedge with confirmed `sParams = 1 byte (sStrParams Pascal SET ≤8 elements)`.
2. `03-sst-output.md` §1.2: rewrite entry layout to reflect the 24-byte `rEspPointerLite` struct shape (sig + subrec + formid + rHash + 8 unknown bytes).
3. `03-sst-output.md` §1.3: add "no entry count; reader scans to EOF" note.
4. `03-sst-output.md` §6: rewrite writer pseudocode to match `SaveSSTFile` Pascal source verbatim (header order: magic, flag, masters, colabs, entries).
5. `03-sst-output.md` §1.4: mark `stringHash` as **TBD** with empirical-fit fallback in Chunk F.

**Confidence**: HIGH on header structure (authoritative source). HIGH on per-entry fixed metadata sizes (authoritative source + hex verification). MEDIUM on rEspPointerLite internal layout (empirical triangulation; Pascal record declaration not yet found). LOW on stringHash + sanitize_formid (algorithms not yet transcribed).

---

## Spike 4 — Provider capability matrix

**Verdict: PASS** with 5 PRD update items.

Full matrix in librarian report (see commit history under spikes/ if archived); summary of corrections to apply:

| # | Update | File / location |
|---|---|---|
| 1 | OpenAI Responses API uses `text.format` envelope, NOT `response_format` (which is chat-completions) | `09-providers-and-keys.md` §6.3 + any client code references |
| 2 | OpenRouter `usage: {include: true}` is **deprecated** — usage with `cost` + `cost_details` is always returned | `09-providers-and-keys.md` §6.2 + §7 |
| 3 | Anthropic prompt-caching minimum varies by model: 1024 (Sonnet 4.5/4.6, Opus 4.8), 4096 (Opus 4.5/4.6/4.7, Haiku 4.5). PRD hardcoded 1024 only. | `09-providers-and-keys.md` §3.1 — note runtime probe required |
| 4 | DeepSeek does NOT support `json_schema` strict mode; only `json_object`. Add hard guard at profile load. | `09-providers-and-keys.md` §2.2 rule 5 |
| 5 | OpenRouter cost denominated in credits (1:1 USD for non-BYOK); relabel "cost_for_probe_usd" field | `09-providers-and-keys.md` §6.2 + §7 |

Per-provider rate-limit headers vary (not universally `x-ratelimit-*`):
- OpenAI: `x-ratelimit-*` ✓
- Anthropic: `anthropic-ratelimit-*` (prefix) + `retry-after`
- Gemini: no documented headers (per-project quota only)
- DeepSeek: no documented headers; concurrency-based throttling
- OpenRouter: no documented headers; URL `/docs/api-reference/limits` returns 404

Cancellation billing semantics: NOT documented by any provider; must be probed at runtime.

**Confidence**: HIGH for OpenAI / Anthropic / OpenRouter. MEDIUM-HIGH for Gemini. MEDIUM for DeepSeek.

**Sources audited**: 13 provider docs URLs + 3 Exa search refinements.

---

## Spike 5 — bgs-kb integration readiness

**Verdict: STRUCTURALLY READY, requires bgs-kb-side prep PR before Chunk G can ship.**

bgs-kb located at `D:\awesome-bgs-mod-master\tools\bgs-kb-mcp\` (TS/Node MCP) + `knowledge/bgs-kb/` (record sources as Markdown + YAML frontmatter).

### Current record kinds (from `knowledge/bgs-kb/schema/record.schema.json`)
- `rule`, `workflow`, `gotcha`, `explanation`, `source-map`, `rule-candidate`

`glossary-entry` not present.

### Pack store schema (`tools/bgs-kb-mcp/src/build/sqlite.ts`)

Tables: `records`, `record_domains`, `record_games`, `record_excludes`, `record_engine_families`, `pack_meta`, FTS5 `records_fts`.

**Critical findings**:
- `kind` field declared in YAML frontmatter, validated by Ajv, but **NOT persisted to SQLite** and **NOT applied as a filter** in `bgs_kb_query` (Zod accepts `kinds` arg but SQL clauses ignore it). Latent gap.
- SQLite file is `kb.sqlite`, NOT `store.sqlite` (PRD §4.1 drift).
- `DOMAIN_VALUES` enum is closed — no localization/glossary value available; must add one.

### Plan to add `glossary-entry` (medium complexity, ~10 files)

1. `record.schema.json` — extend `kind` enum; add optional `glossary` block (root is `additionalProperties: false`); use `if/then` to require `glossary` iff `kind === "glossary-entry"`.
2. `schema/fixtures/` — add `fixture-glossary-entry.json` + example record.
3. `tools/bgs-kb-mcp/src/types/enums.ts` — add a `localization` (or `glossary`) domain.
4. `tools/bgs-kb-mcp/src/build/types.ts` — add `kind` + `glossary` to `SourceRecord`.
5. `tools/bgs-kb-mcp/src/build/sqlite.ts` — add `kind` column to `records`; add new tables `glossary_entries` + `glossary_aliases` with index on `(alias)` case-folded.
6. `tools/bgs-kb-mcp/src/tools/query.ts` — wire the `kinds` filter into actual SQL (currently a no-op).
7. `tools/bgs-kb-mcp/src/tools/get.ts` — surface `kind` + `glossary` in returned record shape.
8. `tests/unit/` — `enums.test.ts`, `validate-records.test.ts`, `build-pack.test.ts`, `sqlite.test.ts`, `tool-query.test.ts`, `tool-get.test.ts`.
9. Documentation addendum.
10. Optional: seed example pack `bgs-kb-l10n-skyrim-en-zhcn` with 5-10 entries for translator integration tests.

### Risks

- Adding `kind` column requires rebuilding all packs (manifest SHA-256 changes → `manifest-index.json` release changes). Coordinate with maintainers.
- DRY drift: `kind`, `domains`, `games` enums duplicated across JSON Schema, Zod, TS enums. Edits must land in all three.
- `kbsqlite` vs `store.sqlite` filename drift between PRD §4.1 and actual build output: PRD must be corrected.

### Recommendation

Translator Chunk G can develop against fixture/stub SQLite shaped like the proposed `glossary_entries` / `glossary_aliases` tables in parallel with bgs-kb-side prep. But translator v1.0 release must NOT depend on bgs-kb-packaged glossary entries until: (a) bgs-kb feature branch lands schema + SQLite + query/get wiring + tests; (b) at least one seed l10n pack ships; (c) translator Chunk G points at real `kb.sqlite` files.

**Confidence**: HIGH (direct source inspection of every claim).

---

## Aggregated PRD updates triggered by Chunk A

Will land in next commit (`docs(translator-tool): apply spike-driven PRD corrections`):

1. `00-overview.md` — Morrowind carved out of "SST as sole deliverable"; emits ESP-ESM XML instead.
2. `02-parser-and-coverage.md` — Morrowind output format = XML; cross-link to ESP-ESM XML schema.
3. `03-sst-output.md` — header + entry byte layout rewritten against authoritative Pascal source; `sParams = 1 byte` confirmed; `stringHash` marked TBD with empirical-fit fallback.
4. `05-glossary-and-kb.md` — SQLite filename `kb.sqlite` (was `store.sqlite`); cross-reference bgs-kb-side prep list.
5. `09-providers-and-keys.md` — 5 provider-matrix corrections per Spike 4.
6. `12-implementation-chunks.md` — Chunk E gets new sub-task "Morrowind XML writer"; Chunk G's `glossary-entry` prereq spelled out.

---

## Chunk A: COMPLETE

Dependencies for downstream chunks now resolved (except `stringHash` body, which is owed to Chunk F as an empirical sub-task).

**Next**: Chunk B (repository skeleton).
