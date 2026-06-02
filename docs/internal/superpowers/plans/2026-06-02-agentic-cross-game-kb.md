# Agentic Cross-Game BGS Knowledge Base — Implementation Plan

- **Spec:** `docs/internal/superpowers/specs/2026-06-02-agentic-cross-game-kb-design.md`
- **Roadmap entry:** `docs/internal/roadmap.md` § 2026-06-02
- **Source list reference:** `docs/internal/roadmap.md` § Appendix
- **Branch model:** Each phase lands on a feature branch `feat/kb-<phase>-<short-name>`, merged to `main` via fast-forward after acceptance.
- **Architecture-only commits already on `main`:** `d3b5abc`, `7ec31d6`, `541901a`.

## How to read this plan

Each phase has: **Goal**, **Dependencies**, **Tasks** (numbered, bounded, individually committable), **Acceptance criteria** (semantic — what proves it works), **Deliverables** (artifacts that survive), **Risks**, and **Estimated commits**.

If a task is "go to spec section X for details", that means the spec is the source of truth for the detail. This plan stays focused on the implementation sequencing.

---

## KB-1 — Schema + seed records + pack-build CLI MVP

**Goal:** Author the record JSON Schema, extract ~50 seed records from existing project docs, and build a minimal pack-build CLI that turns a `records/` tree into `kb.sqlite` + `manifest.json`.

**Dependencies:** none (architecture-only commits already on `main`).

**Branch:** `feat/kb-1-schema-and-seed-records`

### Tasks

| # | Task | Bounded scope | Acceptance | Est. commits |
|---|---|---|---|---|
| **KB-1a** | Author `knowledge/bgs-kb/schema/record.schema.json` (JSON Schema Draft 2020-12) | Schema covers every field from spec §5.2 with enums, required-field constraints, format validators (semver, date) | `ajv-cli` validates 5 hand-authored test records: 1 universal, 1 with `excludes`, 1 with variants, 1 with `related`, 1 minimal | 1 |
| **KB-1b** | Author 10 proof-of-shape seed records under `knowledge/bgs-kb/packs/core/records/` | Mix of xEdit + load-order + Papyrus + archive-precedence; real content extracted from `xedit-knowledgebase.md` + `writing-bgs-load-order/SKILL.md`. Each record has structured `sources` populated. Each record validates against the schema. | All 10 validate; manual review confirms paraphrase quality (no verbatim copy); each `sources` URL resolves | 1-2 |
| **KB-1c** | Bootstrap `tools/bgs-kb-mcp/` package — TypeScript, mirror `tools/xedit-mcp/` structure | `package.json` + `tsconfig.json` + `src/index.ts` skeleton + `src/cli.ts` skeleton. Dependencies: `@modelcontextprotocol/sdk`, `zod`, `gray-matter` (YAML frontmatter parser), `js-yaml`, plus the chosen SQLite lib. | `npm install` succeeds; `npm run build` produces `dist/`; bare `node dist/cli.js --help` prints usage | 1 |
| **KB-1d** | SQLite lib selection smoke test | In `tools/bgs-kb-mcp/test-fixtures/`: a 5-line script that opens an in-memory SQLite, creates an FTS5 virtual table, inserts a row, runs a `MATCH` query. Run with `node:sqlite` first; if FTS5 is unavailable, fall back to `better-sqlite3`. Document the chosen lib in `tools/bgs-kb-mcp/README.md` + the spec. | Script exits 0 with the expected MATCH result | 1 |
| **KB-1e** | Implement `cli build <pack-root>` MVP | Reads `<pack-root>/records/**/*.md` via gray-matter; validates each frontmatter against the schema using `ajv`; resolves `applies_to_json` / `variants_json` / `sources_json` to JSON strings; opens `<pack-root>/kb.sqlite`; runs the schema DDL from spec §7; inserts records + FTS5 triggers; writes `<pack-root>/manifest.json` with sha256 of `kb.sqlite`. | `node dist/cli.js build knowledge/bgs-kb/packs/core` succeeds; produced `kb.sqlite` has 10 rows in `records` table; `records_fts` is populated; manifest sha256 matches | 1-2 |
| **KB-1f** | Implement `cli validate <pack-root>` + `cli info <pack-root>` | Validate exits non-zero on schema failure with a clear pointer to the failing file + path. Info prints a structured summary. | Both subcommands work on the core pack; failing fixture validates exit-code semantics | 1 |
| **KB-1g** | Unit tests for the CLI | Vitest suite covering: schema-fail rejection, missing-sources rejection, duplicate-id rejection, happy-path build, build determinism (same input → same sha256). | `npm test` in `tools/bgs-kb-mcp/` passes | 1 |
| **KB-1h** | Raw SQL smoke test preserved as integration test | A vitest integration test that calls `cli build` on the real core pack, opens the produced `kb.sqlite`, runs 3 FTS5 MATCH queries, asserts rank > 0 and the expected record id surfaces top-3. | Integration test passes; artifact preserved in `tools/bgs-kb-mcp/tests/integration/` | 1 |
| **KB-1i** | Expand seed records to ~50 covering all 4 Stage A core-pack domains (xedit, load-order, papyrus, engine) | Extract from `xedit-knowledgebase.md` + `writing-bgs-load-order/SKILL.md` + project memory. Mix domains, mix game scopes. Each record gets at least one `sources` entry pointing at a real project doc or external URL. **No fan-out yet — this is hand-curated to validate the shape.** | 50 records validate; build CLI produces a pack with all 50; sample queries return sensible top-3 results | 2-3 |

### Acceptance for KB-1 as a whole

Run the full matrix from spec §15 KB-1 acceptance against the produced core pack. Preserve artifacts under `.opencode/artifacts/kb/acceptance/kb-1/`:

- `01-schema-validation.json` — output of `ajv-cli` on every seed record.
- `02-build-output.json` — `cli info` output post-build.
- `03-fts-smoke.json` — results of 5 sample queries.
- `04-pack-tree.txt` — `tree` output of the core pack.
- `05-sha256.txt` — sha256 of the produced kb.sqlite + manifest.

### Deliverables

- `knowledge/bgs-kb/schema/record.schema.json`
- `knowledge/bgs-kb/packs/core/records/**/*.md` (~50 records)
- `knowledge/bgs-kb/packs/core/kb.sqlite` (built artifact; gitignored)
- `knowledge/bgs-kb/packs/core/manifest.json` (committed; serves as the canonical core-pack version pin)
- `tools/bgs-kb-mcp/` package (src + tests + dist + README)
- `.gitignore` update for `knowledge/bgs-kb/packs/*/kb.sqlite` (build artifact; manifest committed)

### Risks

- `node:sqlite` FTS5 unavailability → resolved at KB-1d with a 5-min check. Fallback: `better-sqlite3` with `node-pre-gyp`.
- Seed-record paraphrase quality → manual review at KB-1b + KB-1i checkpoints; one full pass through the 50 records before committing.
- Schema overfit to first 10 records → KB-1i expands to 50; the schema must survive that without changes, otherwise iterate.

### Estimated commits

~10-12 small commits. ~3-5 working sessions.

---

## KB-2 — `bgs-kb-mcp` server with retrieval tools

**Goal:** Stand up `tools/bgs-kb-mcp/` as a real stdio MCP server with `bgs_kb_status` / `bgs_kb_query` / `bgs_kb_get`, register it alongside `xedit-mcp` in all three harness manifests, and update the portable plugin build to include core pack + bgs-kb-mcp dist.

**Dependencies:** KB-1 complete (schema + seed records + build CLI proven).

**Branch:** `feat/kb-2-mcp-server`

### Tasks

| # | Task | Bounded scope | Acceptance | Est. commits |
|---|---|---|---|---|
| **KB-2a** | Pack discovery module | `src/pack-discovery.ts`: scans bundled / cache / `$BGS_KB_USER_PACKS` roots, validates each pack's `manifest.json`, enforces `schemaVersion` + `minPluginVersion` gates, detects `packId` collisions, returns `LoadedPack[]`. | Unit tests for: collision detection, schema-version refusal, plugin-version refusal, missing-manifest skip, integrity (sha256) verification. | 1-2 |
| **KB-2b** | SQLite session module | `src/sqlite-session.ts`: opens read-only connections to each loaded pack's `kb.sqlite`, exposes a query interface (parameterized statements). Connection lifecycle management. | Unit tests: open/close per pack, query execution, parameterized injection-safe. | 1 |
| **KB-2c** | Implement `bgs_kb_status` tool | Returns spec §9.2 envelope shape. Source: `pack-discovery` output. | Test: empty roots → empty packs array; real core pack present → 1 entry with correct fields. | 1 |
| **KB-2d** | Implement `bgs_kb_query` tool | Tokenize free-text query → build SQL with FTS5 MATCH + join filters on `record_games`, `record_domains`, `record_excludes`. ORDER BY BM25 rank. Return ranked hits with snippets (FTS5 `snippet()`), variant notes, sources. | Test: query with `games: ["Fallout4"]` returns only FO4-applicable records; query with `domains: ["xedit"]` filters correctly; FTS5 rank surfaces expected top-3. Latency p95 <50ms on 50 records. | 2 |
| **KB-2e** | Implement `bgs_kb_get` tool with variant merge | Fetch record by id (+ optional packId disambiguator). If `game` arg set, merge variant overlay server-side per spec §5.3. Handle `appliesTo.excludes` → return `appliesToRequestedGame: false` without merging. | Test: get without game returns raw variants; get with FO4 game merges FO4 overlay; get with FNV on a Papyrus record returns `appliesToRequestedGame: false`. | 1-2 |
| **KB-2f** | Wire the stdio MCP server entry | `src/index.ts`: SDK init, tool registration, `tools/list` + `tools/call` handlers, signal handling (mirror `xedit-mcp/src/index.ts` pattern but no daemon lifecycle). | Manual smoke: spawn the server via stdio, send `initialize` + `tools/list`, verify all 3 tools listed. | 1 |
| **KB-2g** | Register bgs-kb-mcp in all 3 harness configs | Update `.mcp.json` (add `bgs-kb` server entry), update `.opencode/plugins/bgs-modding-superpowers.js` (add `config.mcp.bgs_kb` block), update Codex / Claude Code manifests if they reference MCP separately. | Manual smoke in OpenCode: `bgs_kb_status` answers; same in Claude Code; same in Codex (or document if Codex has any specific quirk). | 1 |
| **KB-2h** | Update `scripts/build-portable-plugin.ps1` | Add `tools/bgs-kb-mcp/dist/` + `tools/bgs-kb-mcp/package.json` + `tools/bgs-kb-mcp/README.md` to the materialization. Add `knowledge/bgs-kb/packs/core/` (records + manifest + kb.sqlite). Strip `prepare`/`build`/`test` scripts from the materialized `bgs-kb-mcp/package.json` same as xedit-mcp. | Rebuild portable plugin; verify `dist/portable-plugin/bgs-modding-superpowers/tools/bgs-kb-mcp/` is populated; `node tools/bgs-kb-mcp/dist/index.js` over stdio answers `tools/list` with 3 tools. | 1 |
| **KB-2i** | Update `using-bgs-modding-superpowers` SKILL.md | Add `bgs_kb_status` / `bgs_kb_query` / `bgs_kb_get` to the available-MCP-tools section. Document the three-root discovery model. Add KB query as a routing option in the "When to use" decision tree. | Skill content review: agent reading the bootstrap knows the KB exists and when to query it. | 1 |
| **KB-2j** | Acceptance: full spec §15 KB-2 matrix | Run the 6 acceptance scenarios end-to-end; preserve artifacts under `.opencode/artifacts/kb/acceptance/kb-2/`. | All 6 scenarios pass with preserved evidence. | 1 |

### Acceptance for KB-2 as a whole

Spec §15 KB-2 matrix:
1. MCP startup in `<plugin>/` and `<portable-plugin>/` trees discovers core pack.
2. `bgs_kb_query({query: "loose files override", games: ["Fallout4"]})` returns the asset-precedence record with FO4 variant warning in the snippet.
3. `bgs_kb_get({id: "papyrus.oninit-vs-onload.v1", game: "FalloutNV"})` returns `appliesToRequestedGame: false`.
4. Skyrim-only record query with `games: ["Fallout3"]` filter is suppressed.
5. Stop + restart MCP: same pack set discovered, no state leakage.
6. Multi-pack: drop a fake user pack via `$BGS_KB_USER_PACKS`, verify hits tagged with the user `packId`.
7. Latency: 95th percentile <50ms at 100 records.

### Deliverables

- `tools/bgs-kb-mcp/` fully implemented + tested + dist + portable-plugin integration
- Three-harness MCP registration
- Updated `using-bgs-modding-superpowers` skill
- Acceptance artifacts under `.opencode/artifacts/kb/acceptance/kb-2/`

### Risks

- Multi-pack query merge could double-rank; resolve with per-pack FTS5 query + union with rank normalization, not a federated FTS5 across attached DBs.
- Variant merge could grow complex on records with deletions; if KB-1 seed records exercise this poorly, KB-2 may surface schema issues retroactively.
- MCP registration drift across 3 harnesses; codify the registration into the test matrix.

### Estimated commits

~10-12 commits. ~4-6 working sessions.

---

## KB-3 — `maintaining-modding-environments` skill + `setting-up` split

**Goal:** Create the new `maintaining-modding-environments` skill so end-user pack authoring + KB cache hygiene + version pinning have a permanent home. Audit `setting-up-bgs-modding-environment` and move any ongoing-care content into the new skill.

**Dependencies:** KB-2 complete (the MCP must exist for the maintenance skill to reference its tools).

**Branch:** `feat/kb-3-maintaining-modding-environments`

### Tasks

| # | Task | Bounded scope | Acceptance | Est. commits |
|---|---|---|---|---|
| **KB-3a** | Audit `setting-up-bgs-modding-environment/SKILL.md` | Read the full SKILL body. Identify any sub-workflows that are "ongoing care" (not first-run): KB updates, cache hygiene, environment health checks, custom pack registration, version-pinning, etc. Tag each section as `keep` (first-run) or `move` (ongoing). | A migration list with section refs + rationale, committed as `docs/internal/plans/2026-06-02-setting-up-maintaining-split.md`. | 1 |
| **KB-3b** | Author `skills/maintaining-modding-environments/SKILL.md` | Skill frontmatter + description body. Sub-workflows: (a) check + apply KB updates via `bgs_kb_check_updates` + `bgs_kb_install_pack`, (b) prune cache, (c) register custom pack via `$BGS_KB_USER_PACKS`, (d) run pack-build CLI for end-users, (e) version-pinning advice, (f) absorb the migrated content from KB-3a. | Skill validates against skill-frontmatter linter; manual review confirms coverage of all KB-3a migrated items. | 2 |
| **KB-3c** | Update `setting-up-bgs-modding-environment` | Remove sections tagged `move` at KB-3a. Add a closing pointer: "For ongoing care, see `maintaining-modding-environments`." Add the first-run KB acquisition workflow: ask target games → fetch chosen packs from GitHub Releases → verify sha256 → install to cache → smoke `bgs_kb_query`. | Skill remains coherent as a first-run orchestrator; no orphan references; semantic check: a fresh-machine agent following setting-up reaches a state where `bgs_kb_query` returns hits for the chosen games. | 2 |
| **KB-3d** | Register `maintaining-modding-environments` in `using-bgs-modding-superpowers` | Add to the available-skills table with auto-trigger conditions (e.g. "log KB update", "register custom pack", "prune KB cache", "modpack maintenance"). | Bootstrap-skill review: trigger conditions are unambiguous; no overlap with setting-up triggers. | 1 |
| **KB-3e** | Acceptance: fresh-machine setup + maintenance walkthrough | Two test sessions: (1) fresh agent runs setting-up on a clean state, picks 1-2 games, ends with successful KB queries. (2) Agent invokes maintaining-modding-environments, registers a custom pack, runs the build CLI, queries for the new records. | Transcripts preserved under `.opencode/artifacts/kb/acceptance/kb-3/`. | 1 |

### Deliverables

- `skills/maintaining-modding-environments/SKILL.md` (new)
- Updated `skills/setting-up-bgs-modding-environment/SKILL.md` (slimmed)
- Updated `skills/using-bgs-modding-superpowers/SKILL.md` (registers the new skill)
- Migration log at `docs/internal/plans/2026-06-02-setting-up-maintaining-split.md`
- Acceptance artifacts at `.opencode/artifacts/kb/acceptance/kb-3/`

### Risks

- Skill description / trigger drift between setting-up and maintaining; the registration step in `using-bgs-modding-superpowers` is the seam to keep them clean.
- Existing references to setting-up sub-workflows from other docs/skills could break; grep the repo for the section names being moved and update inbound links.

### Estimated commits

~6-8 commits. ~2-3 working sessions.

---

## KB-4 — Per-game packs via two-stage fan-out

**Goal:** Author the full set of cross-game and per-game records via parallel subagent fan-out, producing 5 published packs (core + 4 per-game; FO3+FNV share a pack via the B3 paired agent). Publish as GitHub Release artifacts.

**Dependencies:** KB-3 complete (the maintenance skill must exist so installed packs have a home). KB-1 schema + KB-2 MCP must be stable — the fan-out is doing 200+ records of work; schema/query churn during fan-out would be expensive.

**Branch:** `feat/kb-4-fanout-stage-a`, then `feat/kb-4-fanout-stage-b` (Stage A merges to main before Stage B starts, since Stage B reads Stage A as context).

### Stage A — Cross-game core pack expansion

4 parallel subagents (`@librarian` variants). Each agent runs in its own sub-session, given:
- Spec §5 (record schema)
- Spec §14 (anti-copy guardrail)
- The current `knowledge/bgs-kb/packs/core/` records as read-only context (no duplication)
- The full source list from `docs/internal/roadmap.md` § Appendix
- A specific domain assignment

| Sub-agent | Domain | Target record count | Sources to prioritize |
|---|---|---|---|
| **A1** | xedit + plugin-format | ~30 records | xEdit docs, xEdit GitHub issues, xEdit Discord pinned, Mutagen docs, UESP CK Wiki, Tome of xEdit |
| **A2** | load-order + archive-precedence | ~15 records | LOOT docs, MO2 wiki, AFK Mods forum, `writing-bgs-load-order` skill, STEP wiki |
| **A3** | papyrus shared core | ~25 records | CK UESP mirror (Playwright), GECK Wiki (Papyrus crossover), AFK Mods forum, Bethesda CK docs archive |
| **A4** | engine quirks + Spriggit tooling | ~15 records | Spriggit + Mutagen docs, GitHub issues, STEP wiki, ENBSeries forum, modder blog write-ups |

Each agent produces:
- A set of new `.md` records under `knowledge/bgs-kb/packs/core/records/<domain>/`
- Each record has structured `sources` with at least one verified URL
- A summary doc at `.opencode/artifacts/kb/fan-out/stage-a/<agentId>-summary.md` listing: records authored, sources cited, any blocking ambiguity flagged
- The agent runs the build CLI's `validate` step on its output before returning

### Stage B — Per-game packs

After Stage A merges, 4 parallel subagents author per-game packs. Each agent receives the merged Stage A output as read-only context.

| Sub-agent | Pack | Game scope | Focus topics |
|---|---|---|---|
| **B1** | `bgs-kb-skyrim` | SkyrimLE / SkyrimSE / SkyrimAE / SkyrimVR | Scripts subsystem, Nemesis/FNIS animation, behavior outputs, SkyUI, SkyrimVR controller API (with citations to SKSEVR/VRIK), AE breakage matrix, version pinning |
| **B2** | `bgs-kb-fallout4` | Fallout4 / Fallout4VR | Precombine/previs integrity, BA2 quirks, settlement worldspace, Buffout-class diagnostics, next-gen update breakage, ENB+F4SE interactions, FO4 VR controller/IK (parallel SKSEVR/F4SEVR APIs; the WingedGuardian source covers SkyrimVR only) |
| **B3** | `bgs-kb-fallout3-fnv` | Fallout3 / FalloutNV | Legacy plugins.txt format, NVSE/FOSE, GECK reality, TTW interop, common Gamebryo engine bugs |
| **B4** | `bgs-kb-starfield` | Starfield | Post-CK toolchain caution, asset/material model differences from FO4, plugin format evolution, "what NOT to assume from FO4/Skyrim" record set |

Each agent produces:
- Pack tree under `knowledge/bgs-kb/packs/<packId>/records/`
- `cli build` succeeds on the pack
- Summary doc at `.opencode/artifacts/kb/fan-out/stage-b/<packId>-summary.md`

### Tasks (controller side, after subagents return)

| # | Task | Acceptance |
|---|---|---|
| **KB-4a** | Author Stage A subagent prompts | 4 prompts ready, each with spec §14 anti-copy guardrail inlined, source list reference, domain assignment, expected output spec. Dry-run reviewed before dispatch. |
| **KB-4b** | Dispatch Stage A in parallel | All 4 return with artifacts. Each artifact set validates against the schema via `cli validate`. |
| **KB-4c** | Controller review of Stage A | Sample 5 records per agent (20 total). Verify: (1) `sources` URLs resolve, (2) no >40-char verbatim copy from WingedGuardian (use `git diff` or a textual diff tool against the WingedGuardian repo), (3) cross-game scope is honored (no Skyrim-only records mis-tagged as multi-game). Reject + iterate if any of the three checks fail. |
| **KB-4d** | Build + smoke-test the expanded core pack | `cli build knowledge/bgs-kb/packs/core` succeeds; `cli info` reports ~85 records (50 seed + ~35 Stage A net new); FTS5 queries surface the new content. |
| **KB-4e** | Author Stage B subagent prompts | 4 prompts, each with full spec §14 guardrails, Stage A output as read-only context, pack assignment. |
| **KB-4f** | Dispatch Stage B in parallel | All 4 return. Each pack `cli build` succeeds; each `cli info` reports expected record count (range: 300-600 per pack). |
| **KB-4g** | Controller review of Stage B | Same 5-records-per-pack sampling as KB-4c, plus a cross-pack consistency check: records in B1 about Papyrus must not contradict Stage A's core Papyrus records (variants should overlay, not contradict). |
| **KB-4h** | Publish GitHub Release artifacts | Build all 5 packs → zip each → compute sha256 → publish a Release with tag `kb-2026.06.02` (or current date) → upload all 5 zips + a `manifest-index.json`. |
| **KB-4i** | Test `bgs_kb_check_updates` + `bgs_kb_install_pack` against the staged release | (Implements those two tools as part of KB-6 normally; if KB-6 is not yet done, scope a minimal implementation here as a forward-port.) On a fresh machine with no cache: install all 4 game packs via the tools, verify discovery + queries. |
| **KB-4j** | Update README.md + release notes with the KB pack catalog | Public-facing: list which packs are available, where they come from, what they cover, how end-users opt in. |

### Acceptance for KB-4

Spec §15 KB-4 matrix:
- 8 subagent runs preserved as artifacts (4 Stage A + 4 Stage B).
- Each pack validates and builds.
- Random sampling of 5 records per pack: every `sources` URL resolves; manual reviewer confirms the source supports the claim.
- Anti-copy check: textual diff against WingedGuardian KNOWLEDGEBASE.md returns no ≥40-character verbatim matches in any Skyrim record.
- Total record count across all 5 packs ≥ 2000.

### Deliverables

- 5 published GitHub Release artifacts (`bgs-kb-{core,skyrim,fallout4,fallout3-fnv,starfield}-<version>.zip`) + `manifest-index.json`
- Source tree under `knowledge/bgs-kb/packs/{core,bgs-kb-skyrim,bgs-kb-fallout4,bgs-kb-fallout3-fnv,bgs-kb-starfield}/records/`
- Per-agent acceptance artifacts under `.opencode/artifacts/kb/fan-out/{stage-a,stage-b}/`
- Updated `README.md` + `RELEASE-NOTES.md`

### Risks

- Subagent quality variance — mitigated by the 5-records-per-pack manual review gate; reject + iterate.
- Cross-pack contradictions — KB-4g's consistency check catches these; if a contradiction is structural (e.g. an A3 core Papyrus record conflicts with a B1 Skyrim variant), the core record wins and the variant must be reworked.
- Cloudflare gates blocking subagents mid-run — spec §14 + Appendix already specify Playwright switchover; reiterate in every subagent prompt.
- Record-count target (≥2000) may push subagents to pad with low-confidence material; the `confidence` field + sampling-review gate is the discipline.
- Release artifact size — if any single pack exceeds 50 MB, split or compress further.

### Estimated commits

~15-20 commits across the two stages. ~6-10 working sessions including the manual review passes.

---

## KB-5 — Lesson-log migration: KB records replace `xedit-knowledgebase.md` appends

**Goal:** Change the `xedit-automation` SKILL.md lesson-log instruction from "append to `xedit-knowledgebase.md`" to "author a new KB record under `knowledge/bgs-kb/packs/core/records/`". Either retire `xedit-knowledgebase.md` or regenerate it deterministically from the KB.

**Dependencies:** KB-2 complete (the MCP must be live so agents can `bgs_kb_query` for the new records). KB-4 complete is preferred but not strictly required — KB-5 can land with just the core pack.

**Branch:** `feat/kb-5-lesson-log-migration`

### Tasks

| # | Task | Bounded scope | Acceptance |
|---|---|---|---|
| **KB-5a** | Update `xedit-automation/SKILL.md` lesson-log section | Replace the "append to `xedit-knowledgebase.md`" instruction with "author a KB record + run `cli build`". Add a worked example. | Skill body coherent; agent reading it knows the new workflow. |
| **KB-5b** | Decide on `xedit-knowledgebase.md`'s fate | Two options: (1) retire it entirely with a redirect note; (2) regenerate it from KB records via a `cli render` subcommand. Decide based on whether end-users currently rely on reading the file directly. | Decision committed in the KB-5 closeout commit message. |
| **KB-5c** | SKIPPED (KB-5b chose Option 1 — retire with redirect) | Do not implement `cli render`; the retired `xedit-knowledgebase.md` path remains as a redirect note, while KB records are the source of truth. | No render subcommand added; redirect decision is documented in KB-5b and closeout. |
| **KB-5d** | Add a forward-looking marker to mechanically-checkable footguns | When the lesson is "agent should not do X with arg Y", flag it for promotion to an `xedit-mcp` rule (LOAD-style). Don't promote in this phase, but tag the records with `kind: "rule-candidate"`. | At least 3 rule-candidate records exist after migration; tracked in a follow-up doc. |
| **KB-5e** | Acceptance: end-to-end lesson-log loop | Agent encounters a new gotcha during an xEdit task, authors a KB record, runs the build CLI, queries for the new record via `bgs_kb_query`, gets the record back with correct snippet. | Transcript preserved at `.opencode/artifacts/kb/acceptance/kb-5/`. |

### Deliverables

- Updated `xedit-automation/SKILL.md`
- Either retired `xedit-knowledgebase.md` (+ redirect note) OR a `cli render` subcommand + regenerated file
- Acceptance transcript

### Risks

- Existing references to specific sections of `xedit-knowledgebase.md` from other docs may break. Grep repo for `xedit-knowledgebase.md#` references and update.

### Estimated commits

~4-6 commits. ~1-2 working sessions.

---

## KB-6 — Update checks + eval harness

**Goal:** Ship `bgs_kb_check_updates` + `bgs_kb_install_pack` MCP tools (network paths), plus a retrieval-quality eval harness with a small gold query set.

**Dependencies:** KB-4 complete (need real published Release artifacts to test against). KB-5 complete is helpful but not strictly required.

**Branch:** `feat/kb-6-updates-and-eval`

### Tasks

| # | Task | Bounded scope | Acceptance |
|---|---|---|---|
| **KB-6a** | Implement `bgs_kb_check_updates` | Fetch `manifest-index.json` from the most recent GitHub Release; compare each installed pack's version vs latest; surface upgrades + breaking-change flag (`minPluginVersion` violation). | Tested against the real published Release: surfaces upgrades correctly when local cache is one version behind. |
| **KB-6b** | Implement `bgs_kb_install_pack` | Download Release asset → verify sha256 → extract to `<cache-root>/incoming/` → validate manifest → atomic-move into `<cache-root>/packs/<packId>/<version>/`. Support `dryRun`. Refuse on sha256 mismatch with `pack_integrity_failed`. | Tested: dry-run shows correct plan; real install lands the pack and the MCP picks it up on next `bgs_kb_status` (or with a refresh hint). |
| **KB-6c** | Eval harness: 20-query gold set | `tools/bgs-kb-mcp/tests/eval/gold-set.json` with 20 queries + expected top-3 record ids. Vitest runner reports retrieval@3 and any regression. | Eval passes on the current corpus; can be added to CI. |
| **KB-6d** | Cache hygiene subroutine | `maintaining-modding-environments` skill grows a "prune cache" workflow that calls a `cli prune-cache` subcommand (or the MCP exposes `bgs_kb_prune_cache`). Pruning keeps current + previous version, deletes older. | Test: install 3 versions of a fake pack; prune; verify only 2 remain (current + previous). |
| **KB-6e** | Acceptance: full update-and-install loop | Walk through a real release update: machine starts on KB-2026.06.02; check_updates surfaces KB-2026.07.01; install_pack lands the new version; queries reflect new content; old version still cached for rollback. | Transcript preserved. |

### Deliverables

- Two new MCP tools (`check_updates`, `install_pack`)
- Eval gold-set + runner
- `maintaining-modding-environments` skill updated with prune subroutine
- Acceptance transcript

### Risks

- GitHub Release URLs change format if we move repos; cache the Release URL pattern in a constant.
- Network failures during install need clean recovery; the `incoming/` staging dir + atomic-move design handles partial downloads.
- Eval gold-set may be too small (20 queries); plan a follow-up to grow it as the KB grows.

### Estimated commits

~6-8 commits. ~2-3 working sessions.

---

## Phase ordering + parallelism

```
KB-1 → KB-2 → KB-3 → KB-4 (Stage A → Stage B) → KB-5 → KB-6
                          │
                          └─ Stage A and Stage B internally fan out 4-wide
```

Only Stage A and Stage B run in parallel internally. The phases themselves are sequential because each depends on the prior phase's foundations.

KB-3 could in principle run in parallel with KB-2 (the maintenance skill design doesn't strictly need the live MCP), but the acceptance scenarios for KB-3 require the MCP to be live, so sequentialize for cleaner verification.

## Cross-cutting invariants (apply to every phase)

1. **Anti-copy guardrail** (spec §14) applies to every record-authoring task.
2. **`sources` field is mandatory** on every record; no exceptions.
3. **`bgs-kb-mcp` is independent of xEdit daemon readiness** — no phase introduces a dependency.
4. **Portable plugin build (Target 1) must keep working** — every phase that touches MCP packaging re-verifies the portable build smoke test.
5. **Acceptance is semantic, not surface** (per `10-semantic-proof-and-acceptance-design.md`) — every phase preserves real-run artifacts.
6. **Roadmap updated after every phase** — KB-1 closeout updates the roadmap with "now known" + "implications for later phases" entries.
7. **Small commits preferred** — every task in this plan is bounded enough to commit individually.

## Status as of 2026-06-02

- Architecture-only commits on `main`: `d3b5abc`, `7ec31d6`, `541901a` (not yet pushed).
- Implementation: **not started**.
- Next concrete step: push the architecture commits, then start KB-1a.

## References

- Spec: `docs/internal/superpowers/specs/2026-06-02-agentic-cross-game-kb-design.md`
- Roadmap: `docs/internal/roadmap.md` § 2026-06-02 + § Appendix
- Source list: `docs/internal/roadmap.md` § Appendix
- Sibling MCP precedent: `tools/xedit-mcp/`
- Reference repo (structural inspiration only, no content copy): `WingedGuardian/skyrimvr-claude-toolkit`
