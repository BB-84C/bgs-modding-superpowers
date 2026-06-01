# Roadmap Control Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite `docs/roadmap.md` into a richer project control panel that states project scope, capability status, phase sequence, dependency logic, and completed foundations based on the repository's actual docs and scaffold.

**Architecture:** Keep the roadmap as a single durable control-panel document. Strengthen `tests/bootstrap/verify-foundation.ps1` so it protects the new roadmap contract, then rewrite `docs/roadmap.md` with hybrid sections for mission, workflow scope, capability map, phase ladder, dependency/blocker logic, completed foundations, current focus, and supporting docs.

**Tech Stack:** Markdown, PowerShell, Git

---

### Task 1: Rewrite The Roadmap As A Control Panel

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `tests/bootstrap/verify-foundation.ps1`

**Step 1: Write the failing test**

Update `tests/bootstrap/verify-foundation.ps1` so it expects the new roadmap structure with these stable headings:

- `## Mission`
- `## Systematic Modpack Workflow`
- `## Capability Map`
- `## Phase Ladder`
- `## Dependency / Blocker Map`
- `## Completed Foundations`
- `## Current Focus`
- `## Supporting Docs`

Also add stable signal checks that confirm:

- the mission still states BGS modpack curation and not general mod authoring
- the workflow section includes setup/runtime, evaluation, MO2, xEdit, localization, testing, and modpack-facing documentation
- the capability map names the main plugin systems
- the completed-foundations section reflects real bootstrap assets already present in the repo
- the current-focus section names the recommended next workflow

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-foundation.ps1`
Expected: FAIL because `docs/roadmap.md` still uses the flatter structure.

**Step 3: Write minimal implementation**

Rewrite `docs/roadmap.md` so it:

- carries the project scope directly
- re-elaborates the systematic BGS modpack workflow
- includes a compact capability-status table
- includes a phase ladder with meaningful progression
- includes a dependency/blocker map
- marks completed foundations based on the actual repo docs and scaffold
- identifies the current recommended next target
- links to durable supporting docs only

Keep the roadmap dense and informative, but still smaller than the full design docs.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-foundation.ps1`
Expected: PASS

Run: `pwsh -File tests/bootstrap/verify-all.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add docs/roadmap.md tests/bootstrap/verify-foundation.ps1 docs/plans/2026-04-13-roadmap-control-panel-design.md docs/plans/2026-04-13-roadmap-control-panel.md
git commit -m "docs: turn roadmap into project control panel"
```
