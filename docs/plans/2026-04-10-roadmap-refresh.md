# Roadmap Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh `docs/roadmap.md` so it accurately states the plugin goal, the workflow coverage the plugin must grow into, the current bootstrap baseline, and the next/deferred work areas.

**Architecture:** Treat the roadmap as a lightweight project charter and status board. Update only `docs/roadmap.md`, keeping detailed design and implementation mechanics in the existing plan documents while re-elaborating the plugin goal and workflow coverage directly in the roadmap itself.

**Tech Stack:** Markdown, Git

---

### Task 1: Rewrite The Roadmap Content Model

**Files:**
- Modify: `docs/roadmap.md`
- Test: `tests/bootstrap/verify-foundation.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-foundation.ps1` so it verifies the refreshed roadmap contract, including stable headings such as:

- `## Goal`
- `## Workflow Coverage`
- `## Current Baseline`
- `## Next Major Tracks`
- `## Deferred / Blocked`
- `## Supporting Docs`

Also verify that the roadmap mentions durable goal language around BGS modpack curation and includes workflow coverage terms such as `MO2`, `xEdit`, `localization`, and `testing`.

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-foundation.ps1`
Expected: FAIL because the current roadmap still uses the older heading model and does not contain the refreshed workflow-coverage contract.

**Step 3: Write minimal implementation**

Rewrite `docs/roadmap.md` so it:

- restates the plugin goal in durable terms
- re-elaborates the top-level modpack curation workflow the plugin must cover
- states the current bootstrap baseline honestly
- identifies next major tracks
- marks deferred or blocked work clearly
- points to the design and bootstrap plan as supporting docs

Keep the roadmap concise and status-oriented. Do not turn it into a second design document.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-foundation.ps1`
Expected: PASS

Run: `pwsh -File tests/bootstrap/verify-all.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add docs/roadmap.md tests/bootstrap/verify-foundation.ps1 docs/plans/2026-04-10-roadmap-refresh-design.md docs/plans/2026-04-10-roadmap-refresh.md
git commit -m "docs: refresh project roadmap"
```
