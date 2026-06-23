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
| mod evaluator | Shipped (judgment skill) 2026-06-23 | `skills/evaluating-bgs-mods/` — BB84 systems-simulationist framework (anti-checklist), game-agnostic body + core `mod-evaluation` KB records (`systemic-design-fit`, `quality-and-risk-signals`, `community-operational-signals` labeled non-BB84) + FO4 `fo4-previs` facts. First skill of the 思想论 judgment layer. Spec `docs/internal/plans/2026-06-23-sixiang-judgment-layer-architecture.md`; plan `docs/internal/plans/2026-06-23-evaluating-bgs-mods-implementation.md`. |
| install planner | Scaffolded only | Moved to `docs/internal/future-skills/install-planner/`; no real workflow yet. |
| conflict auditor | Shipped | The real workflow is now `skills/xedit-conflict-audit/` backed by the bundled xEdit MCP. |
| archive/loose-file reasoning helpers | Shipped 2026-06-13 | `tools/mo2-assets-engine/` Python engine + `mo2-assets` CLI + `tools/mo2-control-plane/live-bridge/mo2_assets_inspector*` IPluginTool GUI. Single shared engine; CLI and GUI agree on every verdict. Coverage: FO4 vanilla BA2 (GNRL + DX10), Skyrim LE/SE/AE/VR BSA v104/v105, FO3/FNV BSA v104, Starfield BA2 v2/v3, loose-file enumeration, 6-bucket conflict resolution mirroring MO2's `doConflictCheck`. 54 automated tests passing; sampled against `B:\WastelandBlues 2.0` (803 mods / 421k files / 80k conflicts) across 7 diverse cases with no semantic bugs. Known scope limits: INI `SArchiveList` (non-standard-named archives like `Fallout4 - Textures1.ba2`) deferred to Phase 3; FO4 next-gen BA2 v7/v8 deferred. See `docs/internal/plans/2026-06-13-mo2-assets-engine-and-cli.md` and `docs/internal/plans/2026-06-13-mo2-assets-inspector-ipluginthool-gui.md`. |
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
| MO2 control MCP | Shipped 2026-06-14 (v1) / v1.1.x polish 2026-06-16 | `tools/mo2-mcp/` TS MCP server + `tools/mo2-mcp-sidecar/` Python JSON-RPC sidecar + extended `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` broker (22 commands, snake_case). 34 agent-facing tools: 11 T1 reads (`mo2_status`, `mo2_machine_contract`, `mo2_modlist`, `mo2_pluginlist`, `mo2_mod_info`, `mo2_profile_ini_get`, `mo2_assets_summary`, `mo2_assets_conflicts`, `mo2_assets_resolve`, `mo2_search_files`, `mo2_list_executables`, `mo2_audit_query`), 5 T2 metadata writes (`mo2_set_mod_notes`, `mo2_edit_meta`, `mo2_profile_ini_set`, `mo2_backup_mod`, `mo2_backup_profile`), 18 T3 mutators (`mo2_toggle_mod`, `mo2_toggle_plugin`, `mo2_send_mod_to`, `mo2_rollback`, `mo2_restore_profile`, `mo2_install`, `mo2_run_tool`, `mo2_switch_profile`, `mo2_configure_executable`, `mo2_create_mod`, `mo2_create_separator`, `mo2_rename_mod`, `mo2_reinstall_mod`, `mo2_remove_mod`, `mo2_set_file_hidden`, `mo2_create_profile`, `mo2_clone_profile`, `mo2_rename_profile`). Architecture: plan/apply pattern with content-hash leases + snapshot-before-apply + cross-process file lock (`.mo2-mcp/leases/`) + JSONL audit. Safety pipeline: Zod `safeParse` central dispatch → 5 rules (STOCK001, PATHSAFE001, NAMESAFE001, CEILING001, future) → handler. FOMOD Pattern A non-interactive install via sidecar `pyfomod` integration. Cold-restart profile switching via broker `system.shutdown` + endpoint.json/status.json poll. Zip Slip rejection in archive extraction (`_validate_safe_member`). Cross-profile mutation guard (`assertActiveProfile`). Permission ceiling enforcement (T1=any, T2≥metadata-editable, T3=full-control). 315 unit tests + 64 sidecar pytest + 19 gated acceptance tests (set `MO2_MCP_ACCEPTANCE=1`; v15 run on 2026-06-16: 16 PASS / 3 SKIP env-gated / 0 FAIL against `.artifacts/mo2` harness + `B:\WastelandBlues 2.0` real-modpack fixtures). Two 3-lens oracle reviews + v1.1.x polish round resolved 10 v1 critical blockers + 5 round-2 polish + STOCK001 v1.1 (gamePath-derived deny instead of "Stock Game" literal) + `@ByteArray()` INI decode + broker `createMod` refresh-in-closure (per MO2 source `organizercore.cpp:705-732`) + sidecar auto-restart + `detectMo2Running` 3-signal ladder (process + profile-lock; shared-memory probe deferred) + WorldCache archive-content fingerprint + T3 ceiling fixture coverage + acceptance suite split (live + closed phases). Plans: `docs/internal/plans/2026-06-14-mo2-mcp-overview.md` + 9 stage plans + `PLAN-PATCH.md`; v1.1.x closeout in dated 2026-06-16 section below. Deferred to v1.2: TOCTOU file-level advisory locks (`LockFileEx` / `flock`), directory lease full-file `(relative_path,size,mtime_ms)` digest, `detectMo2Running` shared-memory probe completion. |
| safety hooks | Foundation in place | Runtime hook code lives in `hooks/`; hook specs moved to `docs/internal/hook-specs/`. |
| save-safety automation | Explicitly deferred | The design calls for it later, but no real save-safety automation should ship until a real curator loop exists. |
| agentic cross-game BGS knowledge base | Shipped (KB-1..KB-6 complete 2026-06-02; Starfield zh-Hans glossary pack added 2026-06-09) | Sibling `tools/bgs-kb-mcp/` + hybrid records under `knowledge/bgs-kb/` + SQLite3+FTS5+BM25 prebuilt index. 6 packs loaded at runtime: `bgs-kb-core` (114) + `bgs-kb-skyrim` (33) + `bgs-kb-fallout4` (34) + `bgs-kb-fallout3-fnv` (28) + `bgs-kb-starfield` (20) + `bgs-l10n-starfield-zhhans` (151k glossary entries) = ~151,655 total records. MCP surface: `bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`, `bgs_kb_check_updates`, `bgs_kb_install_pack`. Distribution: bundled core + per-game GitHub Release artifacts (`kb-2026.06.02` tag) + end-user packs via `$BGS_KB_USER_PACKS` discovery. Authoring workflow lives in `scripts/dev-kb-author.ps1` (see repo `AGENTS.md` "KB Authoring Workflow"). Known follow-up bugs: `records_fts` UNION on glossary-shape packs (scope queries with `packIds`); FTS5 hyphen-digit token parse error (drop the digit suffix or quote). |

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

### Cross-cutting track: Agentic Knowledge Base (KB-1 through KB-6) — SHIPPED

All six phases shipped on `main` in a single autonomous loop on 2026-06-02; carry-forwards cleared 2026-06-03; Starfield zh-Hans glossary pack added 2026-06-09. Full closeout entries below preserve the architecture decisions and per-phase deliverables.

- KB-1 — schema + 46 seed records + pack-build CLI (build/validate/info). **Shipped.**
- KB-2 — `tools/bgs-kb-mcp/` MCP server + 3 read-side tools + portable-plugin integration + bootstrap skill update. **Shipped.**
- KB-3 — `maintaining-modding-environments` skill + first-run KB acquisition steps. **Shipped.**
- KB-4 — 5 per-game packs (Skyrim, FO4, FO3+FNV, Starfield) + core expansion = 228 records across 5 packs (151k more after Starfield zh-Hans glossary pack). **Shipped.**
- KB-5 — `xedit-knowledgebase.md` retired to redirect; lessons now author KB records; schema gained `kind` enum + `rule-candidate` markings. **Shipped.**
- KB-6 — `bgs_kb_check_updates` + `bgs_kb_install_pack` + `cli prune-cache` + 20-query eval gold set (retrieval@3 = 0.800). **Shipped.**

Future expansion (additional records, additional games, community-contributed packs via `$BGS_KB_USER_PACKS`) is unblocked and not tracked as roadmap phases. Internal KB-pack authoring is documented in repo `AGENTS.md` ("KB Authoring Workflow — Internal Dev").

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

1. **Archive / loose-file reasoning helpers — SHIPPED 2026-06-13** (merge commit `fb7f090`). `tools/mo2-assets-engine/` Python engine + `mo2-assets` CLI + `mo2_assets_inspector` MO2 IPluginTool GUI all on `main` and in the vendor clone. Single shared engine: 54 automated tests passing (40 engine + 14 inspector), 2 gated harness tests passing on dev box. Sampled against `B:\WastelandBlues 2.0` profile `BB84自用` (803 mods, 421k files, 80k conflicts) across 7 diverse mods with no semantic bugs. Deployed and visually verified in both `.artifacts/mo2` harness and `B:\WastelandBlues 2.0`. Sampling artifacts under `.opencode/artifacts/mo2-assets-inspector/acceptance/wastelandblues-sampling/`. Plans at `docs/internal/plans/2026-06-13-*.md`. Known Phase-1 scope limits (INI `SArchiveList`, FO4 next-gen BA2 v7/v8) documented and behaving as designed. See dated closeout below.
2. **Unified MO2 control MCP — next major workstream.** Surfaced during the 2026-06-13 archive-helper construction. Today's MO2-facing capability is fragmented across four separate seams: `mo2-control-plane/live-bridge/mo2_agent_control.py` (headless launch + blocker watchdog over named-pipe), `mo2_assets_inspector.py` (asset conflicts GUI), `mo2-assets` CLI (asset conflicts agent surface), `mo2-vfs-launcher` (visible-start). The agent needs ONE coherent MCP that subsumes these and adds broader MO2 control (mod list / plugin list / archive enumeration / profile state / launch & blocker / save profile / tool invocation). Existing `mo2-control-plane` named-pipe broker is the natural transport. Design pending; this is the priority next workstream.
3. **Portable publishability** — `scripts/build-portable-plugin.ps1` materializes `plugins/bgs-modding-superpowers/` directly onto `main` as part of the two-commit dev cycle (source commit + materialized commit; see AGENTS.md 2026-06-03). End-users consume the plugin tree by cloning or pulling the repo (vendor-pull pattern for the OpenCode harness, marketplace-pointed clone for Codex / Claude Code). A separate "release branch / release artifact" channel was once considered for the plugin tree but is unnecessary — Codex / OpenCode / Claude Code all consume `git clone`-shaped state. The release-artifact channel is reserved for KB packs (large binary blobs that do not belong in the main tree; current cadence: `kb-YYYY.MM.DD` tags). The KB track must respect this — only the core pack ships inline in the plugin tree, per-game packs are GitHub Release assets.
4. **Read-only xEdit completion** — Batch 2 carry-forwards #2 / #4 / #5 / #6 are closed (see STATUS file). 2026-06-11 update: CF #7 closed-with-finding (PowerShell adapter ~3.5 s/call floor → Batch 3 must use direct Node named-pipe client; see `.opencode/artifacts/xedit-mcp/acceptance/batch2/cf7-latency/SUMMARY.md`); CF #3 agent half done (MCP envelopes for `Fallout4.esm` WRLD `0x0000003C` saved under `.opencode/artifacts/xedit-mcp/acceptance/batch2/manual-parity/fo4-WRLD-0000003C/`; human-side `xedit-gui.png` screenshot still pending); CF #1 (representative W2 matrix `breaking` fixture) deferred indefinitely until a real-world bug report justifies the fixture-hunt cost.

Target 3 ("Operator UX — smoothing first-run setup") was closed on 2026-06-01: the invariants it referenced (visible MO2 via `scripts/start-mo2.ps1`, non-blocking MCP lifecycle tools `xedit_status/start/health/dirty/stop/restart`) are already shipped, and "smoothing first-run setup" had no concrete acceptance criteria distinct from the existing `setting-up-bgs-modding-environment` skill.

## 2026-06-23 — 思想论 judgment layer batch2 built (pushed branch, pending merge)

**Delivered on feature branch `feat/sixiang-judgment-layer-batch2` (pushed, pending final user merge decision):** 4 new standalone judgment skills + 5 injected judgment sections + 3 new core KB records, all built on top of the flagship `evaluating-bgs-mods` pattern and reviewed/fixed in one batch.

- **4 standalone skills**: `interpreting-mod-author-instructions`, `curating-bgs-modpack`, `diagnosing-bgs-problems`, `testing-bgs-modpack`.
- **5 injections**: `xedit-conflict-audit` patch-vs-reorder, `xedit-automation` patch authoring judgment, `writing-bgs-load-order` ordering judgment, `using-bgs-archive` asset precedence judgment, `using-bgs-translator` localization judgment.
- **3 new core KB records**: `mod-evaluation.author-instruction-signals.v1`, `pack-curation.incremental-batching.v1`, `debugging.scanner-attribution-skepticism.v1`.
- **One batch-specific fix loop**: stale sibling references removed after all 4 skills existed; xEdit injections gained section-local KB query discipline; several game-specific inline examples were pushed back behind KB query walls.

**Now known:**
- Once the flagship anatomy is locked, the remaining judgment-layer construction is batchable: 9 worker lanes + one orchestrator fan-in worked cleanly when each fixer staged only its own paths.
- `testing-bgs-modpack` has intentionally thin substrate (34 `[GAP]` markers across skill + extraction). That is acceptable for now: honest gaps are better than generic QA filler.
- The bootstrap router has become the practical integration point for the whole judgment layer. Source and materialized plugin tree both now advertise all 5 judgment skills.

**Post-merge closeout (same day):**
- Merged feature branch to `main` via fast-forward (`39f7858..db9f271`); vendor clone at `D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers` synced.
- Live acceptance pass: 6 packs / 151670 records loaded, 0 warnings; all 3 new core records returned at score 1.0 for expected queries; `Skill_tool` loads new judgment skills clean; all `(forthcoming)` markers verified gone.
- Hotfix `fix(bgs-kb-mcp): wrap hyphen-bearing tokens as phrases` (commit `6359851`): live acceptance surfaced a pre-existing FTS5 query bug (`no such column: <suffix>` on tokens like `mis-attribution`, `CP-1252`, `UTF-8`). `sanitizeBare` now phrase-wraps any token containing chars outside `[\p{L}\p{N}_]` (Unicode-aware). 5 new regression tests in `tools/bgs-kb-mcp/tests/unit/sanitize.test.ts`; full suite 133/133 green. Existing OpenCode sessions must restart to load the fixed MCP code.
- KB Release `kb-2026.06.23` updated in-place (no version bump): `core-2026.06.23.zip` (298 KB / 125 records → 314 KB / 128 records) and `manifest-index.json` re-uploaded via `gh release upload --clobber`. Other 5 pack assets unchanged. Trade-off: `bgs_kb_check_updates` still says "no upgrade" for existing v2026.06.23 installs even though the artifact changed — explicit per-user decision to avoid a release-version bump cascade.

**Next:** remaining per-game KB backfill (Skyrim animation/script specifics, Starfield toolchain specifics, testing command catalogs/routes); revisit the FTS5 hyphen scope in AGENTS.md if other related parser quirks surface.

## 2026-06-23 — 思想论 judgment layer started (evaluating-bgs-mods shipped)

**Delivered (merged to `main` ff via `feat/sixiang-evaluating-bgs-mods` -> commit `1d7962a`; KB Release `kb-2026.06.23` published; vendor clone at `D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers` synced):** the architecture spec for the whole 思想论 judgment layer (5 standalone skills + 5 tool-skill injections + KB plan) plus the FIRST skill `evaluating-bgs-mods`. Built subagent-driven, grounded in the curator's own tutorial corpus (F-drive scripts + Bilibili AI subtitles + Bethesda design-philosophy essays, archived under `.opencode/artifacts/sixiang-sources/`). Live acceptance passed: `bgs_kb_query` returns the 3 new `mod-evaluation` records at score 1.0 for expected queries; Skill_tool loads `evaluating-bgs-mods` with all 3 oracle-review fixes intact.

- **Architecture**: hybrid carving (cross-stage judgment → standalone skills; tool-bound judgment → injected into the existing tool skill); game-agnostic skill body + per-game KB facts. Decided via multi-perspective brainstorm (oracle×2 + explorer + librarian + wildcard).
- **evaluating-bgs-mods**: BB84 systems-simulationist, anti-checklist framework; Iron Law (fit the pack's 风格 + reinforce systemic feedback; popularity/visuals/downloads are inputs not proof); query-KB-never-inline discipline; route gate + terminal handoff to `interpreting-mod-author-instructions`.
- **KB**: core `mod-evaluation` records faithful to BB84 (`systemic-design-fit`, `quality-and-risk-signals`) + a `community-operational-signals` record explicitly labeled non-BB84 (user-approved hybrid) + FO4 `fo4-previs` precombine/BA2 facts.

**Now known:**
- The curator's corpus is deliberately PHILOSOPHY/PROCESS-weighted, not checklist-weighted. Judgment skills should be strong on posture; modern operational signals belong in KB labeled "community-standard", never inlined into the skill body.
- Bilibili AI subtitles require login (`need_login_subtitle:true`); pulled via the user's SESSDATA + WBI signing; the full 13-video curriculum is archived.
- **Target 1 invariant confirmed**: only the `core` pack materializes into the portable plugin tree; per-game KB facts (the FO4 precombine/BA2 records here) live in source and reach end-users via a KB Release artifact, NOT the plugin tree.

**Also shipped in the same batch:**
- `bgs_kb_get` glossary-pack regression fix (`tools/bgs-kb-mcp/src/tools/get.ts` + `query.ts` defensive regex broadening + 2 regression tests in `tool-get.test.ts`). Root cause: `findRecordById` iterated all loaded packs and crashed with `no such column: canonical_answer` on the glossary-shape `bgs-l10n-starfield-zhhans` pack. Fix follows the same try/catch + skippedPacks pattern `query.ts` already uses for the `records_fts` case. Commits `49f93ed` (src+dist+tests) + `87fe3f2` (materialize).
- KB Release `kb-2026.06.23` (https://github.com/BB-84C/bgs-modding-superpowers/releases/tag/kb-2026.06.23) — 7 assets: `core-2026.06.23.zip` + `bgs-kb-fallout4-2026.06.23.zip` (changed) + 4 unchanged packs re-published for index completeness + `manifest-index.json`. `bgs_kb_check_updates` verifies the live release.

**Next:** remaining 思想论 skills per spec sequencing (xEdit patch-judgment injections → `curating-bgs-modpack` + `interpreting-mod-author-instructions` → `diagnosing-bgs-problems` → `testing-bgs-modpack`).

## 2026-06-16 — MO2 MCP v1.1.x LOW polish deferrals

- **D / TOCTOU narrowing deferred to v1.2.** Current v1.1.x still relies on content-hash leases plus the `.mo2-mcp/leases/` cross-process lock, which narrows but does not mathematically eliminate the window between `verifyLease()` and the actual target write. v1.2 should evaluate a real file-level advisory-lock substrate (`LockFileEx` on Windows, `flock` on POSIX) rather than shelling out per write. Acceptance should include a two-writer race fixture proving one writer blocks while the other holds the target file lock.
- **E / directory lease fingerprint upgrade deferred to v1.2.** Directory targets still use the current `{file_count,total_size}` fingerprint, which is cheap but cannot detect same-count/same-size content swaps. v1.2 should compare an upgraded directory digest `(relative_path,size,mtime_ms)` with a performance threshold: full digest for ordinary directories, explicit fallback for very large trees (candidate threshold: 5,000 files) so BodySlide-scale mods do not turn every plan into a costly scan.


## 2026-06-16 — MO2 MCP v1.2-pre lazy-bind refactor shipped

**Delivered (5 commits on `main`: `5bce94b` → `855b791` → `7a468cc` → `1a2786a` → `774786e`; feature branch `feat/mo2-mcp-lazy-bind` merged via fast-forward; vendor clone synced)**

**Why this batch existed**: OpenCode integration test surfaced a v1 design bug — `mo2-mcp/src/index.ts main()` hard-required `BGS_MO2_ROOT` at startup and `process.exit(1)`d if absent, coupling MCP-server startup to a pre-existing MO2 path. OpenCode could not register `config.mcp.mo2` with the same shape as xedit/bgs_kb (`environment: {}`, transparent parent-env passthrough) because the spawned child crashed and OpenCode reported `mo2 MCP error -32000: Connection closed`. The original commit-1 fix attempt (registering with `environment: {}`) hit the crash; the commit-2 detour (hardcoded `<PLUGIN_ROOT>/.artifacts/mo2` fallback in the plugin file) repeated the STOCK001-v1 anti-pattern of baking dev-machine convention into a shared file. Both were reverted in `c68eb75` before this batch landed the right fix.

**New architecture (mirrors xedit-mcp's daemon-adapter pattern)**:
- Server startup is now lazy: `BGS_MO2_ROOT` is OPTIONAL.
- New `BindingManager` (state machine: `unbound` / `binding` / `bound` / `failed`) owns the lazy lifecycle. The agent drives binding via the new `mo2_session` tool: `mo2_session({})` reads the snapshot, `mo2_session({mo2Root, profile?})` binds/rebinds, `mo2_session({unbind:true})` cleans up.
- `ToolContext` now carries `binding: BindingManager` instead of `config / pipeClient / sidecar`. The 36 existing tools call `requireBoundContext(ctx)` which extracts `bound.config / bound.pipeClient / bound.sidecar` — and falls back to a compat path for legacy unit-test fixtures that still construct ctx the old way (with getter/setter pass-through so in-place pipeClient/sidecar mutation by `mo2_switch_profile` stays visible).
- `main()` after the stdio transport connects: if `BGS_MO2_ROOT` is present, eagerly `await binding.bind({ mo2Root: $env, profile: $env })` BEFORE writing the `ready` log, so clients can treat the ready signal as "tools are usable immediately". A bind failure never blocks the server — it stays alive in `failed` state and the agent can recover via `mo2_session`.
- `dispatch.ts` awaitSettled hook: if a tool call arrives while a bind is in flight (`state === 'binding'`), `await ctx.binding.awaitSettled()` BEFORE dispatching. Applies to ALL tools including the binding-exempt ones so e.g. `mo2_status` answers with the bound view when a bind is imminent.

**Test verification**:
- Unit (vitest): 331 passed / 19 skipped / 0 failed (was 167/19/164 mid-refactor before fixture migration).
- Sidecar pytest: 64 passed.
- Spawn smoke no env: `mo2-mcp ready (..., binding=unbound)` then alive on stdio.
- Spawn smoke with env: `[mo2-mcp] eager bind bound (...)` then `binding=bound`.
- Acceptance suite (PS1 wrapper -Mode all): **16 PASS / 3 SKIP / 0 FAIL of 19** — matches the v1.1.x baseline exactly. Live phase 14/3/0 of 17, closed phase 2/0 of 2.

**Follow-up fixes landed in `1a2786a` after the lazy-bind core shipped (1 PS1 + 4 TS hits)**:
1. `main()` eager-bind reads `BGS_MO2_PROFILE` too (was reading only `BGS_MO2_ROOT`, so realEnv WL2 acceptance bound to `Default` instead of `BB84自用`).
2. `mo2_rollback` was reaching `bound.config.snapshotRoot` (`<mo2Root>/.mo2-mcp/snapshots`) while `ctx.snapshots` writes to `<tmpdir>/mo2-mcp-runtime/snapshots` (the SnapshotManager is constructed at startup before `mo2Root` is known). Writes and reads went to different roots → `snapshot_not_found`. Added `SnapshotManager.findManifest(snapshotId)` and rewrote `mo2_rollback` to use `ctx.snapshots` for both plan and apply.
3. `dispatch.ts` awaitSettled originally skipped binding-exempt tools, which left `mo2_status` returning the unbound view during the eager-bind race. Now applies to all tools.
4. `tests/acceptance-shared.ts` `spawnMcp` now sends `mo2_session({})` before returning so every child has settled bound state before the test runs.
5. `scripts/run-mo2-mcp-acceptance.ps1` `Ensure-HarnessMo2Alive` renamed to `Ensure-Mo2Alive($Root)` and the LIVE phase now starts BOTH MO2 launchers (WL2 + harness) because the live suite mixes `realEnv()` and `harnessEnv()` tests in the same vitest run. Multiple MO2 GUI processes coexist fine.

**Orthogonal closeout debt cleared in the same batch**:
- WL2 broker plugin (`B:\WastelandBlues 2.0\plugins\mo2_agent_control.py`) was stale at v1 (no `organizer.refresh()` calls inside the `mods.create` / `installation.create_mod_from_directory` main-thread closures — the v1.1.x AT16 fix). v1.1.x closeout pushed `main` and synced the plugin vendor clone but missed broker redeploy per MO2 instance. Redeployed via `pwsh scripts/install-mo2-control-plane.ps1 -MO2Root "B:\WastelandBlues 2.0" -Force`; SHA256 now matches `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`. Codified into `.opencode/memory/45-mo2-mcp-internals.md` rule 9 as a permanent closeout-audit step.

**Deferred to v1.2 proper (unchanged from the prior dated section above)**:
- TOCTOU file-level advisory locks (`LockFileEx` / `flock`)
- Directory lease full-file `(relative_path,size,mtime_ms)` digest
- `detectMo2Running` shared-memory probe (signal B — needs FFI)


## 2026-06-13 — Archive/loose-file helpers shipped (Plan A engine+CLI + Plan B MO2 IPluginTool GUI)

**Delivered (merge commit `fb7f090` on `main`; 22 individual commits previously on `feat/archive-loose-file-helpers`, now deleted local + remote)**

- `tools/mo2-assets-engine/` Python package: profile reader, BA2/BSA enumerators, archive load-order resolver, mod enumerator (mohidden-aware), 6-bucket conflict resolver, rationale module, `mo2-assets` typer CLI with 4 subcommands (`summary`, `mod-conflicts`, `resolve-file`, `archive-inventory`). 40 unit tests + 2 gated harness tests.
- `tools/mo2-control-plane/live-bridge/mo2_assets_inspector` MO2 IPluginTool: mobase paths bridge + main window (mod summary view) + mod detail dialog (3-section) + file detail panel (rationale + KB citation) + zh-Hans/en localization. 14 unit tests.
- `scripts/deploy-mo2-assets-inspector.ps1` for in-place deployment into MO2's plugin tree (auto-vendors the engine package alongside the plugin).
- Portable plugin tree (`plugins/bgs-modding-superpowers/`) and vendor clone (`D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers`) both carry the payload.

**Coverage**

- FO4 vanilla BA2 (GNRL + DX10)
- Skyrim LE / SE / AE / VR BSA v104 + v105
- FO3 / FNV BSA v104
- Starfield BA2 v2 + v3 (GNRL + DX10)
- Loose-file enumeration with `.mohidden` skip
- 6-bucket loose-vs-archive resolution mirroring MO2's `ModInfoWithConflictInfo::doConflictCheck()`

**Acceptance evidence**

- Synthetic fixtures pass for both BA2 (GNRL + DX10) and BSA (v105) wire formats. Self-tested round-trip.
- Gated harness tests pass on dev box against `.artifacts/mo2/profiles/Default` (FO4).
- Real-modpack sampling against `B:\WastelandBlues 2.0` profile `BB84自用` (803 enabled mods, 421k files, 80k conflicts) across 7 diverse mods (LODGen overlay, 海之南 worldspace, 海之南 patch, Boston Natural, Sim Settlements 2, 捏脸菜单扩展, and an unattached-BA2 case). All 7 bucket attributions verified correct. Artifacts under `.opencode/artifacts/mo2-assets-inspector/acceptance/wastelandblues-sampling/` (`summary.json` + 7 `mod-conflicts-*.json` files).
- GUI live-tested in MO2 against both `.artifacts/mo2` and `B:\WastelandBlues 2.0` instances. Plugin appears in Settings → Plugins, Tools menu shows `BGS 资源审计器`, window opens with mod table, double-click drills into 3-section detail dialog.

**Now known**

- **BSA v105 file-record `offset` interpretation:** documented as `folder_offset + total_file_name_length` per UESP; our reader subtracts `total_file_name_length` on v105 to recover the per-folder name+record block position. Round-trips cleanly against synthetic fixtures AND against real Skyrim SE BSAs in the harness.
- **BA2 DX10 (texture) directory layout:** `num_chunks` lives at byte offset 13 of the 24-byte texture header. Confirmed against real FO4 textures BA2s in the WastelandBlues sampling.
- **`meta.ini` is enumerated as a file.** Every mod has a per-mod MO2 metadata `meta.ini`. Our enumerator picks it up; it can appear in conflicts between mods even though MO2's runtime VFS never projects it into the game's Data folder. Minor cosmetic; flagged for a future "ignore well-known non-data files" pass. Not load-bearing — the file never reaches the game.
- **Non-standard-named archives are unattached.** FO4 mods that ship `Fallout4 - Textures1.ba2` through `... 09.ba2` (vanilla DDS replacements) rely on the game INI's `SArchiveList` to load. Phase 1 scope explicitly deferred INI parsing; these archives correctly show as "unattached" in our enumeration. WastelandBlues 2.0's "卢克索高清贴图大修 - 辐射4本体 01..09" series is the textbook case (each 9 GB on disk, 0 files reported because no matching enabled plugin). MO2's runtime UI surfaces these because MO2 hooks the engine load path; our Phase-1 offline enumeration cannot.
- **No across-call CLI cache.** Each `mo2-assets` invocation re-enumerates all enabled mods. ~9s for an 800-mod modpack like WastelandBlues 2.0. Acceptable for one-off queries; a future `--session` flag could cache across invocations. The IPluginTool GUI already caches via the `_World` class.
- **Anaconda PyQt6 DLL conflict.** Anaconda's bundled Qt6 conflicts with pip-installed PyQt6 (`DLL load failed importing QtWidgets`). Offscreen Qt smoke tests skipped at dev time as a result. PyQt6 runs fine inside MO2's embedded Python at runtime, where the inspector actually lives. Engine + non-Qt inspector tests (54 total) cover all the load-bearing logic.

**Implications for next workstream — unified MO2 control MCP**

The construction made clear that the agent's MO2-facing capability is fragmented across four separate seams (`mo2_agent_control` named-pipe broker, `mo2_assets_inspector` GUI, `mo2-assets` CLI, `mo2-vfs-launcher`). One unified MCP should subsume them. Target tools:
- `assets_summary` / `assets_mod_conflicts` / `assets_resolve_file` / `assets_archive_inventory` (subsume `mo2-assets` CLI as MCP tools).
- `mo2_status` / `mo2_modlist` / `mo2_pluginlist` / `mo2_archive_inventory` (broader MO2 surface).
- `mo2_launch_visible` / `mo2_run_tool` / `mo2_save_profile` (mutating control, gated like xEdit MCP's mutating ops).
- Transport: existing `mo2-control-plane` named-pipe broker.
- Lifecycle: independent of xEdit daemon (works pre-xEdit setup).

Captured in Capability Map row `MO2 control MCP` and Current Focus item 2 as the priority next workstream.

## 2026-06-03 - KB-* loop carry-forwards cleared (release live, end-to-end acceptance green)

Both carry-forwards documented in the 2026-06-02 `KB-* loop complete` entry are now closed.

**CF-1 cleared** (core kb.sqlite rebuild): a non-Node Windows process held kb.sqlite open with FILE_SHARE_READ + FILE_SHARE_WRITE but NOT FILE_SHARE_DELETE -- node:sqlite write-open succeeded, but `rm` returned EBUSY. Added `scripts/rebuild-locked-pack.mjs` (commit `bc87419`) as the durable escape hatch: drop all user-created schema objects in place, re-apply schema, repopulate, with a 60s `PRAGMA busy_timeout` to retry around external readers. Core pack now correctly reports **113 records**.

**CF-2 cleared** (Release artifacts published): `kb-2026.06.02` is live at https://github.com/BB-84C/bgs-modding-superpowers/releases/tag/kb-2026.06.02 with 6 assets:

| Asset | sha256 | Size |
|---|---|---|
| manifest-index.json | - | ~2 KB |
| core-2026.06.02.zip | 8e62033d2389... | 248.6 KB |
| bgs-kb-skyrim-2026.06.02.zip | d694f1fae684... | 84.8 KB |
| bgs-kb-fallout4-2026.06.02.zip | 7e1f778fed66... | 80.2 KB |
| bgs-kb-fallout3-fnv-2026.06.02.zip | ff6b379bbb01... | 67.4 KB |
| bgs-kb-starfield-2026.06.02.zip | df007b7843bb... | 46.3 KB |

**KB-6e graduates from mock to live**: `bgs_kb_check_updates({})` against the live Release returns `ok: true` with all 5 packs at `upgradeAvailable: false` (local matches latest) and `breakingChange: false` (plugin v0.2.0 >= each pack's `minPluginVersion` 0.2.0). The MCP server entry passes `currentPluginVersion: discovery.currentPluginVersion` correctly; the v0.2.0 plugin sees the v0.2.0 packs as compatible.

**Now known**

- The lock holder was outside Node's reach (likely Defender / Search Indexer / a sync client). Killing stale Node orphans did not release it. The structural fix is to not depend on file-level delete for in-place rebuild; the rebuild script does this by treating the file as a mutable SQLite database rather than a replaceable blob.
- `scripts/rebuild-locked-pack.mjs` is kept in-repo as a maintenance utility. The main `cli build` still tries the unlink-first deterministic path because it produces a cleaner inode under normal conditions; the rebuild helper is the explicit fallback when a contributor hits the lock.
- The maintenance utility uses a single 60s `PRAGMA busy_timeout` rather than wrapping the insert loop in an outer transaction (`insertRecord` already wraps each row in BEGIN/COMMIT and the SQLite driver rejects nested transactions). Per-row COMMIT retries are still fast enough at 228-record scale.

**The KB system is fully production-live**:
- 228 records across 5 packs queryable via `bgs_kb_query`
- update + install flow works against the real GitHub Release (not just the KB-6 mock)
- per-pack manifest sha256s match the published assets
- all six phases (KB-1..KB-6) plus both carry-forwards complete

No remaining open items from the KB-* loop. Future expansion would be additional records, additional games, or community-contributed packs via `\` -- not blocked by anything in this repo.

## 2026-06-02 - KB-* loop complete (all 6 phases shipped; 2 carry-forwards to next session)

The full KB roadmap — from architecture decision through acceptance evidence — shipped in a single autonomous loop spanning six phases on `main`.

### Phase summary

| Phase | Shipped | Commits | Tests added |
|---|---|---|---|
| KB-1 | schema + 46 seed records + pack-build CLI (build/validate/info) | 18 | 22 unit + 1 integration |
| KB-2 | sibling `bgs-kb-mcp` MCP server + 3 read-side tools + portable-plugin integration + bootstrap skill update | 14 | 100 unit + 2 integration (cumulative) |
| KB-3 | `maintaining-modding-environments` skill + `setting-up` split + bootstrap registration | 5 | docs-only |
| KB-4 | 8 parallel subagents (4 Stage A core + 4 Stage B per-game) -> 181 new records across 5 packs | 51 | per-pack manifests committed |
| KB-5 | xedit-automation lesson-log migrated to KB record authoring; `xedit-knowledgebase.md` retired to redirect; schema gained `kind` enum (+`rule-candidate`); 3 rule candidates marked | 7 | acceptance walkthrough record committed |
| KB-6 | `bgs_kb_check_updates` + `bgs_kb_install_pack` + `cli prune-cache` + 20-query eval gold set + mock-based install integration; MCP server now exposes 5 tools | 10 | 119 unit + 4 integration |

### Final state

- **228 KB records across 5 packs**: `bgs-kb-core` 113 + `bgs-kb-skyrim` 33 + `bgs-kb-fallout4` 34 + `bgs-kb-fallout3-fnv` 28 + `bgs-kb-starfield` 20
- **5 MCP tools** at the bgs-kb-mcp surface: `bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`, `bgs_kb_check_updates`, `bgs_kb_install_pack`
- **5 CLI subcommands**: `build`, `validate`, `info`, `prune-cache`, `--help`
- **119 unit + 4 integration tests** in `tools/bgs-kb-mcp/`; eval retrieval@3 = **0.800** (16/20 gold queries) on the current corpus
- **Anti-copy clean** across all 228 records: 0 verbatim >=40-char matches vs `WingedGuardian/skyrimvr-claude-toolkit/KNOWLEDGEBASE.md`
- **Sources structured** (kind + ref/url) on every record; 0 unsourced records
- **Per-pack manifests** committed + sha256-verified for skyrim / fallout4 / fallout3-fnv / starfield (core manifest stale per carry-forward below)
- Plugin version bumped to `0.2.0` to match `minPluginVersion` gates
- Three skills updated to teach the new surface: `using-bgs-modding-superpowers` (bootstrap), `setting-up-bgs-modding-environment` (first-run + KB acquisition), `maintaining-modding-environments` (ongoing care, custom packs, cache prune, update flow)
- `xedit-automation` skill migrated; durable lessons now author KB records instead of appending to a markdown handbook

### Two carry-forwards (require fresh-shell session)

**CF-1 — Rebuild core `kb.sqlite`**

The Windows file handle on `knowledge/bgs-kb/packs/core/kb.sqlite` got pinned during KB-4's parallel subagent CLI invocations and never released for the remainder of this session (8+ retries with cumulative 60s wait all returned `EBUSY` on `unlink`). The records on disk are correct; the core `manifest.json` still reports the pre-Stage-A count of 46 records.

To clear: open a fresh PowerShell / shell, then:
```powershell
cd D:\awesome-bgs-mod-master
node tools/bgs-kb-mcp/dist/cli.js build knowledge/bgs-kb/packs/core
git add knowledge/bgs-kb/packs/core/manifest.json
git commit -m "chore(kb): rebuild core manifest post-KB-4 (113 records)"
```

The expected sha256 will change; that's normal.

**CF-2 — Publish GitHub Release artifacts**

Once CF-1 is resolved, the publishing flow is straightforward; all the wire shape is implemented and proven by the KB-6 mock-based integration test:

```powershell
# in a fresh shell
# 1. ensure all 5 pack manifests are fresh
foreach ($p in @('core','bgs-kb-skyrim','bgs-kb-fallout4','bgs-kb-fallout3-fnv','bgs-kb-starfield')) {
  node tools/bgs-kb-mcp/dist/cli.js build "knowledge/bgs-kb/packs/$p"
}
# 2. zip each pack into bgs-kb-<id>-2026.06.02.zip
# 3. compute sha256 + sizeBytes per zip
# 4. build manifest-index.json listing all 5 packs with releaseUrl + sha256 + sizeBytes
# 5. gh release create kb-2026.06.02 *.zip manifest-index.json
# 6. run `bgs_kb_check_updates` + `bgs_kb_install_pack` against the live Release as KB-6e proper acceptance
```

After CF-2, the KB-6 acceptance walkthrough graduates from mock-backed to real-Release-backed.

### Now known across the full loop

- `node:sqlite` is good enough for both build and runtime, but holds Windows handles tenaciously across parallel worker processes. For parallel KB-authoring loops, consider building each pack in its own subprocess with explicit `db.close()` before exit (which the CLI already does), but also accept that the orchestrator may need a fresh shell to re-acquire write access after a heavy fan-out.
- Best-of-N was deliberately NOT used in KB-4 fan-out; single-fixer dispatches with structured prompts + Ajv validation + anti-copy diff + URL spot-check were sufficient at this scale.
- Playwright is essential for verifying any Cloudflare-gated BGS modding source (CK UESP mirror, Sim Settlements, AFK Mods, GECK Wiki, Starfield Wiki). Simple HTTP probes will silently lie about content; the source-survey appendix's per-entry fetch-strategy column is the contract subagents must follow.
- `bgs_kb_query` BM25 ranking on the 228-record corpus gives retrieval@3 = 0.800 on a hand-curated gold set. That's a decent baseline; lifting it past 0.9 will probably require either embedding-augmented re-ranking (KB-6+) or curation of `queryKeys` / aliases on the records that miss.
- The `debugging` domain still tags too many records (~60% of the core pack); narrowing it remains a future curation pass.
- End-user pack authoring works as designed: the KB-2 acceptance fixture proved `$BGS_KB_USER_PACKS` points at directories containing pack directories (not at a pack directory itself), and the `maintaining-modding-environments` skill phrases this carefully.

### Implications going forward

- The KB architecture is **production-ready as a local-first system today**. Network distribution is one fresh-shell release-engineering session away.
- KB-6's mock-based install integration test will become a real-Release integration test the moment CF-2 lands.
- The schema's new `kind` enum (with `rule-candidate`) opens a clean seam for promoting durable mechanical footguns into LOAD-style `xedit-mcp` rules without further schema churn.
- The Stage A controller-side anti-copy + URL spot-check pattern is the template for any future KB expansion (additional games, deeper per-game packs, or community-contributed packs via `$BGS_KB_USER_PACKS`).

### Repo state at loop end

- All six phase branches merged to `origin/main`:
  - `feat/kb-1-schema-and-seed-records` -> `7cde092`
  - `feat/kb-2-mcp-server` -> `9b81f9a`
  - `feat/kb-3-maintaining-skill` -> `8a09ded`
  - `feat/kb-4-fanout` -> `f4a3771`
  - `feat/kb-5-lesson-log-migration` -> `00ffc1a`
  - `feat/kb-6-updates-and-eval` -> `f5ff2b2`
- 105 KB-loop commits cumulatively shipped across the six branches.

## 2026-06-02 - KB-6 closeout (updates + install + cache prune + eval harness)

**Delivered (on branch `feat/kb-6-updates-and-eval`)**

- Added `bgs_kb_check_updates` with strict Zod args, registry `not_loaded` refusal, GitHub latest-release `manifest-index.json` fetch/parse, semver upgrade detection, breaking-change flagging, and partial warning envelope on fetch failure.
- Added `bgs_kb_install_pack` with exact-version pins, release-index asset lookup, streamed download, byte count + sha256 verification, zip extraction, manifest gate checks, dry-run support, atomic cache move, and incoming cleanup.
- Wired the MCP server tool surface from 3 tools to exactly 5: `bgs_kb_status`, `bgs_kb_query`, `bgs_kb_get`, `bgs_kb_check_updates`, `bgs_kb_install_pack`.
- Added `cli prune-cache [--dry-run]`, keeping current + previous cached pack versions per pack and removing older versions.
- Updated `maintaining-modding-environments` cache hygiene guidance to use `prune-cache --dry-run` before live deletion.
- Added a 20-query eval harness under `tools/bgs-kb-mcp/tests/eval/` plus a gated Vitest integration check. Threshold: `retrieval@3 >= 0.8`; actual current loaded-corpus score: `0.800` (`16/20`).
- Added a mock-release integration smoke that serves a local GitHub-style latest release, `manifest-index.json`, and fixture zip, then runs check-updates + install-pack against it.
- Refreshed compiled `tools/bgs-kb-mcp/dist/` artifacts so the checked-in runnable server/CLI include KB-6.

**Now known**

- The Release updater/install path can be fully exercised with a local HTTP fixture without publishing real GitHub Release artifacts.
- `yauzl` is the practical low-intrusion zip extractor for this package: `.zip` extraction via `node:zlib` alone is awkward because ZIP is a container format, not just a deflate stream.
- Eval currently runs against the discovered loaded pack sessions. Because the core `kb.sqlite` is still the stale pre-KB-4 artifact until the fresh-shell rebuild carry-forward, the loaded corpus is effectively 161 records even though the source records on disk are 228. The eval deliberately still passes at the documented `0.8` floor and records four ranking gaps.
- The expanded multi-pack corpus required loosening older integration expectations: server smoke now expects the multi-pack surface, and the raw FTS core smoke checks top-5 instead of top-3 for `plugins` because newer load-order records outrank the modern-asterisk record.

**Implications for later phases**

- Fresh-shell Release acceptance remains required: rebuild core `kb.sqlite`, zip all five packs, publish the GitHub Release assets + `manifest-index.json`, then run the same check/install path against the live Release.
- Eval failures are useful curation signals, not harness failures: `skyrim skse runtime`, `skyrim vr higgs`, `loot metadata`, and `node sqlite handle leak` should guide queryKeys / ranking work after the core rebuild.
- Cache layout now has two related surfaces: discovery/prune reads `%LOCALAPPDATA%/bgs-modding-superpowers/kb/packs/<packId>/<version>/`, while install stages through the parent `kb/` root as `incoming/` plus `packs/`.

**Acceptance evidence**

- `npm run build`: passed.
- `npm run typecheck`: passed.
- `npm test`: passed (`23` unit test files, `119` tests).
- `npm run test:integration`: passed (`4` integration test files, `4` tests), including eval and mock install smoke.
- `npm run eval`: passed with `retrieval@3=0.800`, `passed=16/20`, `failures=skyrim skse runtime,skyrim vr higgs,loot metadata,node sqlite handle leak`.
- MCP `tools/list` coverage is asserted by both unit and stdio integration tests and now returns exactly 5 tools.

**Carry-forward**

- Real Release-artifact E2E acceptance is deferred to a fresh-shell session after the core rebuild unblocks: rebuild core `kb.sqlite`, produce all five pack zips, publish the Release + `manifest-index.json`, then rerun check-updates/install-pack against GitHub instead of the local mock server.

## 2026-06-02 - KB-5 closeout (lesson-log migration; xedit-knowledgebase.md retired)

**Delivered (on branch `feat/kb-5-lesson-log-migration`)**

- Updated `skills/xedit-automation/SKILL.md` so durable xEdit automation lessons are authored as structured KB records instead of appended to `xedit-knowledgebase.md`.
- Retired `skills/xedit-automation/xedit-knowledgebase.md` to a short redirect note that preserves the path for historical links and points agents to `bgs_kb_query` / `bgs_kb_get` and source records.
- Marked KB-5c `cli render` as skipped because KB-5b chose retire-with-redirect over generated handbook maintenance.
- Added the additive `kind` schema enum with `rule-candidate`, then marked three core records as rule candidates and reserved follow-up rule IDs in `docs/internal/plans/2026-06-02-kb5d-rule-candidates.md`.
- Completed the lesson-log acceptance walkthrough by authoring `debugging.node-sqlite-windows-handle-leak.v1` for the Windows `node:sqlite` / `kb.sqlite` `EBUSY` handle gotcha found during KB-4.

**Now known**

- The existing record schema did not yet expose record-level `kind`; only source citations had `sources[].kind`, while `bgs_kb_query` already accepted a `kinds` filter shape. KB-5 added a record-level `kind` property as an additive schema v1 extension, but the current built SQLite/query path does not yet index or filter by that property.
- Retiring the handbook is lower-maintenance than adding `cli render`: current active skills can point at KB retrieval directly, while historical plans and old source citations can safely keep resolving through the redirect.
- The new lesson-log workflow can be exercised without rebuilding locked core SQLite artifacts: record authoring plus schema/CLI validation is sufficient until a fresh-shell core rebuild is available.

**Implications for later phases**

- A future bgs-kb-mcp pass should decide whether to persist record-level `kind` into `kb.sqlite` and make the existing `kinds` query filter semantically active.
- Future xEdit MCP rule work has three reserved starting points: `RULE_SAVE_DURABILITY_001`, `RULE_DATA_PATH_001`, and `RULE_DIRTY_STATE_001`.
- KB-6 should continue treating KB records as the source of truth and should not revive a generated monolithic handbook unless a concrete consumer appears.

**Acceptance evidence**

- `node tools/bgs-kb-mcp/dist/cli.js validate knowledge/bgs-kb/packs/core` passed after the schema enum addition, after the rule-candidate markings, and after the KB-5e record addition.
- Single-record Ajv check passed for `debugging.node-sqlite-windows-handle-leak.v1`.
- No `cli build` was run for the core pack, preserving the KB-4 carry-forward constraint that core `kb.sqlite` may still be locked on Windows.
- Inbound-reference grep was run for `xedit-knowledgebase`; active skill references were updated to KB retrieval, while historical plans / old source citations are covered by the redirect path.

## 2026-06-02 - KB-4 closeout (Stage A + Stage B fan-out: 227 KB records across 5 packs)

**Delivered (on branch feat/kb-4-fanout)**

Stage A (core pack expansion via 4 parallel subagents):
  - A1 xedit + plugin-format       19 records
  - A2 load-order + archive-prec.  15 records
  - A3 papyrus shared core         17 records (CK UESP via Playwright)
  - A4 engine + Spriggit tooling   15 records
  - 66 new core records on top of KB-1's 46 (112 records on disk)

Stage B (per-game packs via 4 parallel subagents):
  - B1 `bgs-kb-skyrim`           33 records
  - B2 `bgs-kb-fallout4`         34 records (incl. FO4 VR)
  - B3 `bgs-kb-fallout3-fnv`     28 records (GECK + NVSE/FOSE + TTW)
  - B4 `bgs-kb-starfield`        20 records (conservative; sparse public docs)

Total: 227 KB records across 5 packs. Each pack has `bgs-kb-meta.yml` and the four per-game pack manifests are built + committed + sha256-verified.

**Acceptance evidence (orchestrator side)**

- Anti-copy diff against `WingedGuardian/skyrimvr-claude-toolkit/KNOWLEDGEBASE.md` (35338 bytes -> 33963 forty-grams): **0 verbatim >=40-char matches** across all 227 records, scanned per pack.
- URL spot-check: 4/5 Stage A samples HTTP 200 (CK UESP 403 on HEAD is expected -- the A3 fixer verified via Playwright). 4/4 Stage B samples HTTP 200.
- Per-pack `cli validate` + `cli build` succeeded for all four game packs; manifests committed with sha256 entries matching the produced `kb.sqlite`.
- All Playwright probes from B1-B4 cleared: CK UESP, AFK UFO4P, Sim Settlements (partial), GECK Wiki, TTW, Starfield Wiki, Bethesda Creations Starfield.

**Now known**

- `node:sqlite` holds file handles on Windows even after the holding process exits in some configurations. After many parallel CLI build / validate invocations from subagent workers, the core pack's `kb.sqlite` became unlinkable for the orchestrator session (EBUSY on rebuild after 8+ retries with 60s aggregate wait). The records on disk are correct, but the core `manifest.json` still reports the pre-Stage-A count of 46 records.
- Per-pack manifests (skyrim / fallout4 / fallout3-fnv / starfield) are clean because each was built by its own fixer in its own Node process, with no inherited locks.
- Sim Settlements Cloudflare gate is intermittent even with Playwright; FO4 settlement records use `confidence: medium` where the source could not be fully verified.
- Starfield-specific facts are deliberately conservative because Starfield Wiki coverage is sparse and CE2 details are sometimes only available in the xEdit fork source. B4 shipped 20 records rather than the originally-targeted ~25 because the fixer refused to pad with unverified claims.
- The plan's >=2000 record target is aspirational; this loop ships a real 227-record foundation that exercises every schema seam (variants, excludes, related, queryKeys, sources). Deeper fan-out is a future iteration.

**Carry-forwards**

- **Core kb.sqlite rebuild**: regenerate in a fresh shell session (kills the lingering Node handle) before Release artifact zip creation. The `records/` subtree is the source of truth; running `cli build core` will produce a `kb.sqlite` + `manifest.json` that correctly reports 112 records.
- **KB-4h Release publishing** (GitHub Release artifacts for all 5 packs + `manifest-index.json`): deferred to a fresh session after the core rebuild. KB-5 and KB-6 do not depend on the Release being live.
- `debugging` domain remains broad as observed in KB-1; KB-4 records did not narrow it. Future curation pass.
- Sim Settlements + parts of Nexus Cloudflare gating may need a future Playwright pass with longer waits / different User-Agent.

**Implications for later phases**

- KB-5 can rely on the per-pack manifests for its lesson-log migration acceptance walkthrough.
- KB-6 can implement `bgs_kb_check_updates` / `bgs_kb_install_pack` against the per-pack pack format already proven by Stage B. The Release-artifact distribution still needs to be staged once the core rebuild completes.
- Final KB-* closeout entry should re-state the stale-core carry-forward so the next session begins by clearing it before any Release publish.

## 2026-06-02 — KB-3 closeout (maintaining skill + setting-up split)

**Delivered (on branch `feat/kb-3-maintaining-skill`)**

- Added `docs/internal/plans/2026-06-02-setting-up-maintaining-split.md`, documenting what stays in first-run setup vs what belongs in recurring maintenance.
- Added `skills/maintaining-modding-environments/SKILL.md` as the recurring-care home for KB updates, cache hygiene, custom pack authoring / registration, version pinning, and health checks.
- Slimmed `skills/setting-up-bgs-modding-environment/SKILL.md` toward first-run orchestration and added first-run KB target selection / pack acquisition: chosen games, bundled core pack, future per-game GitHub Release downloads, sha256 verification, cache install, and `bgs_kb_query` smoke.
- Updated `skills/using-bgs-modding-superpowers/SKILL.md` so agents can route ongoing environment maintenance to the new skill instead of the first-run setup skill.

**Now known (from the split pass)**

- The existing setup skill did not contain whole ongoing-care sections to delete; it was already mostly first-run setup plus semantic smoke. KB-3 therefore added the maintenance surface net-new and migrated only reusable concepts (version pinning, health checks) into the new skill.
- The important user-pack wording is now captured in the maintenance skill: `BGS_KB_USER_PACKS` entries are roots containing pack directories, not pack directories themselves.
- First-run KB acquisition and recurring KB maintenance are distinct: setup can choose target games and install published per-game packs, while custom-pack authoring / cache pruning / update cadence belongs to maintaining.

**Implications for later phases**

- KB-4 per-game pack publication now has a documented consumer path: first-run setup can install chosen official packs, and maintaining can update or pin them later.
- KB-5 lesson-log migration can point contributors toward the custom-pack authoring / build / validate / info workflow in `maintaining-modding-environments` instead of overloading first-run setup.
- KB-6 should replace the maintaining skill's fallback GitHub Release instructions with direct `bgs_kb_check_updates` / `bgs_kb_install_pack` usage once those tools exist.

**Acceptance evidence**

- Plain inspection only, per KB-3 instruction: no code changed and no tests were run.
- Bootstrap skill now has distinct triggers: setup for first conversation / MO2 or xEdit missing / set up / install; maintaining for ongoing / maintain / register custom pack / prune cache / update knowledge base / health check.
- Custom-pack walkthrough routes through `maintaining-modding-environments`, builds with `node <plugin>\tools\bgs-kb-mcp\dist\cli.js build <pack-root>`, validates / infos the pack, and registers a user root containing pack directories.
- Fresh FO4 setup walkthrough stays in `setting-up-bgs-modding-environment`: detect or install MO2, select `Fallout4`, rely on bundled core, optionally install future FO4 pack with consent + sha256, then smoke with `bgs_kb_query({ query: "plugins", games: ["Fallout4"], maxResults: 3 })` before continuing to MO2 / xEdit setup.

## 2026-06-02 — KB-2 closeout (local MCP retrieval surface + portable/plugin integration)

**Delivered (on branch `feat/kb-2-mcp-server`)**

- `tools/bgs-kb-mcp/` now ships the local retrieval runtime: pack discovery across bundled / cache / user roots with manifest validation, schemaVersion gating, minPluginVersion gating, sha256 integrity checks, and collision reporting; a read-only SQLite session registry over loaded packs; a shared envelope module (`ok` / `refuse`, `KB_ERROR_CODES`); `bgs_kb_status`, `bgs_kb_query`, and `bgs_kb_get`; the stdio MCP server entry; and 100 unit tests + 2 integration tests.
- Plugin / harness integration is wired end to end: `.mcp.json` exposes sibling `bgs_kb` alongside `xedit`; `.opencode/plugins/bgs-modding-superpowers.js` registers the sibling MCP; `scripts/build-portable-plugin.ps1` carries `tools/bgs-kb-mcp/` plus the bundled core pack into the portable tree; and `skills/using-bgs-modding-superpowers/SKILL.md` advertises the `bgs_kb_*` tools and routing doctrine.
- Plugin version is bumped to `0.2.0` to align with the core pack's `minPluginVersion`.

**Now known (from real KB-2 implementation)**

- **`node:sqlite` is good enough for the MCP runtime too**, not just the build CLI. Read-only open works, FTS5 `MATCH` works, and the real core pack answers queries in the low-single-digit ms range at current scale.
- **`BGS_KB_USER_PACKS` points at roots containing pack directories**, not at a pack directory itself. The acceptance fixture surfaced this; KB-3 docs / skill wording must be careful and explicit.
- **Cross-pack ranking uses per-pack BM25 magnitude normalization (Choice A)**, not RRF. This is good enough at current pack sizes; RRF remains a KB-6 enhancement.
- **Empty registry policy is strict `not_loaded`.** `query` / `get` refuse when no packs are loaded.
- **Variant warnings render as Markdown callouts** in the merged body: `> [!WARNING] [CODE|severity] text`.
- **`debugging` domain remains broad** from KB-1. KB-2 query behavior confirms it returns many hits and needs later tightening.
- **Portable now includes runtime dependency closures for both MCPs.** The resulting tree is ~32.86 MB before any end-user game-pack downloads. This is larger than the pre-KB portable tree and acceptable for now, but worth watching.
- **Current `plugins` all-games ranking is corpus-driven.** The real query returns `modern-asterisk`, `plugins-vs-modlist`, then `legacy` in the top 3. Later curation may rebalance this by adjusting queryKeys or domain tags rather than changing SQL first.

**Implications for later phases**

- **KB-3 (`maintaining-modding-environments`)** must explicitly teach the `BGS_KB_USER_PACKS` root semantics, not "point to a pack directory".
- **KB-3 / KB-4** should add a contributor-friendly schema validation command to replace raw Ajv 2020 invocation (`ajv-cli` still does not support Draft 2020-12 cleanly).
- **KB-4 fan-out subagents** can rely on `cli validate` and the MCP retrieval surface for spot-checking authored records before returning.
- **KB-6** `bgs_kb_check_updates` / `install_pack` already have a natural insertion point in the existing server entry and pack-discovery lifecycle.
- **Portable size should stay visible.** If core pack + deps + future per-game bundled assets keep growing, consider whether `bgs-kb-mcp` and `xedit-mcp` can share a lighter runtime dependency footprint before bundling more content — but do not prematurely merge servers.

**Acceptance / evidence**

- 100 unit tests + 2 integration tests pass.
- `bgs_kb_status` on the real plugin tree shows 1 bundled pack (`bgs-kb-core`) with 46 records.
- `bgs_kb_query({ query: 'loose files override', games: ['Fallout4'] })` returns the asset-precedence record with the Fallout 4 variant warning note.
- `bgs_kb_get({ id: 'papyrus.oninit-vs-onload.v1', game: 'FalloutNV' })` returns `appliesToRequestedGame: false` with a `game_excluded` warning.
- A user fixture pack under a user root discovered via `$BGS_KB_USER_PACKS` loads correctly and is queryable; totalRecordCount rises from 46 to 47.

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

## 2026-06-17 — MO2 MCP v1.2 batch1: ENRICHMENT L1+L2 + BUG-11 + BUG-13 shipped

**Delivered (6 commits on eat/mo2-mcp-v1.2-batch1 off main @ 063c437)**:

| Commit | Lane | Scope |
|---|---|---|
| `c2efc24` | C | Forward-slash convert binary/workingDirectory paths in _serializeValue (BUG-11) |
| `3a862b7` | A | Hoist discriminant mode into top-level properties in 
ormalizeMcpInputSchema (BUG-13) |
| `e5f92be` | B p1 | New `broker-error.ts`, `mo2-process-state.ts`, `mo2-log.ts` (L1+L2 helpers) |
| `aa3a83c` | B p2 | Wire pipe-client failures through L1 process probe + L2 log tail, throw BrokerEnrichedError |
| `0b22b9b` | B p3 | Forward structured broker errors through dispatch.ts catch branch |
| `9f306e7` | materialize | Mirror to `plugins/bgs-modding-superpowers/tools/mo2-mcp/` |

**Why this batch existed**: e2e Phase 4-final-beta (fixer-beta) baseline of 17 PASS / 9 FAIL / 1 broker_hang / 1 NOT_COVERED surfaced two architectural gaps in addition to the 17 bugs catalogued in `.opencode/artifacts/mo2-mcp/e2e-test-plan/run-20260617T002922Z/BUGS.md`:
- BUG-13: the v1.2-pre `normalizeMcpInputSchema` shape `{type:'object', properties:{}, additionalProperties:true, anyOf:[...]}` was generation-hostile to OpenAI tool-callers, so gpt-5.x agents (fixer-alpha lane) could not emit `mode: 'apply'` against the discriminated-union schema even though Anthropic agents (claude-opus-4-7) handled the same shape correctly. This is the root cause of the earlier BUG-5 "apply unreachable" misframing.
- BUG-16: broker mods.set_active hangs MO2 GUI when a modal dialog blocks the Qt main thread (BUG-11 binary-path mangling is one trigger). Agent's only signal was opaque internal_error: pipe call timeout (<method>), with no way to distinguish modal vs network vs broker crash.

**3-lane parallel dispatch (fixer-beta × 3)**:
- Lane A (BUG-13): ~80 LOC, 7 tests in 
ormalize-mcp-input-schema.test.ts. Hoists shared const/single-num properties from nyOf/oneOf/llOf branches into top-level properties while preserving the original union; gpt-5.x now sees an num anchor for argument decoding.
- Lane B (ENRICHMENT L1+L2 + BrokerEnrichedError): ~350 LOC, 49 tests across 4 new files. pipe-client.ts call() now wraps every failure in BrokerEnrichedError, runs MO2 process Responding probe (L1) and mo2.log tail (L2), classifies the failure into mo2_gui_unresponsive / pipe_call_timeout / pipe_empty_response / pipe_parse_error / roker_error, and attaches structured details that dispatch.ts forwards to the agent envelope.
- Lane C (BUG-11 Layer B): ~50 LOC, 10 tests in configure-executable-path-encoding.test.ts. _serializeValue(key, value) forward-slashes backslashes for PATH_KEYS = {binary, workingDirectory}; arguments and titles preserved verbatim. Recon verified MO2 itself stores inary=D:/awesome-bgs-mod-master/... with forward slashes, so this matches MO2's own dominant convention (no Qt double-backslash escape, no @ByteArray() wrap).

**False positives falsified during pre-dispatch recon**:
- BUG-11 Layer A ("configure_executable schema missing payload fields under mode:apply") — actually correct plan/apply contract; both fixer-alpha and fixer-beta tried apply-direct based on a wrong PLAN.md expectation and got plan_expired_or_unknown. PLAN.md/BUGS.md to be updated; tool implementation is fine.

**Acceptance**:
- `npm test`: **397 passed / 19 skipped / 0 failures** (was 331 passed at v1.2-pre baseline; net +66 tests).
- `npm run build`: clean.
- `scripts/build-portable-plugin.ps1`: 8764 files, 41.69 MB materialized into `plugins/bgs-modding-superpowers/`.
- Real OpenCode→MCP semantic reverify (V1 BUG-13 fix proof via fixer-alpha gpt-5.x dispatch, V2 BUG-11 byte-correct INI write, V3 BUG-16 reproduce sees mo2_gui_unresponsive, V4 L2 log tail attached on broker errors): pending OpenCode session restart to load the new MCP dist.

**Out of scope** (Batch 2 next):
- BUG-1 (mo2_machine_contract static paths), BUG-2 (mo2_profile_ini_get game derivation), BUG-3 (sidecar multibyte profile binding), BUG-6 (NAMESAFE001/PATHSAFE001 rule order), BUG-7 (mo2_session empty-args), BUG-9 (cross-profile guard), BUG-10 (invalid_arguments envelope), BUG-12 (install fixture PATHSAFE001 false-positive), BUG-14 (mo2_toggle_plugin plugins.txt flush), BUG-15 (mo2_remove_mod backup_first:false orphan row).

**Deferred to v1.3**:
- ENRICHMENT L3 (broker-side Windows API modal dialog probe). Revisit if telemetry shows >5 BUG-16-class hangs per 100 batch calls in real workloads — L1+L2 should already catch most cases at the client side.

**Carried over from v1.2-pre (unchanged)**:
- TOCTOU file-level advisory locks (LockFileEx / lock)
- Directory lease full-file (relative_path,size,mtime_ms) digest
- detectMo2Running shared-memory probe completion

## 2026-06-17 ## MO2 MCP v1.2 batch1 Anthropic regression hotfix + V1 empirical verify

**Hotfix landed (2 commits on eat/mo2-mcp-v1.2-batch1)**: 
- `810f2e6` drop top-level anyOf/oneOf/allOf in normalizeMcpInputSchema (Anthropic regression hotfix)
- `9eff5f7` rematerialize after the hotfix

**Why this hotfix existed**: the original Lane A (BUG-13) fix at `3a862b7` hoisted discriminant fields into top-level `properties` (correct for OpenAI tool-callers) but ALSO preserved the original `anyOf` keyword at the top level on the rationalization that "branch-by-branch validators keep working". There are no branch-by-branch validators in this repo: the real per-branch validator is Zod `safeParse` in `dispatch.ts`, NOT the wire schema. Anthropic's tool-use API rejects top-level union keywords with `"input_schema does not support oneOf, allOf, or anyOf at the top level"`, crashing the entire MCP for any Anthropic-backed OpenCode session. The hotfix drops the union keyword entirely and merges branch properties at top level for LLM visibility. Codified into AGENTS.md "MCP inputSchema Anthropic Compatibility (2026-06-17)" as a permanent constraint.

**V1 empirical verify (PASS)**: fixer-alpha (gpt-5.x family) dispatched for a single plan+apply round-trip on `Mo2Mo2ToggleMod_tool` against harness mod `OpenCodeDevArtifacts`. fixer-alpha generated `mode: "apply"` correctly through the new hoisted-discriminant schema; modlist.txt SHA256 changed from baseline `9CE63125...` to `CFA3F2D3...`; line 5 mutated from `+OpenCodeDevArtifacts` to `-OpenCodeDevArtifacts`. BUG-13 fix confirmed for OpenAI-tool-calling models in the live OpenCode-MCP wire.

**BUG-16 carryforward (could not reproduce)**: reverse-toggle apply via orchestrator self-test succeeded cleanly. MO2 PID 31736 still Responding, broker state "ok", modlist returned to baseline. L1 + L2 had no broker failure to wrap. Unit tests prove the enrichment code emits `mo2_gui_unresponsive` + `mo2_log_tail` when triggered; empirical end-to-end deferred until a natural broker hang.

**Side discovery (BUG-18)**: L2 looked at `<mo2Root>/logs/mo2.log` but real MO2 writes to `<mo2Root>/logs/mo_interface.log`. Fixed in Batch 2 Lane 2A.

## 2026-06-17 ## MO2 MCP v1.2 Batch 2 shipped

**Delivered (9 commits on eat/mo2-mcp-v1.2-batch1)**:

| Commit | Lane | Scope |
|---|---|---|
| `13bb4fc` | 2E | NAMESAFE001 widened to catch traversal markers + PATHSAFE001 defers name-shaped args (BUG-6) |
| `4ab1f94` | 2A | mo2_machine_contract static path fields + mo2_profile_ini_get game-derivation fallback + mo2-log.ts mo_interface.log fallback (BUG-1, BUG-2, BUG-18) |
| `397b462` | 2D | sidecar UTF-8 stdio encoding for multibyte profile names (BUG-3) |
| `c1a1cbb` | 2D | sidecar accepts legitimate _build/ archive paths in install (BUG-12) |
| `e6034ca` | 2B | mo2_session({}) empty-args introspection (BUG-7) |
| `44fc17c` | 2B | z.string().min(1) on 21 plan/apply tools so empty-string args produce invalid_arguments envelope (BUG-10) |
| `a4040d7` | 2C | cross-profile guard at plan time + unify modlist scrub in remove_mod (BUG-9 + BUG-15) + plugins.txt flush after toggle_plugin (BUG-14) |
| `fe2e1c6` | 2C | BUG-9/14/15 test coverage |
| `0c954d1` | materialize | Mirror to plugins/bgs-modding-superpowers/ |

**5-lane parallel dispatch (mixed fixer-alpha/fixer-beta)**: 5 truly disjoint file scopes, dispatched simultaneously. Cross-lane working-tree contention occurred between Lane 2B (tool schemas) and Lane 2C (mutation tool handlers) which both edited files like `mo2-toggle-mod.ts`; lanes resolved by each staging only their own commit-relevant files via `git add` of specific paths. Final integration: 441 TS pass + 70 sidecar pass + clean build.

**Bugs resolved this batch**:
- BUG-1 mo2_machine_contract missing static paths
- BUG-2 mo2_profile_ini_get game-derivation fallback
- BUG-3 sidecar multibyte profile mojibake (UTF-8 stdio)
- BUG-6 NAMESAFE001 vs PATHSAFE001 misroute
- BUG-7 mo2_session({}) empty args rejected by OpenCode
- BUG-9 cross-profile live mutation guard not firing
- BUG-10 invalid_arguments envelope vs internal_error misroute
- BUG-12 install fixture _build/ false-positive path-traversal
- BUG-14 mo2_toggle_plugin apply doesn't flush plugins.txt
- BUG-15 mo2_remove_mod backup_first:false orphan modlist row
- BUG-18 L2 log path wrong filename

**Out of scope (remaining)**:
- BUG-16 broker hang on mods.set_active — partial root-cause traced (modal dialog blocks Qt thread). v1.2 batch1 BUG-11 fix eliminated one trigger source (binary-path mangling). Empirical L1 + L2 validation pending a naturally-occurring broker hang. L3 (broker-side modal probe) deferred per ENRICHMENT-DESIGN.md.
- BUG-17 fixer-alpha runner-pattern recurrence — process bug, mitigated via small batches + fixer-beta preference for schema-sensitive work.

**Acceptance**:
- `npm test` in `tools/mo2-mcp`: 441 passed / 19 skipped / 0 failures (was 397; net +44 tests from Batch 2 lanes)
- `pytest` in `tools/mo2-mcp-sidecar`: 70 passed (was 64; +6 from BUG-3 stdio encoding tests + BUG-12 archive safety widening tests)
- `npm run build`: clean
- `scripts/build-portable-plugin.ps1`: materialized

**Cumulative state on feat/mo2-mcp-v1.2-batch1** (18 commits since main @ 063c437):
- 14 bug fixes shipped (Batch 1: BUG-11, BUG-13 + Anthropic regression hotfix, ENRICHMENT L1+L2; Batch 2: BUG-1, 2, 3, 6, 7, 9, 10, 12, 14, 15, 18)
- 2 BUGs falsified-by-revisit (BUG-4, BUG-5)
- BUG-LAST resolved via `.mo2-mcp.json` ceiling config
- BUG-16, BUG-17 deferred (process bug + needs L3 or empirical trigger)

**Not yet done**:
- Merge `feat/mo2-mcp-v1.2-batch1` to `main` (user call — feature-branch lifecycle is theirs)
- Refresh vendor clone (`git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' pull --ff-only origin main`) — pending main merge
- Per-MO2-instance broker redeploy hash audit (memory/45 rule 9) — pending main merge

## 2026-06-17 ## MO2 MCP v1.2 Batch 3 — fixture lanes + carryforward verify

**Delivered (3 commits on eat/mo2-mcp-v1.2-batch1 since Batch 2)**:

| Commit | Lane | Scope |
|---|---|---|
| `a2dd622` | F1 | zip-slip malicious .zip fixture + 6 sidecar tests in 	est_archive_safety.py (closes C.1.3 carryforward) |
| `f1099b6` | F2 | CEILING001 read-only direction tests + 2 fixture JSONs + config loader tests (closes C.2.1 carryforward) |
| `c4c33ec` | F3 | lease violation harness with 4 acceptance tests (content-hash drift detection — closes C.3.1-4 carryforward; impl found healthy) |

**Plus**: 1 fixer-alpha re-run of 16 harness yellow cases + 1 fixer-beta investigation lane (F4 Unique NPCs reinstall + FOMOD). F4 did NOT commit because it discovered 3 contract bugs in mo2_reinstall_mod before reaching test code; routed to BUGS.md (BUG-22, BUG-23, BUG-24).

**Test counts**:
- `npm test` in `tools/mo2-mcp`: **451 passed** / 19 skipped / 0 failed (+10 from Batch 2: F2 +6, F3 +4)
- `pytest` in `tools/mo2-mcp-sidecar`: **76 passed** (+6 from F1)
- `npm run build`: clean

**Empirical milestones validated this session**:
- **BUG-13 (gpt-5.x can emit mode:apply)**: fixer-alpha (gpt-5.x) successfully drove 8 plan/apply round-trips on Mo2Mo2*_tool (T0.1, B.1.1-7, B.2.3). The Anthropic regression hotfix shape (drop top-level nyOf/oneOf/llOf, hoist discriminant) is OpenAI-tool-callable AND Anthropic-API-acceptable.
- **BUG-14 (toggle_plugin plugins.txt flush)**: confirmed live — plugins.txt SHA256 changed E6CC49... → 62BBC6... and was correctly restored on cleanup.
- **BUG-16 + ENRICHMENT L2 (mo2_log_tail surfaces real MO2 log lines on broker failure)**: fixer-alpha's cleanup re-enable hit pipe_call_timeout and the new envelope surfaced details.mo2_log_tail.lines containing invalid mod index: 20 — the memory/30 rule 10 orphan-row symptom. Prior to this batch, that would have been an opaque timeout. L1+L2 enrichment delivers structured agent context as designed.
- **BUG-18 (L2 log path mo_interface.log fallback)**: confirmed live — the validation above only worked because Lane 2A's 	ools/mo2-mcp/src/mo2-log.ts tries mo_interface.log before mo2.log. The harness only has mo_interface.log.

**6 NEW BUGs discovered this session** (full details in BUGS.md):
- BUG-19 (high): mo2_install sidecar regression — non-FOMOD archives fail with 
ot_a_fomod after Lane 2D BUG-12 fix
- BUG-20 (medium): mo2_create_mod treats bove:"" as a real mod name; should be null/undefined
- BUG-21 (low, cosmetic): cross-profile guard envelope wraps as internal_error instead of cross_profile_live_mutation_blocked (behavior is correct, code is wrong)
- BUG-22 (high): mo2_reinstall_mod path.join mangles absolute installationFile paths (blocks every modpack curator who downloads outside MO2's downloads folder)
- BUG-23 (high): mo2_reinstall_mod apply silently drops omod_choices, would trigger MO2 GUI FOMOD wizard hang via BUG-16 chain
- BUG-24 (medium, design gap): mo2_reinstall_mod plan doesn't surface FOMOD tree like mo2_install does; agents have no way to discover FOMOD structure for reinstall

**FOMOD multi-page coverage status**:
- Multi-page support EXISTS at the sidecar substrate (omod.py iterates oot.pages plural, drives pyfomod wizard via installer.next() per page).
- It's consumed correctly by mo2_install (Pattern A: omod.parse_choices → install.stage_fomod → installation.install_local_archive on staged dir, which has no info.xml).
- **It is NOT wired to mo2_reinstall_mod** (BUG-23 above). Multi-page FOMOD reinstall coverage requires BUG-22 + BUG-23 + BUG-24 fixed first, then can be empirically tested with the Unique NPCs harness mod.

**70-case e2e coverage updated tally**:
- 47/70 verified PASS (38 prior + 9 reverified this session through fixer-alpha)
- 4/70 still yellow pending BUG-19/20/21 fixes (B.3.3, B.3.8, B.5.1, C.4.1 envelope)
- 6/70 WL2 cases yellow (deferred to WL2-bind session)
- 8/70 carryforward fixtures NOW SHIPPED (C.1.3, C.2.1, C.3.1-4, partial B.3.6 via F4)
- 1/70 needs Batch 4 fix-then-test (B.3.6 full reinstall + FOMOD multi-page)
- 2/70 unreachable through OpenCode wire by design (C.5.2, C.5.3)
- 2/70 deferred (B.5.1 PLAN.md correction, FOMOD multi-page apply pending Batch 4)

**Cumulative on feat/mo2-mcp-v1.2-batch1**: 21+ commits since main @ 063c437, 14 Batch 1+2 bugs shipped + 8 carryforward fixtures landed + 6 new bugs documented for Batch 4. 451 TS + 76 sidecar tests pass.

**Out of scope (Batch 4 territory)**:
- BUG-19 through BUG-24 fixes
- PLAN.md formal correction (B.5.1 contract, C.3 spec divergence, C.5.2/3 unreachable-by-design note)
- WL2 yellow re-runs (needs single-instance MO2 swap, separate session)
- mo2_reinstall_mod refactor to Pattern A (shares FOMOD-staging helper with mo2_install)
- End-to-end FOMOD multi-page test using Unique NPCs (pending the refactor)

## 2026-06-17 ## MO2 MCP v1.2 Batch 4 — BUG-19 to BUG-24 shipped + WL2 yellow verified

**Delivered (6 commits on eat/mo2-mcp-v1.2-batch1)**:

| Commit | Lane | Scope |
|---|---|---|
| `1f115d9` | 4A | BUG-19: non-FOMOD install path restored. Root cause was mo2-install.ts truthiness on rgs.fomod_choices (JS treats [] as truthy → routed empty-choices non-FOMOD plans to FOMOD parser). Lane 2D BUG-12 fix was correct; the bug was in TS layer. |
| `228ba36` | 4B | BUG-20: _normalizeAbove() helper in mo2-create-mod.ts treats empty/non-string bove as absent. |
| `166994d` | 4B | BUG-21: CrossProfileMutationError class in profile-guard.ts + dispatch.ts catch branch. Envelope now {code:'cross_profile_live_mutation_blocked', details:{requested, active, hint}}. |
| `554bdab` | 4C | refactor: extracted 	ools/mo2-mcp/src/fomod-helpers.ts shared by mo2_install and mo2_reinstall_mod. |
| `829dd87` | 4C | BUG-22 + BUG-23 + BUG-24: mo2_reinstall_mod wired to Pattern A. path.isAbsolute() check (BUG-22). FOMOD reinstall: extract → sidecar.stage_fomod(choices) → manual replace mod content preserving meta.ini (BUG-23 — skips broker install_local_archive(staged_dir) because broker rejects existing mod names). Plan-time FOMOD tree surfacing via omod_choices_required_for_reinstall error (BUG-24). |
| `604fe29` | materialize | Mirror to `plugins/bgs-modding-superpowers/` |

**5-lane parallel dispatch** (Lane 4A fixer-alpha + Lane 4B fixer-beta + Lane 4C fixer-beta + Lane 4D fixer-alpha WL2 read-only):
- Lane 4A discovered the actual BUG-19 root was in mo2-install.ts, not the assumed rchive.py regression. Lane 2D's BUG-12 sidecar fix was correct; the symptom traced higher up the stack.
- Lane 4C extracted a shared omod-helpers.ts helper. Centralized the 
ot_a_fomod|info.xml contract that was being duplicated with subtly different shapes. mo2_install refactor was 8 lines net (behavior preserved).
- Lane 4D WL2 read-only rerun: WL2 mutation invariant byte-clean (all 3 SHAs match baseline). 3 PASS / 3 FAIL, where 1 FAIL is acceptable (A.3 xedit_target null is correct for WL2 lacking OpenCodeXEdit per Lane 2A spec) and 2 FAILs surface NEW BUG-25 candidate (sidecar asset path normalization for Data/ prefix).

**Acceptance**:
- `npm test` in `tools/mo2-mcp`: **464 passed** / 19 skipped / 0 failed (was 451; net +13 from Batch 4: Lane 4A +3 sidecar via embedded TS tests, Lane 4B +10, Lane 4C +3)
- `pytest` in `tools/mo2-mcp-sidecar`: **79 passed** (was 76; +3 from Lane 4A regression guards)
- `npm run build`: clean
- `scripts/build-portable-plugin.ps1`: materialized into `plugins/bgs-modding-superpowers/`
- WL2 mutation invariant: modlist + plugins + ModOrganizer.ini SHA256 byte-identical to baseline

**Empirically validated this session**:
- BUG-2 (game-derivation fallback): A.8 returned source: profile_local on WL2 (no [General] game= present).
- BUG-3 (sidecar UTF-8 multibyte profile): A.9 returned profile_name: BB84自用 correctly, mod_count: 803.
- WL2 invariant: read-only operations leave WL2 byte-clean.
- Anthropic-compat hotfix: orchestrator's claude-opus-4-7 session loaded post-Batch-3 dist + dispatched 5 parallel Task subagents successfully.

**One new bug discovered**:
- BUG-25 (medium): sidecar asset path normalization. Mo2Mo2AssetsResolve_tool + Mo2Mo2SearchFiles_tool return empty results when query includes Data/ prefix on real WL2 install. Mo2Mo2AssetsSummary_tool works (proves index has content + multibyte profile is correct). Likely sidecar's asset cache stores paths without Data/ prefix while tool layer doesn't strip the input. Investigate mo2_mcp_sidecar/assets.py.

**Cumulative state on feat/mo2-mcp-v1.2-batch1** (28 commits since main @ 063c437):
- 20 bug fixes shipped (Batch 1+2+4 = BUG-1, 2, 3, 6, 7, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 24 + Anthropic regression hotfix)
- 2 BUGs falsified (BUG-4, BUG-5)
- 1 BUG resolved by config (BUG-LAST)
- 8 carryforward fixtures landed (C.1.3, C.2.1, C.3.1-4)
- 1 BUG deferred + validated empirically (BUG-16+L2)
- 1 BUG deferred process-class (BUG-17)
- 1 BUG newly discovered (BUG-25)

**70-case e2e coverage (post-Batch-4, pre-empirical-revalidation)**:
- 47/70 verified PASS (38 prior + 9 reverified in Batch 3 rerun)
- 9 WL2/harness PASS from Batch 3+4 rerun (T0.1, B.1.1-7, B.2.3, A.8, A.9, A.10) — overlap with above
- 6 yellow fixed in Batch 4, needs empirical re-verify after OpenCode restart (B.3.3 BUG-19, B.3.8 BUG-20, C.4.1 BUG-21, plus B.5.1 with corrected contract per PLAN.md CORR-1)
- 4 carryforward fixtures shipped earlier (C.1.3, C.2.1, C.3.1-4 — closed via Batch 3 lanes)
- 1 reinstall+FOMOD test possible (Unique NPCs harness mod ready; awaits OpenCode restart + Batch 4 BUG-22/23/24 fixes loaded)
- 2 unreachable-by-design (C.5.2, C.5.3 — PLAN.md CORR-3)
- 2 yellow BUG-25 candidate (A.11, A.13 sidecar asset paths)

**Status**: feat branch ready for merge to main, vendor clone refresh, and per-MO2-instance broker SHA audit. Per user instruction: STOPPED before merge. PR URL: `https://github.com/BB-84C/bgs-modding-superpowers/pull/new/feat/mo2-mcp-v1.2-batch1`.

**Out of scope (Batch 5 territory if pursued)**:
- BUG-25 (sidecar asset path normalization)
- B.3.6 end-to-end FOMOD apply with Unique NPCs (needs OpenCode restart to load Batch 4 fixes)
- B.3.3, B.3.8, B.5.1, C.4.1 envelope re-verify (same OpenCode restart prerequisite)
- PLAN.md formal PR-shape corrections (currently in .opencode/artifacts/.../PLAN.md which is gitignored; if PLAN.md becomes a PR-deliverable, the CORR-1 through CORR-6 section needs to move into a tracked location)

## 2026-06-17 ## MO2 MCP v1.2 Batch 5 — BUG-25 + BUG-26 shipped + FOMOD apply empirically validated

**Delivered (4 commits on eat/mo2-mcp-v1.2-batch1)**:

| Commit | Lane | Scope |
|---|---|---|
| `d04e818` | 5A | BUG-25a sidecar: _normalize_virtual_path() in assets.py strips leading Data/ for resolve + conflicts. +14 sidecar tests. |
| `ce6d84e` | 5B | BUG-25b TS-side: _stripDataPrefixFromPattern() in mo2-search-files.ts strips leading Data/ from regex (preserving ^ anchor) + glob patterns. +7 TS tests. |
| `ef4db87` | 5C | BUG-26 NEW: FomodChoicesRequiredError typed class + dispatch.ts catch branch. Both mo2_install + mo2_reinstall_mod now preserve fomod_tree in envelope. +4 tests. |
| `1721f5d` | materialize | Mirror to `plugins/bgs-modding-superpowers/` |

**Acceptance**:
- `npm test` in `tools/mo2-mcp`: **475 passed** / 19 skipped / 0 failed (was 464; net +11 from Batch 5: 5B +7, 5C +4)
- `pytest` in `tools/mo2-mcp-sidecar`: **93 passed** (was 79; +14 from Lane 5A)
- `npm run build`: clean
- `scripts/build-portable-plugin.ps1`: materialized into `plugins/bgs-modding-superpowers/`

**Empirical milestone this batch — FOMOD multi-page apply EMPIRICALLY VALIDATED**:

End-to-end test of BUG-22 + BUG-23 + BUG-24 (Batch 4 fixes) on the real-world Nexus FOMOD `Unique NPCs - An Overhaul of the Commonwealth` (6.7 GB archive at `F:/Fallout 4 Mods/MODS/NPC/...`):
- Step 1 plan (no choices) FAILED → exposed BUG-26 (dispatch.ts strips err.fomod_tree from plain Error). **Fixed same batch** `ef4db87`.
- Step 2 choices construction: subagent extracted ModuleConfig.xml directly via 7z (workaround). 6 pages, 19 groups, 51 options.
- Step 3 plan (with valid choices): **PASS**
- Step 4 apply (Pattern A: sidecar.stage_fomod + manual content replacement preserving meta.ini): **PASS in 125 sec**, no broker hang, no MO2 modal dialog popup, no enrichment envelope triggered.
- Step 5 readback: **PASS** — 26 files byte-perfect match against ModuleConfig.xml `Unique NPCs Core.esp` option's `<files>` element. Meshes + Tools dirs CreationTime stamped during apply window.

**Conclusion**: `mo2_reinstall_mod` Pattern A WORKS in production on real-world multi-page FOMODs. The Lane 4C refactor delivered correct end-state without the MO2 GUI FOMOD wizard hang that previously made FOMOD reinstall impossible.

Evidence preserved at `.opencode/artifacts/fomod-test-uniquenpcs/`.

**Side cleanup**: 8 stale staging dirs from prior aborted runs purged from `.artifacts/mo2/.mo2-mcp/staging/`. Best-effort cleanup occasionally fails; periodic prune helper noted for Batch 6.

**Cumulative state on feat/mo2-mcp-v1.2-batch1** (32 commits since main @ 063c437):
- 23 bug fixes shipped (Batch 1+2+4+5 = BUG-1, 2, 3, 6, 7, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 24, 25a, 25b, 26 + Anthropic regression hotfix)
- 2 BUGs falsified (BUG-4, BUG-5)
- 1 BUG resolved by config (BUG-LAST)
- 8 carryforward fixtures landed (C.1.3, C.2.1, C.3.1-4 batteries)
- BUG-16 + L2 enrichment empirically validated
- BUG-22+23 Pattern A FOMOD reinstall empirically validated on 6.7 GB real-world FOMOD
- BUG-17 deferred process-class
- 0 new bugs discovered this session (last new bug BUG-26 found AND fixed in same batch)

**70-case e2e coverage**: **~62/70 verified PASS** (89%). Remaining gaps:
- 2 unreachable-by-design (C.5.2, C.5.3)
- 1 vendor-class limitation (B.5.1 multi-field plan via gpt-5.x — would need fixer-beta or claude for that case)
- ~5 fully-shipped fixture/carryforward cases counted above

**Status**: feat branch READY FOR MERGE. Per user instruction: STOPPED before main merge. PR URL: `https://github.com/BB-84C/bgs-modding-superpowers/pull/new/feat/mo2-mcp-v1.2-batch1`.

**Recommended merge sequence when user is ready**:
1. Review feat branch (32 commits, +6,000-7,000 lines, 23 bug fixes)
2. Fast-forward merge to main OR PR (no rebase needed; clean linear history)
3. Vendor clone refresh: `git -C 'D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers' pull --ff-only origin main`
4. Per-MO2-instance broker SHA audit (memory/45 rule 9) on harness + WL2
5. End-of-cycle OpenCode restart to load merged-main MCP dist

## 2026-06-17 ## MO2 MCP v1.2 → main merge + v1.3 Batch 6 (BUG-27 + Carryforward verify + FOMOD-EXT)

### Stage closeout: v1.2 → main

**Delivered**:
- Deleted stale branch eat/mo2-mcp-e2e-runner (5 commits, 1066 lines, never merged anywhere; was an early stdio-spawn runner approach abandoned in favor of OpenCode→MCP wire + subagent dispatch)
- Fast-forward merged eat/mo2-mcp-v1.2-batch1 → main (35 commits, 9485 insertions, 1598 deletions across 171 files)
- Pushed main to origin
- Refreshed vendor clone at `D:\Starfield MO2\.opencode\vendor\bgs-modding-superpowers` (063c437 → 7bb8389)
- Broker SHA audit (memory/45 rule 9): both harness (.artifacts/mo2) AND WL2 (B:\WastelandBlues 2.0) brokers MATCH source SHA 1CD81E88.... No redeploy needed.
- Deleted merged eat/mo2-mcp-v1.2-batch1 (local + remote)

**Cumulative on main @ 7bb8389**: 23 bug fixes shipped (BUG-1, 2, 3, 6, 7, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 24, 25a, 25b, 26 + Anthropic regression hotfix), 8 carryforward fixtures landed, 2 BUGs falsified, 1 env-resolved, 1 process-class deferred. 475 TS + 93 sidecar tests.

### v1.3 Batch 6 shipped on eat/mo2-mcp-v1.3-bug27-and-fomod

**Delivered (4 commits)**:

| Commit | Lane | Scope |
|---|---|---|
| `c2374ba` | V2 | BUG-27 NEW: _flattenUnionBranches() recursive flatten in 
ormalizeMcpInputSchema + partial-discriminant extraction. Unblocks gpt-5.x multi-field plan calls. +4 TS tests. Anthropic guard preserved. |
| `9814c70` | V3 (Phase 1+2) | FOMOD-EXT sidecar: new omod_deps.py with state-aware valuate_conditions(). parse_choices + esolve_files now consume mo2_state param to evaluate <fileDependency> against plugins.txt, <gameDependency> via LooseVersion. +14 sidecar pytest. |
| `b1d21fd` | V3 (Phase 4) | FOMOD-EXT TS wiring: new mo2-state-for-fomod.ts gathers plugins+mods+gameVersion. mo2-install.ts + mo2-reinstall-mod.ts pass state to sidecar. FomodTreeShape extended with dependencies_status, module_dependencies_status, conditional_pages_note. +9 TS tests. |
| `ce7c3be` | materialize | Mirror to `plugins/bgs-modding-superpowers/` |

**Plus bonus Lane V1 (Carryforward MCP-wire verify)**: C.1.3 zip-slip rejected (path_traversal_blocked), C.3.1 external touch (lease_violation drift), C.3.2 external rewrite (lease_violation drift), C.3.3 one-shot lease (plan_expired_or_unknown on second apply). All 4 PASS via real Mo2Mo2*_tool calls. Cleanup byte-restored harness to baseline.

**Acceptance**:
- `npm test` in `tools/mo2-mcp`: **488 passed** / 19 skipped / 0 failed (was 475; +13)
- `pytest` in `tools/mo2-mcp-sidecar`: **107 passed** (was 93; +14)
- `npm run build`: clean
- `scripts/build-portable-plugin.ps1`: materialized
- 4 Carryforward MCP-wire cases: 4/4 PASS, mutation invariant byte-clean

**Test totals**: 488 TS + 107 sidecar = **595 total tests** across mo2-mcp + sidecar. From 397 at start of Batch 1 to 595 at end of v1.3 = **+198 tests added across the v1.2 → v1.3 arc**.

**Status**: `feat/mo2-mcp-v1.3-bug27-and-fomod` pushed to origin. **STOPPED before v1.3 → main merge** per user instruction implicit ("merge feat前停下来" still standing for v1.3). Awaiting user decision on whether to merge v1.3 → main now or continue iteration.

PR URL: `https://github.com/BB-84C/bgs-modding-superpowers/pull/new/feat/mo2-mcp-v1.3-bug27-and-fomod`

**70-case e2e coverage**: 60/70 MCP-wire verified PASS (85.7%) + 2 expected-PASS-after-OpenCode-restart (B.5.1 with BUG-27 fix loaded; C.2.1 with ceiling-restricted spawn) = 62/70 achievable next session. Final 8 gap: 2 by-design unreachable (C.5.2, C.5.3), 2 BUG-25 candidates (A.11, A.13 — sidecar fix shipped, needs WL2 retest), 2 test-design (B.3.4, B.5.2), 2 carryover.

## 2026-06-17 ## Post-v1.3-merge empirical milestones (4 verified)

After v1.3 → main merge + vendor sync + broker SHA audit (both MO2 instances MATCH src \1CD81E88...\) + OpenCode restart, orchestrator ran 4 empirical milestone verifications. All 4 PASS via real OpenCode→MCP wire.

### A.11 — BUG-25a empirically validated on real WL2 (803 enabled mods)

\Mo2Mo2AssetsResolve_tool({profile:'BB84自用', virtual_path:'Data/textures/BNS/Landscape/Grass/FernGrass01_d.DDS'})\ returned:
- \winner.owner_mod: "LODGen 覆盖素材"\
- \ucket: "loose-overwrites-archive"\
- \providers: ["波士顿自然风景 - 本体", "LODGen 覆盖素材"]\

Pre-fix (Lane 4D 2026-06-17 first WL2 verification): \{winner:null, providers:[]}\. Sidecar \_normalize_virtual_path()\ in \ssets.py\ (Lane 5A commit \d04e818\) confirmed live on real-world WL2.

### A.13 — BUG-25b empirically validated on real WL2

\Mo2Mo2SearchFiles_tool({profile:'BB84自用', pattern:'regex:^Data/textures/.*\\.dds$', max_results:5})\ returned 5 real DDS matches (\BB84补丁/textures/Actors/Character/BaseHumanFemale/*.dds\) with \	runcated:true\ (more available). Pre-fix: \{results:[], count:0}\. TS-side \_stripDataPrefixFromPattern()\ (Lane 5B commit \ce6d84e\) confirmed live.

### C.2.1 — Read-only ceiling all 3 tiers verified via MCP wire

Orchestrator-side ceiling swap: backup \.mo2-mcp.json\, write \{"permission_ceiling":"read-only"}\, unbind, bind. Then per-tier test:

| Tier | Tool | Outcome at read-only |
|---|---|---|
| T1 | \Mo2Mo2Modlist_tool\ | ✅ ALLOWED (19-mod list returned) |
| T2 | \Mo2Mo2SetModNotes_tool\ plan | ✅ BLOCKED \CEILING001 requires metadata-editable, current read-only\ |
| T3 | \Mo2Mo2ToggleMod_tool\ plan | ✅ BLOCKED \CEILING001 requires full-control, current read-only\ |

\Mo2Mo2Status\ reported \permission_ceiling: "read-only"\ after rebind, confirming config re-read on bind. Restored full-control, rebind succeeded with full-control. This proves Lane F2 ceiling fixture (\1099b6\) contract holds through the actual MCP wire, not just unit-test layer.

### B.5.1 — BUG-27 fix EMPIRICALLY VALIDATED + BUG-11 Layer B re-confirmed

Two-step verification:

**Step A** (fixer-alpha dispatch): gpt-5.x successfully emitted the multi-field plan args:
\\\json
{
  "mode": "plan",
  "action": "add",
  "entry": {"title": "E2E-BUG27-Notepad", "binary": "C:\\\\Windows\\\\System32\\\\notepad.exe", ...}
}
\\\

This was impossible pre-BUG-27 because nested \z.discriminatedUnion("action", [...])\ inside outer \z.union([planSchema, applyShape])\ produced \{anyOf:[{oneOf:[...]}, applyShape]}\ — old \
ormalizeMcpInputSchema\ saw the inner \oneOf\ as a property-less branch and dropped its variants' fields. BUG-27 fix (\c2374ba\) recursively flattens nested unions before discriminant extraction + merge. **gpt-5.x can now see the inner branch fields.** Empirical proof: actual tool-call args emitted by fixer-alpha contained \ction:"add"\ + \ntry:{...full nested object...}\.

**Step B** (orchestrator round-trip with MO2 closed): plan succeeded, apply succeeded (\xecutables_count: 8 → 9\), raw \ModOrganizer.ini\ readback:

\\\ini
9\\arguments=
9\\binary=C:/Windows/System32/notepad.exe        ← FORWARD-SLASH (BUG-11 Layer B confirmed live)
9\\hide=false
9\\ownicon=false
9\\steamAppID=
9\\title=E2E-BUG27-Notepad
9\\workingDirectory=C:/Windows/System32          ← FORWARD-SLASH
\\\

BUG-11 Layer B forward-slash conversion (\_serializeValue\ PATH_KEYS handling, Lane C commit \c2efc24\) **re-confirmed live** on real INI write. Cleanup remove plan+apply returned \xecutables_count: 9 → 8\, zero E2E-BUG27 lingering, harness modlist + plugins SHA byte-invariant.

### Mutation invariants final

- WL2: modlist + plugins + ModOrganizer.ini SHA all 3 byte-match baseline post-A.11/A.13 test
- Harness: modlist + plugins SHA byte-match baseline post-C.2.1 + B.5.1 test (only ModOrganizer.ini mutated then byte-cleaned via remove apply)
- \.mo2-mcp.json\ restored to full-control post-C.2.1

### 70-case e2e final tally

| Status | Count |
|---|---|
| ✅ Verified PASS via MCP wire | **64/70 (91.4%)** |
| ❌ Unreachable-by-design (C.5.2, C.5.3) | 2 |
| ⏸ Test-design/sequencing | 4 |

**64/68 reachable cases = 94.1%**. Remaining 4 are test-design issues (B.5.2 needs run_tool round-trip with lifecycle juggling; B.3.4 needs valid FOMOD choices via post-BUG-26 fomod_tree introspection; 2 marginal).

### Test suite progression

| Time | TS | Sidecar | Total |
|---|---|---|---|
| Batch 1 起点 | 331 | 64 | 395 |
| v1.3 closeout | 488 | 107 | **595** |
| Net delta across v1.2 → v1.3 arc | +157 | +43 | **+200 tests** |

### Bug roster final

- 23 bugs shipped on main + 1 (BUG-27) in v1.3 + Anthropic regression hotfix = 25 fixes
- 2 falsified (BUG-4, BUG-5)
- 1 env-resolved (BUG-LAST)
- 1 empirically validated as designed (BUG-16 + L2 enrichment)
- 1 deferred process-class (BUG-17 mitigated)
- **0 open bugs on main**

main HEAD at \53ecd08\; 39 commits since main@\ 63c437\ Batch-1 baseline.

## 2026-06-17 ## B.3.4 + B.5.2 EMPIRICALLY VALIDATED — 66/70 (94.3%) achieved

After OpenCode restart (v1.3 dist live), orchestrator executed both remaining high-priority test-design cases per BATCH7-B52-B34-TEST-DESIGN.md. Both PASS via real OpenCode→MCP wire.

### B.3.4 — \mo2_install\ with valid FOMOD choices (BUG-26 fix end-to-end validated)

Procedure (12 steps, 5 phase). Sequence:

**Phase 1 probe**: \Mo2Mo2Install_tool\ plan with \omod_choices:[]\ on \	est-fomod.7z\ fixture → response envelope contained the full \omod_tree\ structure as designed:

\\\json
{
  "code": "fomod_choices_required",
  "details": {
    "fomod_tree": {
      "fomod_name": "E2EFomod",
      "fomod_version": "1.0",
      "conditional_pages_note": null,
      "pages": [{
        "name": "Install",
        "groups": [{
          "name": "Main",
          "type": "SelectExactlyOne",
          "options": [{"name": "Default", "type": "Recommended", "dependencies_status": {"met": true, "missing": []}}]
        }],
        "dependencies_status": {"met": true, "missing": []}
      }],
      "module_dependencies_status": {"met": true, "missing": []}
    }
  }
}
\\\

**BUG-26 fix (typed FomodChoicesRequiredError) + FOMOD-EXT dependency_status fields validated live**.

**Phase 2 construct**: parse tree → 1 page, 1 SelectExactlyOne group "Main", 1 option "Default". Choice: \[{"page_name":"Install","selected_options":[{"group_name":"Main","option_name":"Default"}]}]\.

**Phase 3 plan+apply**: plan succeeded with valid choices → apply via sidecar Pattern A → \{ok:true, mod_name:"E2E-B34-Fomod", fomod_used:true, dest_path:".../mods/E2E-B34-Fomod"}\.

**Phase 4 readback**: mod dir created with 2 files (\meta.ini\ + \	extures/e2e/fomod-default.txt\ — the "Default" option's payload). \Mo2Mo2ModInfo_tool\ returned correct metadata.

**Phase 5 cleanup**: \Mo2Mo2RemoveMod_tool\ with \ackup_first:false\ cleanly removed mod dir + modlist rows. \profiles_updated:["Default"]\. plugins.txt + ModOrganizer.ini SHA byte-clean. modlist SHA temporarily differed from baseline post-cleanup (BUG-28 below) but **self-normalized on next MO2 launch**.

#### BUG-28 (NEW, discovered during B.3.4) — \mo2_install\ creates dual modlist rows

\mo2_install\ with \	arget_priority:"bottom"\ writes the mod entry to modlist.txt **twice**: once at line 2 (top, disabled \-E2E-B34-Fomod\) AND at the last line (bottom, enabled \+E2E-B34-Fomod\). Only the bottom row reflects the requested target_priority; the top row appears to be a placeholder from \createMod\ → \send_mod_to\ sequence where the initial position isn't cleaned up. \Mo2Mo2RemoveMod_tool\ correctly removes BOTH rows (so no orphan after cleanup) and modlist.txt byte-invariant self-heals on next MO2 launch. **Severity: low** — functional install works, cleanup works, only cosmetic during the mod's lifetime. Investigate \	ools/mo2-mcp/src/tools/mo2-install.ts\ applyMutation for redundant write. Tracked as housekeeping debt for v1.4.

### B.5.2 — \mo2_run_tool\ after \configure_executable\ add (lifecycle juggle, run_tool dispatch validated)

Procedure (14 steps, 3 phase). Sequence:

**Phase 1 offline configure add**: MO2 stopped → \configure_executable\ plan+apply (\ction:add, entry:{title:"E2E-B52-Notepad", binary:"C:\\Windows\\System32\\notepad.exe", ...}\) → \xecutables_count: 8 → 9\. ModOrganizer.ini readback: \9\binary=C:/Windows/System32/notepad.exe\ + \9\workingDirectory=C:/Windows/System32\ (forward-slash per BUG-11 Layer B).

**Phase 2 online run_tool**: MO2 restart (boots with new INI entry) → mo2-mcp rebind (broker reconnected, \pipeConnected:true\) → \Mo2Mo2ListExecutables_tool\ confirmed E2E-B52-Notepad registered → pre-launch notepad count: 0 → \Mo2Mo2RunTool_tool\ plan+apply with title="E2E-B52-Notepad" → \{ok:true, result:{handle:6088, waiting:false}}\ → **notepad.exe PID 60292 spawned** (StartTime 21:17:50, Path \C:\\Windows\\System32\\notepad.exe\). Killed cleanly via Stop-Process.

**Phase 3 offline configure remove**: MO2 stopped → \configure_executable\ remove plan+apply → \xecutables_count: 9 → 8\. 0 E2E-B52 occurrences in INI.

**Final invariant**: modlist + plugins SHA byte-match baseline (\CA4CD4F4...\ + \E6CC4983...\). ModOrganizer.ini differs from pre-test (Qt renumbering, semantically clean: 0 E2E entries, executables_count restored).

End-to-end pipeline validated: configure_executable → MO2 boot → mo2_run_tool → broker organizer.start_application → real process spawn → cleanup.

### Side observation — stale BUG-11 era entry

\Mo2Mo2ListExecutables_tool\ returned a stale entry from Batch 1 era (pre-BUG-11 fix): \E2E-Test-Exe-1781663606679\ with corrupted \inary:"C:indowsystem32/notepad.exe"\ + \workingDirectory:"C:indowsystem32"\. The entry has been sitting in ModOrganizer.ini since the first BUG-11 reproduction (timestamp suggests early June 2026 = 1781663606679 ms epoch). Harmless (would fail to launch with FILE_NOT_FOUND but wouldn't BUG-16 hang because no agent ever tried to run it). Housekeeping debt — could be removed via \Mo2Mo2ConfigureExecutable_tool\ remove. Not done this session to keep state changes minimal.

### Final 70-case e2e tally

| Status | Count |
|---|---|
| ✅ **Verified PASS via MCP wire** | **66/70 (94.3%)** |
| ❌ Unreachable through OpenCode wire by design | 2 (C.5.2, C.5.3) |
| ⏸ Test-design / sequencing — 2 marginal cases | 2 (Bx.x — non-load-bearing variants) |

**66/68 reachable cases = 97.1%**. Remaining 2 marginal are non-load-bearing test variants, not gaps in mo2-mcp coverage.

### Test suite final state

| Surface | Pass | Skipped |
|---|---|---|
| \	ools/mo2-mcp\ (vitest) | 488 | 19 |
| \	ools/mo2-mcp-sidecar\ (pytest) | 107 | 0 |
| **Total** | **595** | 19 |

### Bug roster final v1.3

- 24 bugs fixed and shipped on main (BUG-1, 2, 3, 6, 7, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 24, 25a, 25b, 26, 27 + Anthropic regression hotfix)
- 1 NEW BUG-28 discovered + documented (mo2_install dual modlist row) — low severity, self-healing on MO2 launch, deferred to v1.4
- 2 falsified by revisit (BUG-4, BUG-5)
- 1 env-resolved (BUG-LAST)
- 1 deferred process-class (BUG-17)
- Empirical milestones validated: BUG-13, BUG-14, BUG-16+L2, BUG-22+23 (Pattern A FOMOD on 6.7 GB real), BUG-26 (fomod_tree surfacing), BUG-11 Layer B, BUG-27 (gpt-5.x multi-field), BUG-25a/b

### v1.2 → v1.3 arc summary

Started Batch 1 at main@\ 63c437\ with 395 tests. Ended at main@\<this commit>\ with 595 tests (+200). Closeout: **24 bugs fixed shipped on main, 0 critical open, 1 low-severity housekeeping-debt (BUG-28) deferred**. 66/70 e2e cases verified PASS via real OpenCode→MCP wire. mo2-mcp v1.3 is the stable mainline for downstream BGS modding workflows.

---

## 2026-06-18 ## r6 alignment + #8 consent forwarding + post-r6 wire-verification cascade

### What this round delivered

End-to-end alignment of xedit-mcp + bgs-kb-mcp to TES5Edit-contrib `v4.1.6-automation.r6` (contract `0.20`), plus the wave of follow-up fixes surfaced by real-daemon semantic acceptance.

**16 commits on `main` since `0202943`:**

```
ed74f92 docs(release-notes): surface 4 post-r6 wire-verification fixes
5c370e0 build (wrapper schema realign + glossary skip)
4bbb562 fix: align create_child_record schema with KB + daemon; skip glossary packs in bgs_kb_query
0663322 build (create_child_record parent shape fix)
f6b35b9 fix(xedit-mcp): translate parent spec keys to daemon shape (superseded by 4bbb562)
8dd0214 build (consentEnabled nested path fix)
25b2e18 fix(xedit-mcp): read consentEnabled from nested r6 supports paths
d085c97 build (#8 consent forwarding)
a88378d feat(xedit-mcp): forward iKnowWhatImDoing through launch chain (#8)
96aab51 build (find-records-by-pattern fix)
b5bc71e fix(xedit-mcp): wrap singular file arg to files[] (B2 bug)
71ba083 build (r6 alignment closeout)
83aef9f feat(xedit-mcp): 4 r6 intent tools (#5)
fe21e62 feat(kb): 8 r6 capability records + contract-version-field-presence refresh (#4)
e8df916 feat(skills): r6 progressive-disclosure + dead-link fix (#3, #6)
627d526 feat(xedit-mcp): bump capabilities-digest to 0.20 (#2)
d3af959 docs: README intent-tool count + RELEASE-NOTES r6 alignment (#7)
```

### Issues closed (8 of 9 filed during round)

- #2 capabilities-digest 0.20 (wire-PASS via Phase A handshake)
- #3 skill r6 progressive disclosure (content-only)
- #4 8 KB records + contract-version refresh (122 records validate clean)
- #5 4 intent tool wrappers (3 wire-PASS + 1 fast-fail wire-PASS, + bonus full wrapper success-path wire-verified after schema realignment)
- #6 xedit-knowledgebase.md dead-link removed
- #7 README + RELEASE-NOTES r6 alignment
- #8 consent flag forwarding — full E2E: MCP arg → PS args → xEdit argv `-IKnowWhatImDoing` → `supports.elementsMutation.iKnowWhatImDoing: true` → `xedit_session.consentEnabled: true` → real mutating call → record persisted to disk
- #9 was self-filed during verification then resolved: turned out the KB record was already correct; the wrapper schema was the misaligned side. Closed with `4bbb562` aligning wrapper to KB + daemon (`parent: { file, formId, subGroup?, coords? }`).

### Empirical bugs caught only by real-daemon wire E2E

All four were invisible to mock-tier unit tests and only surfaced during end-to-end verification against the FO4Edit 4.1.6r6 daemon:

1. **B2** `xedit_find_records_by_pattern` — wrapper schema accepted `file: string` but daemon's `records.apply_filter` requires `files: string[]`. Wrapper never wrapped → every call failed with `invalid_request: 'files' must contain at least one plugin name`. Fixed by `wrapFileAsFiles()` translator + regression test asserting `forwarded.files === [file]`. (commit `b5bc71e`)
2. **Hidden consent path** — `buildContext` in `session.ts` was reading `supports.iKnowWhatImDoing` at top level. r6 daemon nests it under `supports.elementsMutation.iKnowWhatImDoing` and `supports.scripts.execution.iKnowWhatImDoing`. Result: `consentEnabled` always returned `false` even with the flag set. Caught the moment #8 forwarding actually let the flag through end-to-end. Fixed to read nested-only paths with regression guard against re-introducing top-level lookup. (commit `25b2e18`)
3. **`xedit_create_child_record` wrapper schema** — used `parent: { parentFile, parentFormId, ... }` but both the daemon AND the KB record use `parent: { file, formId, ... }`. Wrapper never reached a successful daemon call. Realigned schema to match daemon + KB, transparent 0x-prefix strip is the only translation now. (commits `f6b35b9` → superseded by `4bbb562`)
4. **`bgs_kb_query` cross-pack abort** — glossary-schema pack `bgs-l10n-starfield-zhhans` lacks `records` / `records_fts` tables, so the cross-pack FTS UNION threw `no such table: records_fts` and aborted the entire query. Workaround was `packIds` filter. Real fix: wrap each per-pack query in try/catch, skip on `no such table: records(_fts)`, surface skipped packs in `stats.skippedPacks` so the agent can see why they were excluded. (commit `4bbb562`)

### What was previously assumed and now is known

- `system.describe` ok-envelope from xEdit and "consent flag present in spawned xEdit's CommandLine" do NOT imply daemon-reported `consentEnabled: true`. The MCP's session projection layer was a separate failure point.
- Static evidence (compile passes, dist files have new symbols, vendor clones byte-identical) is decisively NOT semantic proof. Three full OpenCode restarts this round each peeled back a deeper layer of cascading bugs that mock + symbol-grep verification had concealed.
- `xedit_call records.create` has at least three field-name traps the daemon doesn't catch in the error message helpfully: top-level `targetFile` (not `file`), `parent.file` (not `parentFile`), and CELL/WRLD parent must already exist in `targetFile` (use `records.copy_into` first to create an override).
- Canonical bootstrap is **bare** `ModOrganizer.exe -p Default` (no `run -e`). MO2's Mo2AgentControl plugin writes `runtime/status.json` on plugin load. `OpenCode xEdit Automation Serve` customExecutable redundantly spawns a second xEdit that the daemon ignores — wastes a process per session. Documented in `.opencode/artifacts/r6-build/VERIFICATION-REPORT.md` for the next session loop.

### What downstream work should do differently

- New r6 capability records belong to `bgs-kb-core 2026.06.13`, now published as part of GitHub release `kb-2026.06.13`. Independent `bgs_kb_install_pack({packId:'bgs-kb-core', version:'2026.06.13'})` users can finally pick them up; bundled-plugin-tree users had them from `0202943..ed74f92`.
- Any future intent-tool wrapper for an r6+ verb MUST wire-test the success path against the live daemon BEFORE the issue ships, not just the schema sweep + fast-fail gate. The four cascade bugs this round each looked clean at static-evidence layer.
- bgs-kb-mcp's `bgs_kb_query` now reports `stats.skippedPacks`; downstream skills should surface that field when explaining narrow result sets to the agent.
- xEdit binaries built before a r6+ release tag don't recognize r6 flags. Always rebuild + sync the harness `Tools/OpenCodeXEdit/xEdit.exe` after pulling the contrib repo.

### KB release published

GitHub release `kb-2026.06.13` published at `https://github.com/BB-84C/bgs-modding-superpowers/releases/tag/kb-2026.06.13`:

- `bgs-kb-core 2026.06.13` (287 KB) — 8 new r6 records + contract-version-field-presence refresh, 122 records validate-clean
- 5 other packs unchanged from kb-2026.06.12 (re-attached at same versions/sha256 so `bgs_kb_install_pack` resolves them under the new tag)
- `manifest-index.json` updated, `bgs_kb_check_updates` now reports `bgs-kb-core latestVersion: 2026.06.13`

### Test suite progression

- xedit-mcp: 87 → 110 → 112 → 114 (+27 across the arc, including 4 regression guards for the cascade bugs)
- bgs-kb-mcp: 126 (unchanged in count; glossary-skip code path covered by existing fixture-pack iteration)
- 0 GitHub issues open after `kb-2026.06.13` publish

### Durability evidence on disk

Three test ESPs left in `.artifacts/mo2/overwrite/` as semantic-acceptance audit trail:
- `OpenCodeR6Test.esp` (183 B) — first Phase C step 2 attempt, contains WEAP 66000001
- `OpenCodeR6Wire.esp` (529 B) — second attempt with CELL override + passthrough REFR child
- `OpenCodeR6Final.esp` (526 B) — final wrapper-wire-test PASS, REFR 66000001 created via `xedit_create_child_record` intent tool with the realigned schema

All three TES4 + signatures verified via raw byte readback. Bundled tree byte-sync to vendor confirmed at every push.

---

## 2026-06-19 ## Two agent-native CLI tools: bgs-archive (BA2/BSA) + bgs-papyrus (Papyrus compile/decompile)

### What this round delivered

Branch `feat/archive-papyrus-cli-tools` (35 commits): two standalone agent-native CLI tools — **CLI + skills, no MCP** — built subagent-driven with multi-commit/push, grounded in 3-lens web recon + exact upstream API extraction, with binding semantic E2E acceptance.

- **bgs-archive** (`tools/bgs-archive/`, Rust on `ba2` v3.0.1 / 0BSD): unpack/pack BA2/BSA across Oblivion/FO3-NV/Skyrim LE-SE/AE/FO4(+NextGen v7/v8)/FO76/Starfield(v2/v3). Subcommands info/list/extract/pack/capabilities, JSON envelopes. Auto-detect via `ba2::guess_format`. Source in-tree; binary intended for GitHub Release (not committed).
- **bgs-papyrus** (`tools/bgs-papyrus/`, Python): detect + drive the user-installed official CK `PapyrusCompiler.exe` (compile) + Champollion + CK-grounded Starfield Guard post-processor (decompile), for Skyrim/FO4/Starfield. Subcommands detect-toolchain/compile/decompile/capabilities.
- Both materialized into `plugins/bgs-modding-superpowers/tools/` + `using-bgs-archive` / `using-bgs-papyrus` skills + bootstrap-table rows. README + (papyrus) bilingual USER-GUIDE.

### Binding semantic acceptance (real, not green-test theatre)

- **bgs-archive**: real FO4 BA2 (`ccbgsfo4008-pipgrn`, auto-detect fo4 v1 GNRL Zip, 30 entries) + real Skyrim BSA (auto-detect tes4 v105 lz4) — structural-validity (format magic + size) + self-consistency SHA256 round-trip PASS. Tool-free (no external oracle: BSArchPro is GUI-only and hangs bash; no CLI archive oracle exists on this machine).
- **bgs-papyrus COMPILE**: real Starfield CK 4.7.0.5 compiled the Chronomark scripts via our wrapper — both `.pex` produced byte-identical-SIZE to the original CK output (3624/886).
- **bgs-papyrus DECOMPILE + Guard**: Chronomark decompile round-trip (symbol-match, our recompiled pex decompiles to same normalized source as original). Starfield Guard syntax **empirically observed** from real CK-authored vanilla scripts and recompile-validated: Champollion `Guard…EndGuard` → official `LockGuard…EndLockGuard`; `TryGuard…EndGuard` → `TryLockGuard…EndTryLockGuard`.

### What is now known

- BA2/BSA version matrix (BSA v103/104/105; BA2 v1/v2/v3/v7/v8; FO4 NG bump is structurally-inert version-only; Starfield v3 uses LZ4 *block* not SSE's frame).
- Starfield CK compiler lives at `<root>\Tools\Papyrus Compiler\PapyrusCompiler.exe` (the `Tools\` segment differs from Skyrim/FO4's bare `Papyrus Compiler\`). Flags: `Starfield_Papyrus_Flags.flg`.
- The official CK PapyrusCompiler runs headless via subprocess (no GUI) and supports batch (`-all`) — pyro-proven; our wrapper drives it cleanly.
- Caprica/Champollion ARE stale (2023-24) and Champollion's Starfield Guard syntax is GUESSED/wrong; the real official syntax was recovered empirically from CK-authored vanilla sources.
- KNOWN LIMITATION: Champollion v1.3.2 has an *unrelated* decompile bug (remote-event casts) that can prevent some complex vanilla scripts from recompiling — documented honestly; our Guard post-processor is validated, this is upstream Champollion.
- `ba2` Rust crate is the only library with write + full Starfield/FO4-NG coverage + permissive (0BSD) license.

### What later phases should do differently / open items

- **bgs-archive binary needs a GitHub Release publish** (`bgs-archive-vX.Y.Z`, per-platform) so end-users get a binary without a Rust toolchain; currently source-in-tree + `cargo build`.
- DX10/GNMF pack deferred (Task A-DX10) — gated on resolving `fo4::DX10Header` field layout.
- Large-compressed-entry decompression validated only via upstream `ba2`; the tiny real fixtures are uncompressed — a bigger compressed BA2 fixture would strengthen this.
- Champollion remote-event-cast decompile limitation is a candidate for a future post-processor rule or an upstream Champollion fork.
- Oracle review (2 rounds) caught + drove fixes: JSON error envelopes, archive path-traversal sanitization, in-tool game-Data write guard (`--allow-game-data`), tes4 nested-path split, compile/decompile fresh-output checks, starfield_syntax unmodeled-construct honesty, and acceptance-doc honesty. All 7 resolved.
- Branch pending merge decision; not yet merged to main / vendor-refreshed.

### Test state
- bgs-archive: cargo test green (incl path-traversal, game-data-refusal, tes4-nested round-trip, real-archive `#[ignore]` acceptance).
- bgs-papyrus: 36 non-e2e pytest green + 3 e2e (real CK compile/decompile) passing with evidence under `.opencode/artifacts/archive-papyrus-tools/acceptance/`.

### 2026-06-19 addendum — coverage gaps Q1/Q2 closed (pre-merge)

- **Q2 real Starfield BA2**: v2 GNRL (`Constellation - Localization.ba2`, 27 entries) + v3 DX10/LZ4 (`Starfield - LODTextures02.ba2`, 658 entries). FOUND + FIXED a real bug — v3 LZ4-block texture extraction failed with `DecompressionFailed`; added an LZ4 decompression path before FO4/DX10 file write (commit `ba0c68d`, `lzzzz` direct dep). 658/658 `.dds` extract with valid `DDS ` magic. The prior "compressed-entry decompression unproven" open item is now CLOSED. (Note: `SFBGS006 - Textures.ba2` turned out to be v2/Zip; the real v3/LZ4 fixture is `Starfield - LODTextures02.ba2`.)
- **Q1 FO4 compile**: FO4 CK `PapyrusCompiler 2.8.0.4` (at `B:\SteamLibrary\steamapps\common\Fallout 4\Papyrus Compiler\`, found via `libraryfolders.vdf` scan — a second Steam library on B:) compiled `BoSResQuestScript.psc` → valid FO4 `.pex` (magic `0xFA57C0DE`, ver 3.9, gameId 2) via our wrapper (commit `bf7bd85`).
- **Q1 FO4/Skyrim decompile**: Champollion via our tool → `WeaponLLInject` (FO4) + `MMX452_Sofia_MarkerOnOff` (Skyrim) valid `.psc` with ScriptName.
- **Remaining honest gap**: Skyrim COMPILE not E2E-verified (Skyrim CK not installed on this machine). Identical wrapper/code path proven on Starfield + FO4; blocked only by the missing CK, not a tool defect.

### 2026-06-19 — landed: merged to main + bgs-archive released
- Feature branch `feat/archive-papyrus-cli-tools` merged to `main` (`9cafedd`, --no-ff) and deleted; vendor clone refreshed to `9cafedd`.
- `bgs-archive v0.1.0` published: https://github.com/BB-84C/bgs-modding-superpowers/releases/tag/bgs-archive-v0.1.0 (asset `bgs-archive-windows-x64.exe`, sha256 `73C985D000D1E3...`). Closes the "binary needs a Release" open item. Other platforms build from source.
- Coverage final: archive read all families + real Starfield v2/v3 (LZ4 bug fixed); Papyrus compile Starfield+FO4 via real CK, decompile Starfield/FO4/Skyrim. Only Skyrim *compile* unverified (no Skyrim CK on machine).
