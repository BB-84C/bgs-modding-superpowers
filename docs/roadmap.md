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
| repository/standards | Foundation in place | `README.md` and `docs/standards/repo-hygiene.md` define scope and durable repo rules. |
| OpenCode packaging | Deferred | `.opencode/README.md` and `.opencode/INSTALL.md` intentionally wait on confirmed plugin metadata and packaging format. |
| repo-bootstrap agent | Foundation in place | `agents/repo-bootstrap/AGENT.md` covers scaffold maintenance and repository bootstrap responsibilities. |
| mod evaluator | Scaffolded | `skills/mod-evaluator/SKILL.md` exists, but no production evaluator workflow is wired yet. |
| install planner | Scaffolded | `skills/install-planner/SKILL.md` defines intent, pending real execution support. |
| conflict auditor | Next target | `skills/conflict-auditor/SKILL.md` is the recommended first real workflow. |
| archive/loose-file reasoning helpers | Planned | Needed to explain archive precedence, loose-file wins, and overwrite outcomes during install review. |
| diagnostics / crash-triage support | Planned | Should organize logs, crash indicators, and reproducible symptom framing before deeper workflow advice. |
| benchmark or smoke-test harness | Planned | Direction only for now; later phases should add fast validation passes for install batches and release baselines. |
| localization assistant | Scaffolded | `skills/localization-assistant/SKILL.md` frames localization support for later workflow expansion. |
| test session guide | Scaffolded | `skills/test-session-guide/SKILL.md` defines test-session outputs but not yet automated orchestration. |
| modpack dev log workflow | Scaffolded | `skills/write-dev-log/SKILL.md` plus `templates/modpack/dev-log-template.md` and `templates/modpack/dev-log-index-template.md` are ready as durable workflow assets. |
| release changelog workflow | Scaffolded | `skills/write-release-changelog/SKILL.md` plus `templates/modpack/release-changelog-template.md` are present. |
| xedit-cli | Specified | `tools/xedit-cli/README.md` and `tools/xedit-cli/CONTRACT.md` define a read-only-first wrapper contract. |
| MCP integrations | Specified | `mcps/xedit-readonly.md`, `mcps/nexus-metadata.md`, `mcps/loot-metadata.md`, and `mcps/translation-memory.md` hold planned integration contracts. |
| knowledge base/research distillation | Foundation in place | The repo layout reserves `knowledge/` for promoted guidance and `research/summaries/` for source-derived findings, including future game-specific risk notes, mod-quality heuristics, and localization glossary strategy. |
| safety hooks | Foundation in place | `hooks/runtime-compatibility.md`, `hooks/repo-cleanliness.md`, `hooks/scope-guard.md`, and `hooks/dev-log-reminder.md` provide baseline safety checks. |
| save-safety automation | Explicitly deferred | The design calls for it later, but no real save-safety automation should ship until a real curator loop exists. |

## Phase Ladder

1. Phase 0 bootstrap foundation: repository layout, standards, scaffold docs, hook specs, skill shells, templates, contracts, and bootstrap verification.
2. Phase 1 read-only xEdit conflict inspection vertical slice: deliver the first real workflow through `conflict-auditor` backed by the `xedit-cli` contract.
3. Phase 2 file/archive reasoning and install planning: connect install planning to archive precedence, overwrite reasoning, and controlled incremental installation.
4. Phase 3 mod evaluation and intake: make the front-end selection workflow usable before deeper automation expands.
5. Phase 4 modpack dev-log workflow: turn internal decision capture into a real maintained workflow rather than a template-only asset.
6. Phase 5 test-session guidance: add repeatable test-session structure and smoke-test direction tied to install batches.
7. Phase 6 localization workflow: layer translation support onto already-stable install, conflict, and test flows.
8. Phase 7 public release changelog workflow: derive player-facing release communication from the stabilized internal dev-log workflow.
9. Phase 8 controlled higher-risk automation: add carefully gated automation only after the read-only and operator-guided loops are proven.
10. Phase 9 packaging and publishable plugin surface: finalize packaging metadata, command surfaces, and publishable OpenCode plugin structure.

## Dependency / Blocker Map

- OpenCode plugin format blocks final OpenCode packaging and install metadata beyond the bootstrap notes already in `.opencode/`.
- The first real xEdit workflow depends on a safe read-only bridge between `skills/conflict-auditor/SKILL.md`, `tools/xedit-cli/CONTRACT.md`, and `mcps/xedit-readonly.md`.
- Release changelog workflow depends on a real dev-log workflow first, or it will have no trustworthy internal source of truth.
- Localization should follow stable install/conflict/test flows so translation work is applied to a reasonably settled baseline.
- Metadata integrations should come after conflict truth, not before; source metadata is useful, but it cannot replace actual conflict inspection.
- Broader MCP integrations depend on stable contracts for metadata lookup, translation-memory access, and consistent agent invocation patterns.
- Save-safety should follow a real curator loop rather than precede it, so warnings reflect actual workflow behavior instead of guesses.
- Higher-risk safety and packaging automation should stay behind the read-only workflow until operational behavior is verified in practice.
- Any write-capable packaging or patching step remains gated by safety rules, explicit targets, and confidence earned from the earlier workflow phases.

## Not Yet Real

- There is no functioning plugin package yet.
- There are no working command entrypoints yet.
- There are no real MCP adapters yet.
- There is no real xEdit wrapper yet.
- There is no usable end-to-end curator workflow yet.
- There is no save-safety automation yet.
- There is no write-capable patch generation yet.

## Game-Specific Pressure Points

- Skyrim: scripts, animation generation, and behavior-output conflicts need special care beyond ordinary plugin ordering.
- Fallout 4: precombine/previs integrity, Buffout-oriented diagnostics, BA2 pressure, and settlement-worldspace edits create recurring curator risk.
- Starfield: evolving toolchain caution matters, including not inheriting FO4/Skyrim assumptions blindly when defining workflow policy.

## Completed Foundations

- Scope and repo guardrails are established in `README.md` and `docs/standards/repo-hygiene.md`.
- Repository bootstrap responsibilities are captured in `agents/repo-bootstrap/AGENT.md`.
- Core workflow skill scaffolds exist, including `skills/conflict-auditor/SKILL.md` and the related curator workflow skills.
- Safety baseline hooks are present in `hooks/runtime-compatibility.md`, `hooks/repo-cleanliness.md`, `hooks/scope-guard.md`, and `hooks/dev-log-reminder.md`.
- Durable documentation templates already ship in `templates/modpack/dev-log-template.md`, `templates/modpack/dev-log-index-template.md`, and `templates/modpack/release-changelog-template.md`.
- Read-only tool and integration contracts already exist in `tools/xedit-cli/CONTRACT.md` and `mcps/xedit-readonly.md`.
- Bootstrap verification is already wired through `tests/bootstrap/verify-foundation.ps1` and `tests/bootstrap/verify-all.ps1`.

## Current Focus

Recommended next target: the first real workflow, specifically read-only xEdit conflict inspection through `conflict-auditor`. That step exercises the most important curator signal path without committing the project to early write automation.

## Supporting Docs

- `README.md` for the project scope and top-level repo entry point.
- `docs/standards/repo-hygiene.md` for durable content and artifact-handling rules.
- `docs/plans/2026-04-10-bgs-modpack-superpowers-design.md` for the broader product architecture and workflow-first model.
- `docs/plans/2026-04-10-bgs-modpack-superpowers-bootstrap.md` for the original repository bootstrap sequence.
- `docs/plans/2026-04-10-roadmap-refresh-design.md` for the roadmap-as-control-panel design intent.
- `docs/plans/2026-04-10-roadmap-refresh.md` for the implementation steps behind this roadmap refresh.
- `templates/README.md` for shipped template resources.
- `tools/README.md` for implementation code and automation placement.
- `mcps/README.md` for MCP specs and contracts only.
- `tests/README.md` for bootstrap verification and future test coverage direction.
