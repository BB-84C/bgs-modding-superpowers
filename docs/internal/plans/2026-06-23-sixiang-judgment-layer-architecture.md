# 思想论 Judgment-Layer Architecture (Design Spec)

- Date: 2026-06-23
- Status: APPROVED (architecture); per-skill content deferred to follow-up `writing-plans`
- Scope: architecture map + conventions only. This spec does NOT author skill bodies or KB records.
- Owner: bgs-modding-superpowers plugin

## 1. Context & Problem

The plugin already has a strong **methodology layer (方法论)** — tooling and mechanics: `xedit-automation`, `xedit-conflict-audit`, `writing-bgs-load-order`, `using-bgs-translator`, `using-bgs-archive`, `using-bgs-papyrus`, MO2 MCP, the asset-conflict engine, the KB. What is missing is the **judgment layer (思想论)** — the human curator's *decision-making*: how to pick a good mod, how to read author instructions, how to build a pack incrementally, how to decide reorder-vs-patch, how to localize well, how to diagnose problems, how to test.

The original founding prompt (`docs/initial_pormpt.md`) asked for a workflow-first, game-agnostic, progressive plugin and explicitly named "how to pick a good mod" as the most important thing — and the thing still living only in the curator's head. The source material for this judgment lives in the curator's tutorial corpus (F-drive scripts + Bilibili AI subtitles + design-philosophy essays), now gathered under `.opencode/artifacts/sixiang-sources/` (see `_source-map.md`).

This spec carves that judgment into a set of small, focused skills plus KB facts, mirroring the `superpowers` skill style and explicitly avoiding one giant catch-all skill.

## 2. Locked Decisions (from brainstorm)

1. **Hybrid carving**: cross-stage judgment → standalone new skills; judgment bound to a single existing tool → injected as a section into that tool's existing skill.
2. **Game-agnostic skills + per-game KB facts**: skills teach the cross-game judgment FRAMEWORK; game-specific facts (FO4 precombine/previs, Skyrim scripts/animation/behavior, Starfield toolchain) live in `bgs-kb` per-game packs and the skill queries the KB at runtime. Boundary: framework → skill, facts → KB.
3. **Read-author-instructions = standalone skill** (`interpreting-mod-author-instructions`).
4. **Asset precedence split**: loose-vs-archive precedence judgment → injected into `using-bgs-archive`; FO4 precombine/previs → KB facts (no standalone skill).
5. **KB schema**: MVP reuses the existing closed 15-value `domain` enum + the `variants` per-game overlay; defer any `judgment.*` / `localization` schema bump.

## 3. Goals / Non-Goals

Goals:
- A modular judgment layer: 5 standalone skills + 5 tool-skill injections + a KB extension plan.
- Game-agnostic skill bodies; game-specific facts in KB per-game packs.
- Mirror proven `superpowers` SKILL.md anatomy; never a giant catch-all skill.

Non-goals (this spec):
- Authoring skill bodies or KB record content (subsequent `writing-plans` + implementation).
- Any KB schema migration.
- New MCP tools or CLI surfaces.
- Starfield/Skyrim deep judgment content (corpus is FO4-heavy; cross-game framework now, per-game KB facts backfilled as packs grow).

## 4. Standalone Judgment Skills (5)

Gerund-named; each owns exactly ONE judgment question.

| skill | The one question | Out of scope | Primary source material |
|---|---|---|---|
| `evaluating-bgs-mods` | Should this mod go in the pack? (BGS systemic-design fit, quality/risk/compatibility/pack-value signals, critical reading of the mod page) | How to install; load order; patching | Bethesda Breakdown design-philosophy corpus + E12 总纲 + cv/opus BA2 articles |
| `interpreting-mod-author-instructions` | How do I correctly download/install per the author's instructions? (FOMOD option reasoning, file/variant selection, prerequisite sequencing) | Whether to include the mod at all | E2/E12 scripts + favlist install-type videos |
| `curating-bgs-modpack` | How do I build the whole pack incrementally? (batch sizing, rollback boundaries, attribution & naming/separator discipline) | Per-mod evaluation; conflict resolution | E12 总纲 + 废土蓝调 2.0 / 介绍 devlog |
| `diagnosing-bgs-problems` | It crashed / FPS tanked — what's the diagnostic ladder? (symptom-first, crash-log reading, bottleneck ID) | Proactive post-install testing | E4/E10 + favlist #4/#10 |
| `testing-bgs-modpack` | It's installed — how do I verify it? (what to inspect, console commands, mod-impact awareness, save hygiene) | Reactive deep diagnosis after failure | thin; backfill from favlist #1 + Starfield/Review |

Granularity rule applied: each passes the carving test (owns one question + has a non-obvious decision worth a flowchart + has rationalizations the agent would use to skip). `understanding-asset-precedence` was rejected as standalone per Decision 4.

## 5. Injections into Existing Tool Skills (5)

Judgment bound to a single tool lives as a new section in that tool's skill (low-intrusion; no new skill).

| Judgment | Target skill | New section | Insertion point |
|---|---|---|---|
| Load-order ordering principles | `writing-bgs-load-order` | `## 排序判断 / Ordering judgment` | after the asterisk-format reference, before official-masters |
| loose-vs-archive precedence | `using-bgs-archive` | `## 资产优先级判断 / Asset precedence judgment` | after `## Hard rules`, before `## JSON envelope contract` |
| When reorder vs when patch | `xedit-conflict-audit` | `## 补丁 vs 改顺序决策 / Patch-vs-reorder decision` | after `## Tools` |
| How to author a good patch | `xedit-automation` | `## 补丁创作判断 / Patch authoring judgment` | after `## Routing doctrine`, before R6 capability checks |
| Localization judgment | `using-bgs-translator` | `## 本地化判断 / Localization judgment` | after `## Prerequisites`, before workflow recipes |

## 6. KB Extension Plan (reuse existing domains; no schema bump)

Facts and game-specific knowledge go to `bgs-kb`. Reuse the existing closed `domain` enum; scope per-game via `appliesTo.games[]` and/or the `variants` overlay (game-agnostic record in `bgs-kb-core` + per-game `variants` merged at `bgs_kb_get({game})`).

| Knowledge | Reused domain | Pack(s) |
|---|---|---|
| FO4 precombine/previs mechanics + risk (NO standalone skill) | `engine`, `archive-precedence` | `bgs-kb-fallout4` |
| mod-quality / risk signals taxonomy | `install-planning` | `bgs-kb-core` + per-game `variants` |
| crash/perf signatures (Buffout4, .NET SF, Trainwreck) | `debugging`, `engine` | per-game packs |
| console commands + test routes per game | `debugging`, `install-planning` | per-game packs |
| load-order grouping templates | `load-order` | per-game packs |
| localization protected-spans / glossary discipline | reuse `install-planning` (loose fit) | `bgs-kb-core` |
| FOMOD pattern taxonomy / variant naming | `install-planning` | `bgs-kb-core` + per-game |

Deferred: adding `judgment.*` / `localization` domain values is a `schemaVersion` 1→2 bump that ripples to every pack manifest; revisit only if reuse proves semantically inadequate.

## 7. Conventions (every judgment skill obeys)

- **SKILL.md anatomy**: Iron Law (one boxed non-negotiable) + When-to-use / When-NOT + DOT process flowchart + Checklist + Red-Flags table (thought→reality) + Rationalizations table (excuse→reality) + single terminal-state handoff.
- **Carving test**: if you cannot fill the Rationalizations table, the candidate is a KB record, not a skill — demote it.
- **Naming**: judgment skills use gerunds (`evaluating-`, `interpreting-`, `curating-`, `diagnosing-`, `testing-`); tool skills keep `using-bgs-*`.
- **Triggers**: `description` describes WHEN (not WHAT); include symptom phrasing ("FPS tanked after a batch", "this override isn't winning") and bilingual EN + 中文 trigger phrases (precedent: `using-bgs-translator`).
- **Boundary-drift guard** (esp. `evaluating-bgs-mods`): skill carries a red-flag "if you are about to write a game-specific fact here, STOP — it belongs in a KB record"; skill always `bgs_kb_query`s, never caches/inlines game facts.
- **Anti-sprawl**: each skill opens with a "one primary skill per user intent" route gate (use-me / don't-use-me / hand-off-to-X), so an agent does not chain 3-5 judgment skills for one task.
- **Anti-patterns banned** (from superpowers/Anthropic): no narrative war-stories, no first-person, no `@`-include of other skills, description must not summarize the workflow.

## 8. Registration & Build Mechanics

- **Bootstrap is the only registration surface.** Each new standalone skill is registered in `skills/using-bgs-modding-superpowers/SKILL.md` in THREE places: the `## Available skills` router-table row, a `## How to use this bootstrap` bullet, and a `## See also` entry.
- **KB authoring**: `scripts/dev-kb-author.ps1 -PackId <packId>` (validate → build → materialize), or the manual `cli validate` / `cli build` + `build-portable-plugin.ps1` path. Two-commit shape (source commit + materialized `plugins/` commit) per repo `AGENTS.md`.
- **MCP discovery is one-shot at startup** — restart OpenCode after KB build before verifying retrieval.
- **Hard rules** in the bootstrap stay authoritative; a new skill introducing a new boundary adds a rule there.

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| skill↔KB boundary drift (taste-as-fact in `evaluating-bgs-mods`) | red-flag + always-query-KB + KB record discipline (controlled risk vocabulary) |
| skill sprawl / cross-reference chaining recreating a "giant brain" | "one primary skill per user intent" route gate; carving test |
| FO4 bias in corpus → accidental FO4-specific skill bodies | game-agnostic body rule + per-game KB facts; review each skill body for inlined FO4 facts |
| `testing-bgs-modpack` thin source material | backfill from favlist #1 + Starfield/Review; mark UNVERIFIED facts rather than inventing |
| reused KB domains semantically loose (localization) | accept for MVP; track as candidate for a future scoped schema bump |

## 10. Sequencing (recommended; not binding)

Implement standalone skills in descending source-richness / leverage order, each as its own `writing-plans` → implementation cycle:
1. `evaluating-bgs-mods` (richest substrate: Bethesda Breakdown + 总纲; highest leverage — the founding "most important thing").
2. xEdit injections (`xedit-automation` + `xedit-conflict-audit`) — E9 substrate is strong; closes the patch-judgment gap.
3. `curating-bgs-modpack` + `interpreting-mod-author-instructions`.
4. `diagnosing-bgs-problems` + the `using-bgs-archive` / `writing-bgs-load-order` injections + FO4 precombine KB.
5. `using-bgs-translator` localization injection.
6. `testing-bgs-modpack` (backfill source first).

## 11. Acceptance Criteria (for the architecture, not the content)

- Each standalone skill has a one-question scope statement and a fillable Rationalizations table (else demoted to KB).
- No judgment skill body contains a game-specific fact that belongs in KB (review gate).
- Every new skill registered in all three bootstrap places.
- KB additions validate against the existing schema with no `schemaVersion` change.
- The bootstrap router routes a representative symptom phrase to the correct single primary skill.

## 12. References

- `docs/initial_pormpt.md` — founding prompt.
- `.opencode/artifacts/sixiang-sources/_source-map.md` — source corpus map (F-drive scripts + Bilibili subtitles + articles + design-philosophy corpus).
- `.opencode/artifacts/sixiang-architecture/multi-lens/synthesis.md` — multi-perspective brainstorm synthesis.
- `docs/internal/roadmap.md` — Capability Map (mod evaluator / install planner / localization / test-session previously "scaffolded only").
- Prior art: `obra/superpowers` (SKILL.md anatomy), negative example `WingedGuardian/skyrimvr-claude-toolkit` (monolithic KNOWLEDGEBASE.md).
