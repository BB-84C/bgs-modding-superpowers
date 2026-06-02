# Plugin Roadmap

This roadmap is the compact control panel for the plugin. It carries scope, workflow coverage, and current sequencing without duplicating the larger design set.

## Mission

This plugin exists for professional BGS modpack curation across Skyrim, Fallout 4, and Starfield. It is workflow-first, multi-session, and focused on curator decision support for repeatable modpack work, not general mod authoring.

## Systematic Modpack Workflow

1. Environment setup: define game targets, profiles, repository state, and working conventions.
2. Runtime/toolchain setup: confirm loaders, utilities, xEdit, and other curator prerequisites before evaluating content.
3. Provenance and naming discipline: keep downloads, extracted assets, plugin names, and working notes attributable and consistently named.
4. Mod discovery and evaluation: screen candidate mods for fit, quality, risk, compatibility signals, and pack value.
5. Install planning: batch proposed additions, order work, and note rollback boundaries before touching the pack.
6. Controlled incremental installation: add small install batches deliberately so regressions can be attributed quickly.
7. MO2 execution: perform organizer changes in a deliberate sequence with profile awareness.
8. File/archive conflict reasoning: explain loose-file, archive, overwrite, and asset precedence outcomes.
9. Separate file deployment order from plugin order: treat asset winner selection and plugin load order as related but different decisions.
10. xEdit-driven plugin/data conflict analysis: inspect records read-only and surface actionable conflict findings.
11. Decide load-order resolution vs patch resolution: distinguish what can be solved by ordering from what requires an explicit compatibility patch.
12. Localization: track translation impact, string coverage, and language consistency for shipped content.
13. Testing: run in-game validation loops against the current install batch and capture unresolved issues.
14. Diagnostics-first troubleshooting: start with reproducible symptoms, logs, and crash signals before prescribing fixes.
15. Modpack-facing documentation: maintain dev-log, public changelog, and other modpack-facing documentation as part of the workflow itself.
16. Document-and-freeze / release-baseline discipline: record the validated state and freeze a release baseline before broader change resumes.

## Capability Map

| Capability | Current status | Notes |
| --- | --- | --- |
| repository/standards | Shipped | `README.md`, `CONTRIBUTING.md`, `LICENSE`, `RELEASE-NOTES.md`, and `docs/internal/standards/repo-hygiene.md` now define the public and internal surfaces cleanly. |
| multi-harness packaging | Shipped (v0.1 dev shape) | Root `package.json`, `.claude-plugin/`, `.codex-plugin/`, `.mcp.json`, `.opencode/plugins/bgs-modding-superpowers.js`, `.version-bump.json`, and `hooks/` all land and install locally. |
| repo-bootstrap guidance | Shipped | The old `agents/repo-bootstrap/` persona is retired; its responsibilities live in `docs/internal/repo-bootstrap.md`. |
| mod evaluator | Scaffolded only | Moved to `docs/internal/future-skills/mod-evaluator/` as a design note. |
| install planner | Scaffolded only | Moved to `docs/internal/future-skills/install-planner/`; no real workflow yet. |
| conflict auditor | Shipped | The real workflow is now `skills/xedit-conflict-audit/` backed by the bundled xEdit MCP. |
| archive/loose-file reasoning helpers | Planned | Needed to explain archive precedence, loose-file wins, and overwrite outcomes during install review. |
| diagnostics / crash-triage support | Planned | Should organize logs, crash indicators, and reproducible symptom framing before deeper workflow advice. |
| benchmark or smoke-test harness | Planned | Direction only for now; later phases should add fast validation passes for install batches and release baselines. |
| localization assistant | Scaffolded only | Moved to `docs/internal/future-skills/localization-assistant/`. |
| test session guide | Scaffolded only | Moved to `docs/internal/future-skills/test-session-guide/`. |
| modpack dev log workflow | Shipped | `skills/writing-modpack-devlog/` creates and maintains the file at runtime; templates deleted. |
| release changelog workflow | Shipped | `skills/writing-modpack-changelog/` creates and maintains the file at runtime; templates deleted. |
| BGS load-order guidance | Shipped | `skills/writing-bgs-load-order/` documents `plugins.txt` / `loadorder.txt`, official-master detection, ESL routing, and xEdit `-P:` / `-D:` integration. |
| visible MO2 startup | Shipped | `scripts/start-mo2.ps1` launches MO2 with a visible GUI, detects zombie processes, and exposes the profile-driven startup path to agents. |
| native xEdit outer client | Shipped | `tools/mo2-vfs-launcher/xedit-client.ps1` launches native xEdit automation under MO2 and preserves session/plugin-file/launch artifacts. |
| xEdit MCP runtime | Shipped (v0.1 dev shape) | `tools/xedit-mcp/` now ships `dist/`, non-blocking lifecycle tools, explicit `dataPath` / `pluginsFile` launch overrides, and dirty-state-safe stop/restart. |
| MCP integrations beyond xEdit | Specified only | Specs live at `docs/internal/mcp-specs/` (`nexus-metadata`, `loot-metadata`, `translation-memory`). |
| safety hooks | Foundation in place | Runtime hook code lives in `hooks/`; hook specs moved to `docs/internal/hook-specs/`. |
| save-safety automation | Explicitly deferred | The design calls for it later, but no real save-safety automation should ship until a real curator loop exists. |
| agentic cross-game BGS knowledge base | Planned (architecture chosen 2026-06-02) | Sibling `tools/bgs-kb-mcp/` + hybrid records under `knowledge/bgs-kb/` + SQLite3+FTS5+BM25 prebuilt index. Pack format = `<packId>/{manifest.json, records/, kb.sqlite}` zipped per release. Bundled core + per-game Release artifacts + end-user packs via `$BGS_KB_USER_PACKS` discovery. See 2026-06-02 entry for full architecture + KB-4 fan-out plan. Scale: ~2500-3000 items across Skyrim / FO3 / FNV / FO4 / Starfield, de-duplicated via per-game variant overlays. |

## Phase Ladder

1. Phase 0 bootstrap foundation: repository layout, standards, scaffold docs, hook specs, skill shells, templates, contracts, and bootstrap verification.
2. Phase 1 read-only xEdit conflict inspection vertical slice: deliver the first real workflow through `conflict-auditor` backed by the native xEdit outer client boundary in `tools/mo2-vfs-launcher/xedit-client.md`.
3. Phase 2 file/archive reasoning and install planning: connect install planning to archive precedence, overwrite reasoning, and controlled incremental installation.
4. Phase 3 mod evaluation and intake: make the front-end selection workflow usable before deeper automation expands.
5. Phase 4 modpack dev-log workflow: turn internal decision capture into a real maintained workflow rather than a template-only asset.
6. Phase 5 test-session guidance: add repeatable test-session structure and smoke-test direction tied to install batches.
7. Phase 6 localization workflow: layer translation support onto already-stable install, conflict, and test flows.
8. Phase 7 public release changelog workflow: derive player-facing release communication from the stabilized internal dev-log workflow.
9. Phase 8 controlled higher-risk automation: add carefully gated automation only after the read-only and operator-guided loops are proven.
10. Phase 9 packaging and publishable plugin surface: finalize packaging metadata, command surfaces, and publishable OpenCode plugin structure.

### Cross-cutting track: Agentic Knowledge Base (KB-1 through KB-6)

Runs in parallel with the phase ladder above, not as a single inserted phase, because it touches multiple workflows (conflict audit, install planning, diagnostics, setup). Phases live in the 2026-06-02 architecture entry below.

- KB-1 — schema + seed records extracted from existing `xedit-knowledgebase.md` and `writing-bgs-load-order/SKILL.md`.
- KB-2 — `tools/bgs-kb-mcp/` with `bgs_kb_status` / `bgs_kb_query` / `bgs_kb_get`; loads bundled core pack only.
- KB-3 — `setting-up-bgs-modding-environment` skill gains pack-acquisition + cache-hygiene steps.
- KB-4 — per-game packs (FO4, SkyrimSE, FO3, FNV, Starfield) published as GitHub Release artifacts.
- KB-5 — dual-write lessons; legacy `xedit-knowledgebase.md` becomes generated-from-records or retired.
- KB-6 — optional `bgs_kb_check_updates` + opt-in refresh; eval harness for retrieval quality.

## Dependency / Blocker Map

- Codex still expects a `plugins/<name>/` marketplace subdirectory layout. The current local-only workaround uses a gitignored `plugins/` tree plus absolute paths. A real publishable Codex packaging story is still outstanding.
- The first real xEdit workflow no longer depends on the old `skills/conflict-auditor/` scaffold. The active bridge is `skills/xedit-conflict-audit/` + `tools/xedit-mcp/` + `tools/mo2-vfs-launcher/xedit-client.md`.
- Release changelog workflow depends on a real dev-log workflow first, or it will have no trustworthy internal source of truth.
- Localization should follow stable install/conflict/test flows so translation work is applied to a reasonably settled baseline.
- Metadata integrations should come after conflict truth, not before; source metadata is useful, but it cannot replace actual conflict inspection.
- Broader MCP integrations depend on stable contracts for metadata lookup, translation-memory access, and consistent agent invocation patterns.
- Save-safety should follow a real curator loop rather than precede it, so warnings reflect actual workflow behavior instead of guesses.
- Higher-risk safety and packaging automation should stay behind the read-only workflow until operational behavior is verified in practice.
- The current xEdit MCP still assumes MO2 is already running. A future release may choose to auto-start MO2, but only if the visible-GUI invariant is preserved and stale-process cleanup remains explicit.
- Any write-capable packaging or patching step remains gated by safety rules, explicit targets, and confidence earned from the earlier workflow phases.
- The agentic KB track (KB-1..KB-6) must keep `bgs-kb-mcp` independent of xEdit daemon readiness — KB queries must work before MO2 / xEdit are configured (the setup skill needs guidance while environment state is incomplete). KB tools never auto-start xEdit. KB records are advisory; xEdit MCP semantic readback remains authoritative for actual plugin / load-order state.
- KB pack distribution must keep the portable-plugin tree small (Target 1 invariant). Only the `core` pack ships inline; per-game packs are GitHub Release artifacts pulled on user consent via the setup skill.

## Not Yet Real

- There is no published / portable Codex package yet (current Codex install path is local-workaround only).
- There is no fully portable end-user xEdit runtime config story yet; current acceptance uses explicit `dataPath` / `pluginsFile` overrides and a dev MO2 sandbox.
- There is no write-capable patch generation workflow yet.
- There is no automated LOOT integration yet.
- There is no save-safety automation yet.

## Game-Specific Pressure Points

- Skyrim: scripts, animation generation, and behavior-output conflicts need special care beyond ordinary plugin ordering.
- Fallout 4: precombine/previs integrity, Buffout-oriented diagnostics, BA2 pressure, and settlement-worldspace edits create recurring curator risk.
- Starfield: evolving toolchain caution matters, including not inheriting FO4/Skyrim assumptions blindly when defining workflow policy.

## Completed Foundations

- Scope and repo guardrails are established in `README.md`, `CONTRIBUTING.md`, `LICENSE`, and `docs/internal/standards/repo-hygiene.md`.
- Repository bootstrap responsibilities are captured in `docs/internal/repo-bootstrap.md`.
- Core workflow skills now exist as runnable top-level skills under `skills/`, including `using-bgs-modding-superpowers`, `setting-up-bgs-modding-environment`, `xedit-automation`, `xedit-conflict-audit`, `writing-modpack-devlog`, `writing-modpack-changelog`, and `writing-bgs-load-order`.
- Safety baseline hooks ship as real runtime files in `hooks/`, with the old specs preserved under `docs/internal/hook-specs/`.
- Runtime-generated dev-log / changelog files are created by skills, not by templates (templates deleted).
- Read-only tool and integration contracts already exist in `tools/mo2-vfs-launcher/xedit-client.md` and `docs/internal/mcp-specs/xedit-readonly.md`.
- Bootstrap verification is already wired through `tests/bootstrap/verify-foundation.ps1` and `tests/bootstrap/verify-all.ps1`.

## Current Focus

The reshape to a Superpowers-shaped multi-harness plugin is complete in the local repo (`main`). Immediate next targets:

1. **Agentic cross-game knowledge base (KB track)** — architecture chosen 2026-06-02; see entry below. Next concrete step is KB-1: schema + seed records under `knowledge/bgs-kb/` extracted from the existing `xedit-knowledgebase.md` and `writing-bgs-load-order` skill. Long-term shape: sibling `tools/bgs-kb-mcp/` server + hybrid records with per-game variant overlays + bundled core / per-game Release-artifact distribution. This is the next major workstream.
2. **Portable publishability** — `scripts/build-portable-plugin.ps1` now stages a self-contained `dist/portable-plugin/bgs-modding-superpowers/` tree (no junctions, no machine-specific paths). Remaining work: stage that tree onto a release branch (or release artifact) so end-users on Codex can consume it without running the build script. The KB track must respect this invariant — only the core pack ships inline.
3. **Read-only xEdit completion** — Batch 2 carry-forwards #2 / #4 / #5 / #6 are closed (see STATUS file). Remaining: representative W2 matrix needs a `breaking` fixture (CF #1), manual GUI parity evidence under `.opencode/artifacts/xedit-mcp/acceptance/<batch>/manual-parity/` (CF #3), daemon-adapter latency measurement before any snapshot/preview-heavy mutating flow (CF #7).

Target 3 ("Operator UX — smoothing first-run setup") was closed on 2026-06-01: the invariants it referenced (visible MO2 via `scripts/start-mo2.ps1`, non-blocking MCP lifecycle tools `xedit_status/start/health/dirty/stop/restart`) are already shipped, and "smoothing first-run setup" had no concrete acceptance criteria distinct from the existing `setting-up-bgs-modding-environment` skill.

## 2026-06-02 — KB-1 closeout (schema + seed records + pack-build CLI MVP)

**Delivered (on branch `feat/kb-1-schema-and-seed-records`, 17 commits, not yet merged)**

- `knowledge/bgs-kb/schema/record.schema.json` — JSON Schema Draft 2020-12 per spec §5; 5 positive + 1 negative fixture validate the contract.
- `knowledge/bgs-kb/packs/core/` — canonical core pack with `bgs-kb-meta.yml`, 46 source records across 11 domains and all 9 games, plus the built `manifest.json` (kb.sqlite is gitignored, regenerated by `cli build`).
- `tools/bgs-kb-mcp/` — TypeScript package with `cli build` / `cli validate` / `cli info` working. Build emits a deterministic SQLite database with FTS5 + BM25 ranking; validate gives `<sourcePath>:<jsonPointer>: <message>` errors with exit 1; info reconciles manifest vs kb.sqlite and surfaces drift as warnings without auto-fixing. MCP server itself is still a stub — that's KB-2.
- 22 unit tests + 1 integration smoke. Integration test builds a copy of the core pack into a temp dir, runs 5 representative FTS5 MATCH queries, asserts expected record IDs in top-3.

**Now known (from real KB-1 implementation)**

- **SQLite lib decision is `node:sqlite`** — Node 24.16.0 ships `node:sqlite` stable (no `--experimental-sqlite` flag), FTS5 is enabled in the bundled SQLite, BM25 ranking works. Zero native deps. Preserves the portable-plugin Target-1 invariant. No `better-sqlite3` / `sql.js` needed.
- **Vitest mishandles static `node:sqlite` imports.** The build module had to use `createRequire("node:sqlite")` instead of `import { DatabaseSync } from "node:sqlite"`. This is a known Vite/Vitest quirk with built-in Node modules; the workaround is contained to the SQLite-touching code path.
- **`ajv-cli@latest` does NOT support Draft 2020-12** even though Ajv 2020 (the library) does. Schema validation uses Ajv 2020 programmatically via a small validator module. Contributors who want CLI validation will need a wrapper script — recommend adding `bgs-kb-mcp validate-schema <file>` in a follow-up.
- **Spec §3 domain enum was too narrow.** KB-1a needed to expand the enum to include `tooling.mutagen`, `tooling.loot`, `file-conflicts`, `install-planning`. Spec §3 should be updated to match the schema's actual enum at the next docs pass.
- **`debugging` domain became too broad.** 32 of 46 records tag the debugging domain (~70%); using `domains: ["debugging"]` as a filter returns most of the pack. The KB-4 review needs to tighten or split this domain; consider `debugging.symptoms` vs `debugging.harness` or a separate `diagnostics` domain.
- **Default-derived packId is `basename(packRoot)`**, which produced `core` instead of the spec-§6.1 canonical `bgs-kb-core` until `bgs-kb-meta.yml` was added. The meta file is technically optional in the design but practically required for any pack that wants a canonical packId. Document this prominently in the KB-3 `maintaining-modding-environments` skill so end-user packs don't ship as `my-pack` by accident.
- **Deterministic build verified.** Same input records → same `kb.sqlite` sha256. Sorted-keys output in `manifest.json`. Build can be run in CI without drift surprises.

**Implications for later phases**

- **KB-2** can wire the MCP server over the existing build pipeline without re-thinking the SQLite shape. `pack-discovery` reads `manifest.json` + opens `kb.sqlite` read-only; FTS5 queries with BM25 ranking already work from raw SQL. The retrieval-tool layer is straightforward orchestration over the existing primitives.
- **KB-3 (`maintaining-modding-environments`)** must surface the `bgs-kb-meta.yml` requirement for end-user packs; without it, custom packs get default-derived metadata that may collide or look wrong in `bgs_kb_status`.
- **KB-4** Stage A subagents will be authoring against a proven schema + proven build pipeline. They can run `cli validate` locally before returning records; any validation failure is the subagent's responsibility, not the orchestrator's. The Stage A prompt template should bake in the validate step.
- **KB-5** lesson-log migration to KB records is fully feasible — the authoring flow (Markdown + YAML frontmatter + run validate) is the same pattern the orchestrator-curated KB-1i records already use.
- **Domain enum needs a versioning policy** before KB-4 fan-out. Adding domains is a schema change. KB-2 should expose `bgs_kb_status.schemaVersionSupported` so end-user packs at a different schema version are visibly incompatible.

**Carry-forwards**

- The `tooling-mo2` directory under `packs/core/records/` is a category, not a domain enum — directory naming is decoupled from schema domains. This is fine but document explicitly in the KB-3 skill so end-user pack authors don't conflate the two.
- `debugging` domain breadth (see "Now known" above) — flag for KB-4 review.
- `ajv-cli` Draft 2020-12 gap — flag for contributor-facing CLI tooling.

## 2026-06-02 — Agentic cross-game KB architecture (decision, not yet built)

**Context**

Today's xEdit knowledge surface is a single deep-reference markdown file (`skills/xedit-automation/xedit-knowledgebase.md`) and short skill bodies. The reference repo `WingedGuardian/skyrimvr-claude-toolkit` carries "600+ lines of Skyrim modding knowledge" as a single ~35 KB `KNOWLEDGEBASE.md` auto-loaded per session. That pattern does not scale to our target: ~2500-3000 items across Skyrim, Fallout 3, Fallout New Vegas, Fallout 4, Starfield, with significant shared BGS-engine substrate that should de-duplicate.

**Architecture decision (chosen after 4-way multi-perspective consultation: librarian-alpha on reference repo, librarian-beta on agentic KB tech survey, oracle + oracle-gamma on architecture)**

Storage model: **hybrid records** — structured frontmatter (id, title, domains, tasks, signatures, appliesTo.games, appliesTo.engineFamilies, appliesTo.excludes, severity, confidence, sources, lastReviewed) + prose body for nuance. Pure prose loses retrieval; pure structured loses caveat depth.

Cross-game de-duplication: **base record + per-game variant overlays**, NOT pure `games: [...]` tag duplication. A single "loose files override archives" record applies to FO4 + SkyrimSE with `variants.Fallout4` adding precombine/previs caveats and `variants.SkyrimSE` adding behavior-generation caveats. Variant merge happens server-side in `bgs_kb_get`.

Retrieval seam: **new sibling `tools/bgs-kb-mcp/`**, NOT folded into `xedit-mcp`. The substrate is different — xedit-mcp is a live-daemon execution harness with readiness semantics; the KB is static curated content with its own lifecycle. Per `~/.config/opencode/memory/40-low-intrusion-architecture.md`, the boundary is honest. The roadmap already frames `nexus-metadata` / `loot-metadata` / `translation-memory` as sibling MCP tracks; the KB joins that pattern. KB queries must work before MO2 / xEdit are configured.

Tool surface: `bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`, and optional `bgs_kb_check_updates` / `bgs_kb_install_pack` for network refresh. Query returns ranked snippet hits + appliesTo + sources; agent calls `get` only after a promising hit. Atomic primitives, not bundled "answer everything" tools.

v1 storage tech: **SQLite3 + FTS5 + BM25** (user-confirmed override of the JSONL+JS-FTS recommendation). Rationale: BM25 ranking maturity, `MATCH` query expressiveness, snippet/highlight built-ins, predictable performance characteristics at 2500-3000 items. SQLite library choice is a v1 implementation detail to confirm at KB-2: prefer Node 24's built-in `node:sqlite` (the maintainer's machine runs Node v24.16.0; `node:sqlite` is stable in Node 22+ and Node 24's bundled SQLite ships FTS5 per upstream release notes — verify with a 5-min smoke test at KB-2). If FTS5 is not bundled, fall back to `better-sqlite3` with prebuilt binaries via `node-pre-gyp`. WASM `sql.js` is the floor option. Plugin `engines.node` will pin `>=22` so users on Node 22 LTS also work.

Source of truth: `knowledge/bgs-kb/` **in this repo**:
- `knowledge/bgs-kb/schema/record.schema.json` — JSON Schema for record validation (must validate every record at build time)
- `knowledge/bgs-kb/packs/core/records/{xedit,load-order,archive-precedence,papyrus,engine}/...` — shared substrate
- `knowledge/bgs-kb/packs/{fallout4,skyrimse,fallout3,falloutnv,starfield}/records/...` — per-game overlays
- `knowledge/bgs-kb/guides/...` — long-form prose where records are too granular (e.g. generated `xedit-deep-reference.md`)

**Pack format** (one shape for repo-owned packs AND end-user packs):

```
<packId>/
  manifest.json                # versioned, sha256-gated, schemaVersion + minPluginVersion
  records/                     # source-authored .md with YAML frontmatter (human-editable)
    xedit/conflict-winner-basics.md
    load-order/plugins-txt-modern.md
    ...
  kb.sqlite                    # prebuilt index built from records/
```

Distribution artifact = `<packId>-<version>.zip` of that tree. `records/` rides along with the prebuilt index so the source is always auditable and rebuildable next to its artifact.

**Distribution + cache:**
- **Plugin ships `core` pack bundled** under `knowledge/bgs-kb/packs/core/` (small, ~1-3 MB) — works offline immediately.
- **Per-game packs published as GitHub Release artifacts** (`bgs-kb-fallout4-<version>.zip` etc.) pulled by `setting-up-bgs-modding-environment` on user consent.
- **Installed cache** at `%LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/<packId>/<version>/`.
- **KB cadence is independent of plugin cadence**; KB content fixes do not force a plugin re-release.

**Modular / end-user-extensible architecture** (followup #2):

The MCP discovers packs from three roots in precedence order:

```
1. Bundled    <plugin>/knowledge/bgs-kb/packs/           # plugin-shipped (core only)
2. Cache      %LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/   # downloaded game packs
3. User       $BGS_KB_USER_PACKS (semicolon-separated paths)     # end-user packs
```

Queries **merge hits from all loaded packs**, each result tagged `pack: <packId>` for provenance. `bgs_kb_query` accepts an optional `packIds: [...]` filter. No silent precedence; collisions surface as ranked hits with explicit pack source.

**End-user authoring flow:**

1. User creates `~/my-modpack-kb/records/*.md` with YAML frontmatter (same schema as official packs).
2. User runs `node tools/bgs-kb-mcp/dist/cli.js build ~/my-modpack-kb` → produces `kb.sqlite` + minimal `manifest.json`.
3. User sets `BGS_KB_USER_PACKS=C:/Users/.../my-modpack-kb`. MCP discovers + loads on next start.
4. `setting-up-bgs-modding-environment` grows a "register a custom pack" subroutine that handles 2+3 for users who'd rather not touch env vars.

Official packs and user packs are equal citizens at query time — modularity by virtue of pack discovery with stable manifest shape.

**Sources are structured, not prose** (gate B refinement): every record's `sources` field is a JSON array of `{ kind, ref, url?, sectionPath? }` entries; the JSON Schema enforces this. Unsourced facts get `confidence: low-community` and a `needs verification` note. This mirrors WingedGuardian's source-cited bottom-up pattern, lifted into the structured layer.

Reference-repo lessons applied:
- Steal: hub-skill + on-demand-Read separation, path-glob auto-activation, slash-command workflow skills, top-N hot-cache, source-cited bottom-up entries.
- Avoid: single flat markdown at scale (35 KB × 5 games = 175 KB+ stops working before game #2), `skyrim-` skill prefix (would explode N×M with per-game tool wrappers), no per-entry game-mode tag (inline `(VR)` prose markers don't survive multi-game expansion), CLAUDE.md mixing config + knowledge routing.

**Migration phases (KB-1 .. KB-6)**

- **KB-1** — schema + seed records + pack-build CLI: author `knowledge/bgs-kb/schema/record.schema.json`; extract ~50 seed records from `skills/xedit-automation/xedit-knowledgebase.md` and `skills/writing-bgs-load-order/SKILL.md` into structured records under `knowledge/bgs-kb/packs/core/records/`; build minimal `tools/bgs-kb-mcp/cli` that takes a pack root and emits `kb.sqlite` + `manifest.json` from its `records/`. Old markdown stays put.
- **KB-2** — `tools/bgs-kb-mcp/` ships `bgs_kb_status` / `bgs_kb_query` / `bgs_kb_get` + the three-root pack discovery (bundled + cache + `$BGS_KB_USER_PACKS`). Loads bundled core pack at startup. SQLite lib decision (`node:sqlite` vs `better-sqlite3` vs `sql.js`) locked here based on FTS5 availability check. New MCP registered in `.mcp.json` + `.opencode/plugins/bgs-modding-superpowers.js`. Portable-plugin build script copies `knowledge/bgs-kb/packs/core/` + `tools/bgs-kb-mcp/dist/`.
- **KB-3** — split the modding-environment skill surface so end-user pack authoring does not become an orphan that everyone forgets:
  - `setting-up-bgs-modding-environment` (read-once at project start) keeps the first-run install responsibilities: ask target games → fetch chosen packs from GitHub Releases → verify sha256 → install to cache → smoke test (`bgs_kb_query` returns hits) → register MCP.
  - **New skill `maintaining-modding-environments`** (recurring usage during a modpack project's life) absorbs ongoing care that does not belong in a first-run orchestrator: KB update checks, cache hygiene (prune old versions), custom pack authoring + registration (`$BGS_KB_USER_PACKS`), pack-build CLI walkthroughs, version-pinning advice, and any other recurring environment-maintenance work currently bolted onto setting-up. Reviewing `skills/setting-up-bgs-modding-environment/SKILL.md` at KB-3 time will surface a list of steps that should move into the maintenance skill rather than stay in first-run; do the split intentionally.
- **KB-4** — author per-game packs via the two-stage fan-out plan documented below (Stage A: 4 cross-game core agents; Stage B: 4 per-game agents). Publish as GitHub Release assets. **Anti-copy guardrail enforced in every subagent prompt**: no hard copy from `WingedGuardian/skyrimvr-claude-toolkit`; paraphrase + cite in the structured `sources` field.
- **KB-5** — `xedit-automation` lesson-log appending changes from "edit `xedit-knowledgebase.md`" to "add KB record"; mechanically-checkable footguns become xEdit MCP rule candidates; legacy markdown becomes generated-from-records or retired.
- **KB-6** — optional `bgs_kb_check_updates` + opt-in refresh; eval harness for retrieval quality (negative-case fixtures: "FO4 precombine" query with `game=skyrimse` filter should suppress FO4-only records).

**KB-4 fan-out plan (WingedGuardian breakdown → cross-game structure)**

WingedGuardian's 10 H2 categories map onto our cross-game domains as follows:

| WingedGuardian H2 | Our domain | Game scope | Target pack |
|---|---|---|---|
| Papyrus Scripting | `papyrus` | FO4 + Skyrim family + Starfield (all 3 Papyrus-using games; FO3/FNV use GECK scripting, not Papyrus, and are excluded via the schema's `excludes` field) | **core** + per-game variants |
| Version-Specific Differences | `version-differences` | Per-game runtime variants | per-game packs |
| xEdit / xelib / ESP Editing | `xedit` + `plugin-format` | All games | **core** |
| Game Engine Quirks | `engine` | Mixed | split: family-shared → core; game-specific → game pack |
| ESP Creation via Spriggit | `tooling.spriggit` | Multi-game (Mutagen) | **core** |
| VR Controller Input Detection | `game-specific.vr` | Skyrim VR + FO4 VR (parallel SKSEVR / F4SEVR APIs; WingedGuardian source is SkyrimVR-only but the domain itself is broader) | **skyrimse** + **fallout4** (each gets its own VR subsection) |
| Weapon Manipulation at Runtime | `papyrus.advanced` | Skyrim-specific | **skyrimse** |
| Papyrus Debugging | `papyrus` + `debugging` | FO4 + Skyrim family + Starfield | **core** |
| Save File Analysis | `save-file` + `debugging` | Per-game format | per-game packs |
| Hook Candidates | meta / authoring discipline | n/a | repo convention, not a domain |

**Stage A — cross-game core pack** (4 parallel subagents). Default scope on every Stage A record is **all 5 games**; per-game divergences are expressed via `appliesTo.games` / `excludes` / `variants` on the record, not by spawning per-game duplicates. Per-game pack additions live in Stage B.

- **A1 — xedit + plugin-format** (~30 records): conflict taxonomy, override chain, ITM/ITPO/ITC, FormID model, light-master rules, ONAM, master headers, plugin-type matrix. All 5 games in scope; legacy plugins.txt nuance for FO3/FNV is a variant on the relevant records, not a separate package.
- **A2 — load-order + archive-precedence** (~15 records): modern asterisk plugins.txt, legacy FO3/FNV format, BSA/BA2 priority, loose-file precedence, MO2 profile model. All 5 games in scope; the modern-vs-legacy split is per-record `appliesTo`.
- **A3 — papyrus shared core** (~25 records): script lifecycle, threading, event lifecycle, common bugs (OnInit-vs-OnLoad, RegisterForUpdate, Utility.Wait reliability), debugging conventions. Shared across FO4 / Skyrim family / Starfield (the three Papyrus-using games). FO3 + FNV are excluded on each Papyrus record via `excludes` so the agent retrieval surface explicitly refuses to apply Papyrus advice to non-Papyrus games.
- **A4 — engine quirks + Spriggit tooling** (~15 records): fUpdateBudgetMS, abilities, vanilla bugs surviving editions, Spriggit/Mutagen multi-game support. All 5 games in scope by default; Gamebryo-vs-Creation engine differences expressed via `engineFamilies` on each record.

**Stage B — per-game packs** (4 parallel subagents, each given Stage A results as read-only context so they only add game-specific records or per-game variants on existing core records):
- **B1 — Skyrim (LE/SE/AE/VR)**: scripts subsystem, animation generation (Nemesis/FNIS), behavior outputs, SkyUI, SkyrimVR controller API, AE breakage categories, version-pinning rules.
- **B2 — Fallout 4 (incl. FO4 VR)**: precombine/previs integrity, BA2 quirks, settlement worldspace, Buffout diagnostics, next-gen update breakage, ENB+F4SE interactions, FO4 VR controller/IK quirks (parallel to but distinct from SkyrimVR; the WingedGuardian SkyrimVR source does not cover FO4 VR — Stage B2 gathers it independently).
- **B3 — Fallout 3 + New Vegas** (paired): legacy plugins.txt format, NVSE/FOSE, GECK reality, common engine bugs, TTW interop notes.
- **B4 — Starfield**: post-CK toolchain caution, asset/material model changes, plugin format evolution, what NOT to assume from FO4/Skyrim.

**Anti-copy guardrails (verbatim into every Stage A/B subagent prompt):**

```
HARD RULE: Do not hard-copy any text from WingedGuardian/skyrimvr-claude-toolkit.
Where the same fact applies, paraphrase in our own voice and cite the
WingedGuardian repo path (or upstream CK Wiki / UESP / GitHub issue) in
the record's structured `sources` field.

Every record MUST include the `sources` field with at least one entry.
Unsourced facts get `confidence: low-community` and a `needs verification` note.
```

**Source survey for fan-out** — Stage A and Stage B subagents are not free to wander the web at random. Each subagent is given a curated list of BGS modding sources (forums, mod hosts, wikis, GitHub orgs, Discords, Reddit, xSE homes, ENB / shader hubs, bug trackers, long-form blog write-ups) covering all 5 games. The list is enumerated in the **Appendix: BGS modding source list** at the end of this file (populated by the 2026-06-02 librarian survey). Per-source notes flag access conditions (login? Cloudflare? rate-limit?) and fetch strategy (simple HTTP vs Playwright vs API). Subagents that hit a Cloudflare challenge MUST switch to the Playwright harness rather than give up and fall back to prior-based summarization.

**Now known (from the consultation)**

- The reference repo's loading model is NOT what its README claims. `KNOWLEDGEBASE.md` is opt-in `Read`, not auto-stuffed; the auto-load happens via `CLAUDE.md` (top-15 hot cache, ~3K tokens) + path-triggered `skyrim-context` SKILL (~700 tokens on `*.psc/*.pex/Data/**`). Our hub `xedit-automation` SKILL already follows this pattern.
- Reference repo's `skyrim-bsa` skill already path-globs `**/*.ba2` — proves a multi-game seam exists in shape, but the rest of the repo is Skyrim-anchored.
- No public Bethesda / xEdit / Papyrus / Creation Engine KB MCP exists at our target scale. This is greenfield for the modding domain.
- Closest public references: `nicholasglazer/gnosis-mcp` (SQLite + FTS5 + RRF hybrid; reports 8.7 ms mean MCP round-trip, p50 <30 ms hybrid on 700 docs), `alphabet-h/kb-mcp` (sqlite-vec + FTS5 + RRF + reranker), `macanolli/KnowledgeBaseMCP` (small-model-friendly: `quick_search` / `read_note` / `get_note_summary`).
- At 2500-3000 items, bulk-loading the corpus into context is ruinous: 3000 items × ~1 KB ≈ 3 MB ≈ hundreds of K tokens before ranking. Query-and-snippet contract is the only thing that scales.

**Implications for later phases**

- Phase 2 (file/archive reasoning and install planning), Phase 5 (test-session guidance), and the game-specific pressure points section all become consumers of KB queries — the KB is cross-cutting, which is why it runs as the KB-1..KB-6 track rather than as a single phase insertion.
- Save-safety automation (deferred) can use KB symptom records ("save not durable", "Papyrus stuck") as discovery surface once a real curator loop exists.
- LOOT integration (planned) can become a KB consumer (LOOT metadata → KB records on a known plugin set) rather than a separate MCP.

**Carry-forwards / risks**

- **Retrieval false negatives without embeddings**: mitigation = strong metadata + aliases + symptoms + task tags + `related` links. Vector store reserved as future option.
- **Stale folklore**: every record needs `confidence`, `sources`, `lastReviewed`. Unsourced "community says" facts get lower confidence rank.
- **Schema overreach**: keep body prose first-class. Maintainers will stop authoring if every nuance must fit a field.
- **xedit-mcp pollution**: bgs-kb-mcp must stay independent. If KB tools shipped inside xedit-mcp, they would inherit daemon-readiness failures exactly when the setup skill needs them.
- **File-count vs file-size**: prefer JSONL shards (small file count, larger per-file) over thousands of individual markdown files (Codex cache copy friction).
- **Plugin/KB compat drift**: enforce `minPluginVersion` + `schemaVersion` gates in `manifest.json`.

## 2026-06-01 — Batch 2 carry-forwards + portable publishability + Target 3 closure

**Delivered**

- **Batch 2 carry-forwards closed**:
  - CF #2 (audit uniformity): `xedit_session` and `xedit_list_capabilities` now emit stage-[7] audit lines via a shared `src/audit-line.ts` helper. `xedit_inspect_conflicts` audit lines now carry `daemonPid` and `sessionId` matching `xedit_read_record`'s shape.
  - CF #4 (MEDIUM findings): `runRules` returns `{ refusal, warnings, ruleHits }`. MEDIUM (and HIGH with `blockHigh=false`) findings surface as `Warning` entries on the success envelope's `warnings` array. CRITICAL still always blocks; HIGH blocks by default. Safe to add the first MEDIUM seed rule.
  - CF #5 (precheck.targetFileFromArg): retired. Load-order checks are owned by LOAD001 in the rule layer for every record-side tool. `find-record.ts` migrated off the precheck flag; the dead field was removed from `PrecheckNeeds`.
  - CF #6 (mapVerdict): lifted into `src/verdict.ts` so future record-side tools share one verdict vocabulary against the xEdit `caXxx` enum.
  - Bonus fix: `xedit_find_record` locators now round-trip the caller's `formId` / `file` style (e.g. `0x012345` stays `0x012345` instead of being downgraded to `012345` by the daemon's prefix-stripped echo).
- **Target 1 progress (portable publishability)**: `scripts/build-portable-plugin.ps1` materializes a self-contained portable plugin tree to `dist/portable-plugin/bgs-modding-superpowers/` (122 files, ~2.7 MB before `npm install`, zero reparse points) plus a sibling Codex-shape `marketplace.json`. The materialized `.mcp.json` and `tools/xedit-mcp/package.json` are rewritten for portable consumption (relative MCP path; `prepare`/`build`/`test`/`typecheck` scripts and devDependencies stripped). Semantic verification: stdio `initialize` + `tools/list` returns all 12 expected tools from the materialized tree after `npm install --omit=dev`.
- **Target 3 closed (Operator UX)**: "Smoothing first-run setup" had no concrete acceptance criteria. The invariants it referenced are already shipped — visible MO2 (`scripts/start-mo2.ps1`), non-blocking MCP lifecycle (`xedit_status` / `xedit_start` / `xedit_health` / `xedit_dirty` / `xedit_stop` / `xedit_restart`) — and the first-run orchestrator is the existing `setting-up-bgs-modding-environment` skill. Removed from Current Focus.

**Now known (from real implementation + verification)**

- The Batch 1 STATUS file claimed `precheck.targetFileFromArg` was unused after Batch 1 — that was wrong. `find-record.ts:62` was still using it. The carry-forward closure required migrating find-record onto LOAD001 first, then deleting the field. Lesson: when a carry-forward says "X is unused", grep the call sites before retiring.
- The portable plugin build cannot reuse the dev `package.json` as-is. The dev `prepare: npm run build` script and `devDependencies` (typescript, @types/node) would force any `npm install --omit=dev` consumer to also install dev deps or break. The build script rewrites the materialized `package.json` to drop both. `dist/` is the source of truth for the portable shape.
- Codex's marketplace schema is the only constraint that forced the `plugins/<name>/` layout. The local-only workaround under repo-root `plugins/` (gitignored) used directory junctions, which Codex's cache copy step silently drops. The portable script avoids junctions entirely.
- The MCP entry parses + runs from a freshly materialized tree against only the two runtime deps (`@modelcontextprotocol/sdk`, `zod`). No hidden coupling to the dev tree.

**Implications for later phases**

- A release-engineering step can now stage `dist/portable-plugin/bgs-modding-superpowers/` onto a release branch (or zip it as a release artifact) without further code changes.
- Batch 3 (mutating workflows) can now ship MEDIUM-severity rules confidently: the warnings channel is in place, so MEDIUM findings become visible without changing tool signatures.
- The shared `src/audit-line.ts` and `src/verdict.ts` modules are the canonical seams for any future tool that needs uniform stage-[7] auditing or `caXxx`-enum verdict mapping. Do not re-derive either per tool.

## 2026-06-01 — Reshape closeout (Superpowers-shaped multi-harness plugin)

**Delivered**

- Repo reshaped from `awesome-bgs-mod-master` dev harness + scattered scaffolds into a Superpowers-style plugin checkout with:
  - root `package.json`
  - `.claude-plugin/`, `.codex-plugin/`, `.mcp.json`, `.opencode/plugins/`, `.version-bump.json`, `hooks/`
  - public `README.md`, `CONTRIBUTING.md`, `LICENSE`, `RELEASE-NOTES.md`
  - internal docs consolidated under `docs/internal/`
- Working skills moved out of gitignored `.opencode/skills/` into tracked top-level `skills/`.
- New runtime skills landed: `using-bgs-modding-superpowers`, `setting-up-bgs-modding-environment`, `writing-modpack-devlog`, `writing-modpack-changelog`, `writing-bgs-load-order`.
- `tools/xedit-mcp/` ships `dist/` and a real stdio production entry. The MCP now provides:
  - non-blocking lifecycle tools (`xedit_status`, `xedit_start`, `xedit_health`)
  - read-only domain tools (`xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`, `xedit_call`)
  - explicit launch overrides (`dataPath`, `pluginsFile`, `gameMode`, `moProfile`, `launcherPath`)
  - dirty-state-safe control verbs (`xedit_dirty`, `xedit_stop`, `xedit_restart`)
- `scripts/start-mo2.ps1` landed to enforce the visible-MO2 invariant and handle zombie MO2 cleanup.
- `scripts/install-mo2-control-plane.ps1` was simplified so the Python plugin is the only deployable control-plane component at v0.1.
- `xEditHookBridge.dll` moved to `tools/xedit-hook-bridge/dist/` and ships as a tracked runtime artifact.
- Codex-specific marketplace support landed via `.agents/plugins/marketplace.json`, with a local-only `plugins/` workaround documented and gitignored.

**Now known (from real implementation + acceptance)**

- The old C++ `Mo2AgentControlPlugin` tree was a `STATIC` skeleton with no MO2 plugin interface; it could never have produced a usable `.dll`. The actual MO2 plugin is `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`.
- usvfs logs prove xEdit launched inside MO2's VFS; the missing-DLL diagnosis was wrong. The real early blocker was the 30s readiness timeout in `Wait-XeditClientAutomationReady`, which had to be bumped to 240s.
- The xEdit daemon's production main-entry needed a Windows-safe ESM entry detection fix (`pathToFileURL`) and then a real lazy `buildServerToolset()` wiring path.
- MCP clients that stringify nested `args` break a naïve `z.record(...)` schema; `xedit_call` must defensively accept both object and JSON-string forms.
- A correct xEdit launch needs an explicit `dataPath` (`-D:`) derived from MO2's `gamePath`, otherwise xEdit may fall back to the Windows registry and open the platform install path instead of MO2's managed game root.
- For experimentation, the right unit of control is an agent-authored `plugins.txt` plus `xedit_restart({ pluginsFile, dataPath, ... })`, not a manual `/mcp reconnect`.
- Codex's marketplace schema differs materially from Claude Code's. It requires a `source: { source: "local", path: ... }` object and a `plugins/<name>/` layout. It also strips directory junctions from its cache copy, which forced the current local workaround.

**Implications for later phases**

- A publishable Codex release likely needs a pre-build / pre-publish step that materializes a real `plugins/<name>/` tree with copied files and relative paths, not runtime junctions.
- The `writing-bgs-load-order` skill should be treated as the canonical authority for any future LOOT integration or profile-file mutation helpers; it already encodes the routing rules between file edits and daemon commands.
- Any future write-capable workflow must keep the current non-blocking MCP invariant. Domain tools must never wait minutes for xEdit startup.
- Save-safety automation should build on the new `xedit_dirty` / `xedit_stop` / `xedit_restart` semantics instead of inventing a second shutdown model.
- End-user install UX is now good enough for the dev sandbox, but portable packaging remains a separate release-engineering task, not just more documentation.

## 2026-05-31 — Batch 1 closeout (xEdit Skills + Harness MCP)

**Delivered**

- TypeScript MCP package at `tools/xedit-mcp/` with the 7-stage harness pipeline (stages [1][2][3][6][7] live; snapshot [4] and preview [5] reserved for Batch 3).
- Six MCP intent tools (`xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`) plus `xedit_call` atomic passthrough closing the CLI-bypass hole.
- Seed rule `LOAD001` (CRITICAL) and decoupled rule registry mechanism.
- Append-only JSONL audit logger with a never-throws contract.
- Curated 49-command capabilities digest, `keyArgs` independently verified against the xEdit fork source.
- Skills layer under `.opencode/skills/`: hub `xedit-automation` + knowledgebase + W2 task skill `xedit-conflict-audit`.
- Live W2 semantic acceptance against the MO2-backed xEdit daemon: 3/3 integration tests pass, real `caConflict` / `caOnlyOne` verdicts derived from real `conflict.all` values, real override chains and referenced_by populated.
- Oracle re-review verdict: `accept_with_followups`.

**Now known (from real implementation)**

- xEdit's automation daemon writes response files as UTF-8 *with BOM* on Windows; `JSON.parse` requires the leading `0xFEFF` stripped first.
- `system.describe` returns the friendly game label as `gameName`, not `gameMode` (which is the internal `gmFO4` token).
- `files.list` returns an array of objects (`{name, loadOrder, fileName, isESM, ...}`), not strings.
- The daemon rejects `0x`-prefixed FormIDs and answers `invalid_request`; MCP must strip the prefix at the edge.
- `records.conflict_status` returns the conflict label under `result.conflict.all` using the xEdit `caXxx` enum, not as a top-level flat `result.status`.
- `xedit-client.ps1` verified subcommand surface is `process launch | status | wait | stop` plus `automation call`, with `automation call --xedit-pid <pid> --request-file <reqPath> --response-file <resPath> --timeout-seconds <n>`. `process launch` accepts `--launcher-path / --game-mode / --mo-profile`. Codified in `AGENTS.md`.
- The working live-test launch shape is: pre-launch MO2 with `Start-Process` (no tool arg) so the Mo2AgentControl plugin loads and writes the bootstrap files; then `xedit-client.ps1 process launch` triggers the broker's `launch.start` which runs xEdit-as-tool via `OpenCodeVfsLauncher`. Direct `ModOrganizer.exe ... run -e <tool>` against an already-running MO2 does **not** dispatch the tool.

**Implications for later phases**

- Batch 2 (read-only completion): reuse the formId normalization, `files.list` object-shape handling, and BOM-strip patterns already in the adapter/session/tools — do not re-derive them per tool.
- Batch 2 must fold in oracle v2 follow-ups: representative W2 matrix (add a `breaking` fixture), audit uniformity (session + list_capabilities still don't write audit lines), and manual GUI parity evidence preservation.
- Batch 3 (mutating jobs with snapshot + preview): the composer already supports stages [4] and [5] insertion points; the top-level try/catch in `runTool` keeps the audit + envelope shape uniform on unexpected throws.
- Batch 3+: `save → fresh daemon restart → readback` durability semantics become mandatory before any mutating workflow can claim acceptance.
- xEdit fork coordination (`-automation-mcp-mode` + `mcpToken` enforcement) remains the prerequisite for declaring the harness mandatory, not a Batch 1 blocker.

**Carry-forwards (full list in `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md`)**

- runRules silently discards MEDIUM findings — must surface as warnings before the first MEDIUM rule lands.
- `precheck.targetFileFromArg` is unused after Batch 1 — decide whether to retire it or document its future use.
- `mapVerdict` should lift to a shared `src/verdict.ts` once more record-side tools land.
- Daemon-adapter PowerShell-hop latency (~1-2s per call) is fine for Batch 1's read-only flows but needs measurement before snapshot/preview-heavy mutating flows.

The Batch 1 plan, spec, full STATUS file, and acceptance artifacts are preserved at the paths listed above.

## Supporting Docs

- `README.md` for the project scope and top-level repo entry point.
- `docs/internal/standards/repo-hygiene.md` for durable content and artifact-handling rules.
- `docs/internal/plans/2026-04-10-bgs-modpack-superpowers-design.md` for the broader product architecture and workflow-first model.
- `docs/internal/plans/2026-04-10-bgs-modpack-superpowers-bootstrap.md` for the original repository bootstrap sequence.
- `docs/internal/plans/2026-04-10-roadmap-refresh-design.md` for the roadmap-as-control-panel design intent.
- `docs/internal/plans/2026-04-10-roadmap-refresh.md` for the implementation steps behind this roadmap refresh.
- `tools/README.md` for implementation code and automation placement.
- `tools/mo2-vfs-launcher/xedit-client.md` for the native xEdit outer-client boundary.
- `docs/internal/mcp-specs/README.md` for MCP specs and contracts only.
- `tests/README.md` for bootstrap verification and future test coverage direction.

## Appendix: BGS modding source list (KB-4 fan-out research targets)

Curated 2026-06-02 by `@librarian-beta` with live web verification. URLs checked, Cloudflare / anti-bot status flagged per entry, Discord invites validated via the Discord invite API. Where simple HTTP returned 403 or hit a Cloudflare challenge, the source was re-verified via Playwright (real Chromium fingerprint passes the "Just a moment..." gate after ~3-8 seconds). Subagents at KB-4 fan-out time MUST follow the per-entry `Fetch strategy` and switch to Playwright on any Cloudflare challenge — do NOT fall back to prior-based summarization.

### Load-bearing summary

1. **xEdit docs + xEdit Discord + TES5Edit GitHub** — core sources for plugin records, conflict semantics, cleaning, automation, and tool behavior across all five games.
2. **Nexus Mods + Bethesda Creations + ModDB + LoversLab + AFK Mods** — main mod-discovery and author-note surfaces. Use Nexus public API where possible and Playwright where pages block simple HTTP.
3. **CK Wiki (UESP mirror) + GECK Wiki + UESP + Independent Fallout Wiki + Starfield Wiki** — best structured references for editor concepts, Papyrus, GECK, lore, records, game content. Note: official `creationkit.com` is currently down/redirected; the UESP mirror at `ck.uesp.net` is the current accessible canonical for the Skyrim CK.
4. **MO2 + LOOT + Wabbajack + Mutagen + Spriggit + Synthesis** — canonical for modpack tooling, load-order automation, virtualized installs, generated patchers, plugin text serialization.
5. **Sim Settlements + TTW + AFK Unofficial Patch forums + STEP / DynDOLOD + r/skyrimmods + r/falloutmods + tool Discords** — high-signal community sources for compatibility, precombines / LOD, settlement systems, TTW rules, real load-order failure cases.

### Section 1 — Mod hosts / mod databases

| Name | URL | Primary topics | Games | Access | Fetch strategy |
|---|---|---|---|---|---|
| Nexus Mods: Skyrim LE | https://www.nexusmods.com/skyrim | Mod pages, files, posts, bugs, requirements | SK | Public; files/login gated | simple HTTP / Playwright if blocked |
| Nexus Mods: Skyrim SE/AE | https://www.nexusmods.com/skyrimspecialedition | SSE/AE mods, collections, tools | SK | Public; files/login gated | simple HTTP / Playwright if blocked |
| Nexus Mods: Fallout 4 | https://www.nexusmods.com/fallout4 | FO4 mods, collections, posts, bugs | FO4 | Public; files/login gated | simple HTTP / Playwright if blocked |
| Nexus Mods: Fallout New Vegas | https://www.nexusmods.com/newvegas | FNV mods, xNVSE ecosystem, bug tabs | FNV | **Simple HTTP returned 403; Playwright verified** | **Playwright** |
| Nexus Mods: Fallout 3 | https://www.nexusmods.com/fallout3 | FO3 mods, legacy compatibility | FO3 | **Simple HTTP returned 403; Playwright verified** | **Playwright** |
| Nexus Mods: Starfield | https://www.nexusmods.com/starfield | Starfield mods, Creations-era compatibility | SF | Public; files/login gated | simple HTTP / Playwright if blocked |
| LoversLab | https://www.loverslab.com/ | Adult mods, animation frameworks, technical support | SK / FO4 / FO3 / FNV / SF | Public forum index; adult content; login for downloads | simple HTTP; Playwright/login for downloads |
| ModDB: Skyrim SE | https://www.moddb.com/games/the-elder-scrolls-v-skyrim-special-edition/mods | Mod pages, total conversions, mirrors | SK | Public; no Cloudflare observed | simple HTTP |
| ModDB: Fallout 4 | https://www.moddb.com/games/fallout-4/mods | FO4 large projects, total conversions | FO4 | Public | simple HTTP |
| ModDB: Fallout New Vegas | https://www.moddb.com/games/fallout-new-vegas/mods | FNV total conversions, legacy mods | FNV | Public | simple HTTP |
| ModDB: Starfield | https://www.moddb.com/games/starfield/mods | Starfield mod pages, early projects | SF | Public | simple HTTP |
| Schaken-Mods | https://schaken-mods.com/ | Skyrim/FO4 mods, tutorials, community | SK / FO4 | Public landing; registration for much content | simple HTTP; Playwright/login if gated |
| AFK Mods Downloads | https://www.afkmods.com/index.php?/files/ | Arthmoor mods, unofficial patch downloads | SK / FO4 / SF | Files visible; some downloads/posts require account | simple HTTP / Playwright (login) |
| Bethesda Creations: Skyrim | https://creations.bethesda.net/en/skyrim/all | Official Creations, console mods | SK | JS app; login for library | **Playwright (JS app)** |
| Bethesda Creations: Fallout 4 | https://creations.bethesda.net/en/fallout4/all | FO4 Creations, console mods | FO4 | JS app | **Playwright (JS app)** |
| Bethesda Creations: Starfield | https://creations.bethesda.net/en/starfield/all | Starfield Creations | SF | JS app | **Playwright (JS app)** |
| CurseForge Starfield | https://www.curseforge.com/starfield | Starfield mods, performance/INI mods | SF | Public | simple HTTP |

### Section 2 — Dedicated game-or-topic forums

| Name | URL | Primary topics | Games | Access | Fetch strategy |
|---|---|---|---|---|---|
| Sim Settlements | https://simsettlements.com/ | Sim Settlements, Workshop Framework, settlement systems | FO4 | **Cloudflare "Just a moment" observed; passed via Playwright after 3s** | **Playwright (Cloudflare)** |
| AFK Mods Forums | https://www.afkmods.com/index.php?/forum/ | Unofficial patches, mod support, tools, Arthmoor notes | SK / FO4 / SF | Public; some subforums require login | simple HTTP; Playwright/login if blocked |
| TTW Forums | https://taleoftwowastelands.com/ | Tale of Two Wastelands, FO3-in-FNV, load-order rules | FO3 / FNV | Public phpBB-style; older read-only/historical | simple HTTP |
| ENBSeries Forum | http://enbdev.com/enbseries/forum/ | ENB binaries, presets, bugs, shader config | SK / FO4 / FO3 / FNV | Public; older forum; no Cloudflare | simple HTTP |
| ReShade Forum | https://reshade.me/forum | ReShade releases, shader troubleshooting | multi | Public; login for posting | simple HTTP |
| STEP Forum / Wiki | https://stepmodifications.org/wiki/Main_Page | Guide curation, LOD, tools, stable mod-build methodology | SK / FO4 / FNV | Public wiki | simple HTTP |
| Bethesda Community Hub | https://bethesda.net/community/ | Official community resources, Discord/Creations links | SK / FO4 / SF | Public | simple HTTP |
| Bethesda Official Forums (legacy) | https://forums.bethesda.net/ | Historical official forum discussions | SK / FO4 / FO3 / FNV / SF | **Live check failed; treat as dead/moved** | archived snapshot only (Wayback) |

### Section 3 — Wikis and documentation sites

| Name | URL | Primary topics | Games | Access | Fetch strategy |
|---|---|---|---|---|---|
| UESP | https://en.uesp.net/wiki/Main_Page | Elder Scrolls lore, quests, records, game data | SK / TES | Public | simple HTTP |
| **Creation Kit Wiki (UESP mirror)** | https://ck.uesp.net/wiki/Main_Page | Skyrim CK, Papyrus, editor reference, SKSE plugin docs | SK | **Cloudflare/security check; passed via Playwright after 3s** | **Playwright (Cloudflare)** |
| Official CK Wiki (legacy) | https://www.creationkit.com/index.php?title=Main_Page | Official CK docs | SK / FO4 | **Redirects to Bethesda wiki maintenance page** | archived snapshot only |
| Official FO4 CK Wiki (legacy) | https://www.creationkit.com/fallout4/index.php?title=Main_Page | FO4 CK docs, Papyrus | FO4 | **Redirects to Bethesda wiki maintenance page** | archived snapshot only |
| **Community GECK Wiki** | https://geckwiki.com/index.php?title=Main_Page | GECK, FO3/FNV scripting, editor usage | FO3 / FNV | **Cloudflare/security check; passed via Playwright after 3s** | **Playwright (Cloudflare)** |
| Independent Fallout Wiki | https://fallout.wiki/wiki/Fallout_Wiki | Fallout lore, game data, mod/community pages | FO3 / FNV / FO4 | Public | simple HTTP |
| Nukapedia / Fallout Fandom | https://fallout.fandom.com/wiki/Fallout_Wiki | Fallout lore, quests, items | FO3 / FNV / FO4 | Public; Fandom scripts | simple HTTP |
| Elder Scrolls Fandom | https://elderscrolls.fandom.com/wiki/The_Elder_Scrolls_Wiki | TES lore, quests, items | SK / TES | Public; Fandom scripts | simple HTTP |
| **Starfield Wiki (UESP team)** | https://starfieldwiki.net/wiki/Home | Starfield content, lore, modding links | SF | **Cloudflare/security check; passed via Playwright after 3s** | **Playwright (Cloudflare)** |
| Starfield Fandom | https://starfield.fandom.com/wiki/Starfield_Wiki | Starfield lore/content | SF | Public; Fandom scripts | simple HTTP |
| xEdit Docs / Tome of xEdit | https://tes5edit.github.io/docs/ | xEdit, cleaning, conflict resolution, records | SK / FO4 / FO3 / FNV / SF | Public | simple HTTP |
| LOOT Docs | https://loot.readthedocs.io/ | Load order, metadata, sorting | SK / FO4 / FO3 / FNV / SF | Public | simple HTTP |
| Wabbajack Wiki | https://wiki.wabbajack.org/ | Modlist installation/authoring, policies | SK / FO4 / FNV | Public | simple HTTP |
| DynDOLOD Docs | https://dyndolod.info/ | LOD, xLODGen, TexGen, DynDOLOD, occlusion | SK / FO4 | Public | simple HTTP |
| OpenMW Site | https://openmw.org/ | OpenMW, engine behavior | engine-shared / Morrowind | Public | simple HTTP |

### Section 4 — GitHub orgs / canonical tool repos

| Name | URL | Primary topics | Games |
|---|---|---|---|
| TES5Edit / xEdit | https://github.com/TES5Edit/TES5Edit | xEdit source, issues, releases, supported game modes | SK / FO4 / FO3 / FNV / SF |
| ModOrganizer2 / modorganizer | https://github.com/ModOrganizer2/modorganizer | MO2 source, plugins, usvfs, issues | SK / FO4 / FO3 / FNV / SF |
| Mutagen | https://github.com/Mutagen-Modding/Mutagen | C# Bethesda plugin parsing/editing | SK / FO4 / FO3 / FNV / SF |
| Spriggit | https://github.com/Mutagen-Modding/Spriggit | Plugin-to-YAML/JSON serialization, Git workflows | SK / FO4 / FO3 / FNV / SF |
| Synthesis | https://github.com/Mutagen-Modding/Synthesis | Mutagen patchers, generated patches | SK / FO4 / FO3 / FNV |
| LOOT | https://github.com/loot/loot | Load-order optimizer, issues, metadata logic | SK / FO4 / FO3 / FNV / SF |
| Wabbajack | https://github.com/wabbajack-tools/wabbajack | Automated modlist installer | SK / FO4 / FNV |
| xNVSE | https://github.com/xNVSE/NVSE | New Vegas script extender | FNV |
| BodySlide / Outfit Studio | https://github.com/ousnius/BodySlide-and-Outfit-Studio | Body morphs, outfit conversion | SK / FO4 |
| OpenMW | https://github.com/OpenMW/openmw | Open-source engine/editor | engine-shared / Morrowind |

All GitHub URLs: simple HTTP (public), no Cloudflare.

### Section 5 — Reddit (use old.reddit.com for clean extraction)

| Name | URL | Primary topics | Games |
|---|---|---|---|
| r/skyrimmods | https://old.reddit.com/r/skyrimmods/ | Skyrim modding, guides, troubleshooting | SK |
| r/falloutmods | https://old.reddit.com/r/falloutmods/ | Fallout modding, support rules, guides | FO3 / FNV / FO4 |
| r/fo4 | https://old.reddit.com/r/fo4/ | FO4 discussion, bugs, mod links | FO4 |
| r/fnv | https://old.reddit.com/r/fnv/ | FNV discussion, Viva New Vegas link, modding guides | FNV |
| r/fo3 | https://old.reddit.com/r/fo3/ | FO3 discussion, fix guide, mods | FO3 |
| r/starfield | https://old.reddit.com/r/starfield/ | Starfield discussion, official links | SF |
| r/starfieldmods | https://old.reddit.com/r/starfieldmods/ | Starfield modding, load orders | SF |
| r/skyrimvr | https://old.reddit.com/r/skyrimvr/ | Skyrim VR setup, SKSEVR, VRIK, FUS | SK VR |
| r/Mod_Organizer | https://old.reddit.com/r/Mod_Organizer/ | MO2 support | multi |
| r/wabbajack | https://old.reddit.com/r/wabbajack/ | Wabbajack support/modlists | multi |
| r/SkyrimModsXbox | https://old.reddit.com/r/SkyrimModsXbox/ | Xbox load orders, console compatibility | SK |
| r/xEdit | https://old.reddit.com/r/xEdit/ | xEdit usage/help | multi |

### Section 6 — Discord servers (invites verified via Discord API 2026-06-02)

| Name | Invite | Primary topics | Games |
|---|---|---|---|
| xEdit | https://discord.com/invite/5t8RnNQ | xEdit builds, docs, record/protocol discussions | SK / FO4 / FO3 / FNV / SF |
| Mod Organizer 2 | https://discord.com/invite/ewUVAqyrQX | MO2 support/dev, usvfs, logs | multi |
| Wabbajack | https://discord.com/invite/wabbajack | Wabbajack support, modlists, authoring | multi |
| Mutagen / Synthesis | https://discord.com/invite/53KMEsW | Mutagen, Synthesis, Spriggit | SK / FO4 / FO3 / FNV / SF |
| xNVSE | https://discord.com/invite/EebN93s | xNVSE support/dev | FNV |
| r/skyrimmods | https://discord.com/invite/M2Hz5v8 | Skyrim modding support/chat | SK |
| Fallout Network | https://discord.com/invite/tfn | Fallout discussion/modding/lore | FO3 / FNV / FO4 |
| Bethesda Game Studios | https://discord.com/invite/BethesdaStudios | Official BGS announcements, modding news | SK / FO4 / SF |
| Wildlander | https://discord.com/invite/8VkDrfq | Wildlander / Ultimate Skyrim support | SK |
| OpenMW | https://discord.com/invite/bWuqq2e | OpenMW, modding-openmw | Morrowind |
| Nemesis | https://discord.com/invite/9rXN6gr | Nemesis behavior engine, animation patching | SK |

Discord extraction: invites are link-stable (validated against the public Discord invite API). Pinned-message extraction requires login or a Discord-aware export tool — not directly scrapeable.

### Section 7 — xSE script-extender homes

| Name | URL | Games | Fetch |
|---|---|---|---|
| SKSE / SKSE64 / SKSEVR | https://skse.silverlock.org/ | SK LE / SE / AE / VR | simple HTTP |
| F4SE / F4SEVR | https://f4se.silverlock.org/ | FO4 / FO4 VR | simple HTTP |
| FOSE | https://fose.silverlock.org/ | FO3 | simple HTTP |
| xNVSE | https://github.com/xNVSE/NVSE | FNV | simple HTTP |
| SFSE | https://sfse.silverlock.org/ | SF | simple HTTP |

### Section 8 — ENB / shader / asset-pipeline hubs

| Name | URL | Primary topics | Games |
|---|---|---|---|
| ENBSeries main site | http://enbdev.com/ | ENB binaries, ENBoost, graphics mod | SK / FO4 / FO3 / FNV |
| ENBSeries forum | http://enbdev.com/enbseries/forum/ | ENB troubleshooting, presets, releases | SK / FO4 / FO3 / FNV |
| ReShade forum | https://reshade.me/forum | ReShade releases, shaders | multi |
| DynDOLOD | https://dyndolod.info/ | LOD generation, xLODGen, TexGen | SK / FO4 |
| BodySlide / Outfit Studio | https://github.com/ousnius/BodySlide-and-Outfit-Studio | Body/outfit conversion | SK / FO4 |
| Cathedral Assets Optimizer | https://www.nexusmods.com/skyrimspecialedition/mods/23316 | BSA / mesh / texture / animation conversion | SK / FO4 / FO3 / FNV |

### Section 9 — Bug trackers

| Name | URL | Topics | Games |
|---|---|---|---|
| Bugthesda / Tales from Tamriel | https://www.bugthesda.net/ (Discord-backed) | Bethesda game bug reporting | SK / FO4 / SF |
| xEdit Issues | https://github.com/TES5Edit/TES5Edit/issues | xEdit bugs/features | multi |
| MO2 Issues | https://github.com/ModOrganizer2/modorganizer/issues | MO2 bugs/features | multi |
| LOOT Issues | https://github.com/loot/loot/issues | LOOT bugs/features | multi |
| OpenMW Issues | https://gitlab.com/OpenMW/openmw/-/issues | OpenMW bugs/features | Morrowind |
| AFK USSEP Forum | https://www.afkmods.com/index.php?/forum/351-unofficial-skyrim-special-edition-patch/ | USSEP bugs, release notes | SK |
| AFK UFO4P Forum | https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/ | UFO4P bugs, patch discussion | FO4 |
| AFK USFP Forum | https://www.afkmods.com/index.php?/forum/416-unofficial-starfield-patch/ | USFP/USSP bugs, Starfield patching | SF |

### Section 10 — Long-form dev write-ups / guide ecosystems

| Name | URL | Topics | Games |
|---|---|---|---|
| STEP Wiki | https://stepmodifications.org/wiki/Main_Page | Stable mod-build methodology | SK / FO4 / FNV |
| DynDOLOD Docs / FAQ | https://dyndolod.info/ | LOD generation, warnings/errors | SK / FO4 |
| Wabbajack Wiki | https://wiki.wabbajack.org/ | Modlist authoring, policies | multi |
| Mutagen Docs | https://mutagen-modding.github.io/Mutagen/ | Mutagen API, typed records, patcher examples | SK / FO4 / FO3 / FNV / SF |
| Spriggit Docs | https://mutagen-modding.github.io/Spriggit/ | Plugin serialization, Git workflows | multi |
| Synthesis Docs | https://mutagen-modding.github.io/Synthesis/ | Patcher development, pipeline usage | multi |
| xEdit Docs / Tome of xEdit | https://tes5edit.github.io/docs/ | xEdit usage, cleaning, conflicts | multi |
| Wildlander Site | https://wildlandermod.com/ | Roleplay modlist, support, install | SK |
| OpenMW Site | https://openmw.org/ | Engine releases, Lua API, mod compatibility | Morrowind |
| Cathedral Assets Optimizer Nexus page | https://www.nexusmods.com/skyrimspecialedition/mods/23316 | Asset optimization instructions and warnings | SK / FO4 / FO3 / FNV |

### Meta-notes for KB-4 subagent prompts

- **Use Playwright for Cloudflare / anti-bot gates.** Verified during this survey: Sim Settlements, CK UESP mirror, GECK Wiki, Starfield Wiki, and FO3 / FNV Nexus pages all returned challenge pages on simple HTTP and passed via Playwright with `time: 3-8s` wait. Simple HTTP failure does NOT mean the site is dead.
- **Nexus behavior varies by game/page.** Skyrim / FO4 / Starfield Nexus pages fetched cleanly; FO3 / FNV returned 403 via simple HTTP. For scale, prefer the Nexus public API where it covers the needed fields, and Playwright for description / posts / bugs pages otherwise.
- **Bethesda's old official forum / wiki surfaces have moved or degraded.** `forums.bethesda.net` was not reachable; `creationkit.com` redirects to a maintenance page. Current routing: Bethesda Community Hub + Bethesda Game Studios Discord `#modding-news`. The CK UESP mirror (`ck.uesp.net`) is the current accessible canonical for the Skyrim CK Wiki.
- **Discord is often canonical but not scrape-friendly.** Invites are link-stable; pinned-message extraction requires login or a Discord-aware export tool.
- **Treat community claims by source class.** Official / tool docs and GitHub issues are authoritative for tool behavior; AFK / TTW / Sim Settlements are authoritative for their own projects; Reddit is best for field reports and sidebar guide links, not final truth without cross-checking.
- **Per-record `sources` discipline**: every KB record's `sources` field cites at minimum the URL and a kind tag (`tooling-docs` / `community-forum` / `official` / `wiki` / `github-issue` / `discord-pinned`). Unsourced facts default to `confidence: low-community` with a `needs verification` note per the KB-4 anti-copy guardrail.
