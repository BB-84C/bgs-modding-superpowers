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
| agentic cross-game BGS knowledge base | Planned (architecture chosen 2026-06-02) | Sibling `tools/bgs-kb-mcp/` + hybrid records under `knowledge/bgs-kb/` + bundled core + per-game Release-artifact packs. See 2026-06-02 entry for full architecture. Scale: ~2500-3000 items across Skyrim / FO3 / FNV / FO4 / Starfield, de-duplicated via per-game variant overlays. |

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

## 2026-06-02 — Agentic cross-game KB architecture (decision, not yet built)

**Context**

Today's xEdit knowledge surface is a single deep-reference markdown file (`skills/xedit-automation/xedit-knowledgebase.md`) and short skill bodies. The reference repo `WingedGuardian/skyrimvr-claude-toolkit` carries "600+ lines of Skyrim modding knowledge" as a single ~35 KB `KNOWLEDGEBASE.md` auto-loaded per session. That pattern does not scale to our target: ~2500-3000 items across Skyrim, Fallout 3, Fallout New Vegas, Fallout 4, Starfield, with significant shared BGS-engine substrate that should de-duplicate.

**Architecture decision (chosen after 4-way multi-perspective consultation: librarian-alpha on reference repo, librarian-beta on agentic KB tech survey, oracle + oracle-gamma on architecture)**

Storage model: **hybrid records** — structured frontmatter (id, title, domains, tasks, signatures, appliesTo.games, appliesTo.engineFamilies, appliesTo.excludes, severity, confidence, sources, lastReviewed) + prose body for nuance. Pure prose loses retrieval; pure structured loses caveat depth.

Cross-game de-duplication: **base record + per-game variant overlays**, NOT pure `games: [...]` tag duplication. A single "loose files override archives" record applies to FO4 + SkyrimSE with `variants.Fallout4` adding precombine/previs caveats and `variants.SkyrimSE` adding behavior-generation caveats. Variant merge happens server-side in `bgs_kb_get`.

Retrieval seam: **new sibling `tools/bgs-kb-mcp/`**, NOT folded into `xedit-mcp`. The substrate is different — xedit-mcp is a live-daemon execution harness with readiness semantics; the KB is static curated content with its own lifecycle. Per `~/.config/opencode/memory/40-low-intrusion-architecture.md`, the boundary is honest. The roadmap already frames `nexus-metadata` / `loot-metadata` / `translation-memory` as sibling MCP tracks; the KB joins that pattern. KB queries must work before MO2 / xEdit are configured.

Tool surface: `bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`, and optional `bgs_kb_check_updates` / `bgs_kb_install_pack` for network refresh. Query returns ranked snippet hits + appliesTo + sources; agent calls `get` only after a promising hit. Atomic primitives, not bundled "answer everything" tools.

v1 storage tech: **JSONL records + lightweight JS-side FTS** (minisearch or flexsearch). Pure-JS, zero native deps — preserves the plugin's current zero-native-dep invariant (multi-harness portability, Codex marketplace friction). SQLite + FTS5 stays the documented upgrade path if BM25-quality relevance becomes load-bearing.

Source of truth: `knowledge/bgs-kb/` **in this repo**:
- `knowledge/bgs-kb/schema/record.schema.json` — JSON Schema for record validation
- `knowledge/bgs-kb/core/records/{xedit,load-order,archive-precedence,papyrus}/...` — shared substrate
- `knowledge/bgs-kb/games/{fallout4,skyrimse,fallout3,falloutnv,starfield}/records/...` — per-game overlays
- `knowledge/bgs-kb/guides/...` — long-form prose where records are too granular (e.g. generated `xedit-deep-reference.md`)

Distribution:
- **Plugin ships `core` pack bundled** (small, ~1-3 MB) — works offline immediately.
- **Per-game packs published as GitHub Release artifacts** (`bgs-kb-fallout4-<version>.zip` etc.) pulled by `setting-up-bgs-modding-environment` skill on user consent.
- **Installed cache** at `%LOCALAPPDATA%/bgs-modding-superpowers/kb/<pack>/<version>/`.
- **Pack format**: zipped JSONL + `manifest.json` with sha256 + schemaVersion + minPluginVersion gates.
- **KB cadence** is independent of plugin cadence; KB content fixes do not force a plugin re-release.

Reference-repo lessons applied:
- Steal: hub-skill + on-demand-Read separation, path-glob auto-activation, slash-command workflow skills, top-N hot-cache, source-cited bottom-up entries.
- Avoid: single flat markdown at scale (35 KB × 5 games = 175 KB+ stops working before game #2), `skyrim-` skill prefix (would explode N×M with per-game tool wrappers), no per-entry game-mode tag (inline `(VR)` prose markers don't survive multi-game expansion), CLAUDE.md mixing config + knowledge routing.

**Migration phases (KB-1 .. KB-6)**

- **KB-1** — schema + seed records: extract today's high-value facts from `skills/xedit-automation/xedit-knowledgebase.md` and `skills/writing-bgs-load-order/SKILL.md` into structured records under `knowledge/bgs-kb/core/`. Old markdown stays put. JSON Schema + ~50 seed records.
- **KB-2** — `tools/bgs-kb-mcp/` ships `bgs_kb_status` / `bgs_kb_query` / `bgs_kb_get`. Loads bundled core pack only. New MCP registered in `.mcp.json` + `.opencode/plugins/bgs-modding-superpowers.js`. Portable-plugin build script copies `knowledge/bgs-kb/core/` + `tools/bgs-kb-mcp/dist/`.
- **KB-3** — `setting-up-bgs-modding-environment` skill gains explicit KB acquisition workflow: ask target games -> detect cache -> consent for >threshold downloads -> fetch from GitHub Releases -> verify checksum -> smoke test (`bgs_kb_query` returns hits) -> cache hygiene (prune old versions).
- **KB-4** — author per-game packs: FO4 (precombine/previs, BA2, settlement worldspace), SkyrimSE (scripts, animation generation, behavior outputs), FO3 / FNV (legacy plugins.txt + loadorder.txt model), Starfield (toolchain caution). Publish as GitHub Release assets.
- **KB-5** — `xedit-automation` lesson-log appending changes from "edit `xedit-knowledgebase.md`" to "add KB record"; mechanically-checkable footguns become xEdit MCP rule candidates; legacy markdown becomes generated-from-records or retired.
- **KB-6** — optional `bgs_kb_check_updates` + opt-in refresh; eval harness for retrieval quality (negative-case fixtures: "FO4 precombine" query with `game=skyrimse` filter should suppress FO4-only records).

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
