# BGS Modpack Superpowers Bootstrap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bootstrap a clean, GitHub-ready OpenCode plugin repository for BGS modpack curation with the initial structure, standards, agent/skill skeletons, template resources, and integration specs.

**Architecture:** Build the repo as a workflow-first plugin modeled after `superpowers`, with OpenCode-specific installation scaffolding, a dedicated `repo-bootstrap` agent, core skill and hook skeletons, clean separation between durable knowledge and ignored artifacts, and placeholder specs for future tooling like `xedit-cli` and MCP integrations. Use small PowerShell verification scripts as the bootstrap test harness so the repo structure and document contract can be checked automatically without inventing heavy application code too early.

**Tech Stack:** Markdown, PowerShell, Git, OpenCode plugin conventions

---

### Task 1: Repository Foundation And OpenCode Scaffolding

**Files:**
- Create: `tests/bootstrap/verify-foundation.ps1`
- Create: `.gitignore`
- Create: `.opencode/INSTALL.md`
- Create: `.opencode/README.md`
- Create: `README.md`
- Create: `docs/roadmap.md`
- Create: `docs/standards/repo-hygiene.md`

**Step 1: Write the failing verification script**

```powershell
$ErrorActionPreference = "Stop"

$requiredPaths = @(
    ".gitignore",
    ".opencode/INSTALL.md",
    ".opencode/README.md",
    "README.md",
    "docs/roadmap.md",
    "docs/standards/repo-hygiene.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing required bootstrap files: $($missing -join ', ')"
}

$readme = Get-Content "README.md" -Raw
if ($readme -notmatch "BGS modpack curation") {
    throw "README.md is missing the project scope statement"
}

$roadmap = Get-Content "docs/roadmap.md" -Raw
foreach ($heading in @("## Now", "## Next", "## Later", "## Blocked / Needs Research", "## Done")) {
    if ($roadmap -notmatch [regex]::Escape($heading)) {
        throw "docs/roadmap.md is missing heading: $heading"
    }
}

$install = Get-Content ".opencode/INSTALL.md" -Raw
if ($install -notmatch "OpenCode") {
    throw ".opencode/INSTALL.md is missing OpenCode installation guidance"
}

Write-Host "Foundation bootstrap checks passed."
```

**Step 2: Run the verification script to make sure it fails**

Run: `pwsh -File tests/bootstrap/verify-foundation.ps1`
Expected: FAIL with missing file errors because none of the foundation files exist yet.

**Step 3: Write the minimal repository foundation**

Create `.gitignore`:

```gitignore
.artifacts/*
!.artifacts/.gitkeep

*.log
*.tmp
*.bak
Thumbs.db
Desktop.ini
```

Create `.opencode/INSTALL.md`:

```markdown
# OpenCode Installation

## Purpose

This repository is an OpenCode plugin for Bethesda Game Studios modpack curation workflows.

## Bootstrap State

The initial bootstrap provides repository structure, workflow skeletons, hook skeletons, templates, and integration specs.

## Later Work

Actual install commands and plugin metadata should be added only after the OpenCode plugin packaging format is verified.
```

Create `.opencode/README.md`:

```markdown
# OpenCode Plugin Notes

This directory holds OpenCode-specific installation notes and later plugin metadata.

Do not invent packaging files until the required OpenCode format has been verified.
```

Create `README.md`:

```markdown
# BGS Modpack Superpowers

An OpenCode plugin for Bethesda Game Studios modpack curation across Skyrim, Fallout 4, and Starfield.

## Scope

This project focuses on BGS modpack curation, not general mod authoring.

## Current Status

This repository is in bootstrap phase.

## Initial Areas

- workflow skills
- protective hooks
- operational agents
- template resources
- xEdit orchestration specs
- MCP placeholder specs

## Project Tracking

See `docs/roadmap.md` for the plugin roadmap.
See `docs/standards/repo-hygiene.md` for repository cleanliness rules.
```

Create `docs/roadmap.md`:

```markdown
# Plugin Roadmap

## Now

- Bootstrap the repository structure and standards.

## Next

- Draft first-wave skill and hook skeletons.

## Later

- Implement `xedit-cli` read-only inspection commands.

## Blocked / Needs Research

- Verify the exact OpenCode plugin packaging format.
- Verify the safest initial xEdit Pascal-script invocation contract.

## Done

- Approved the initial architecture and bootstrap design.
```

Create `docs/standards/repo-hygiene.md`:

```markdown
# Repo Hygiene Standard

## Durable Content

Tracked files should contain durable knowledge, workflow definitions, project docs, templates, or tested tooling.

## Ignored Working Content

Raw investigation output belongs in `.artifacts/` and must not be committed.

## Artifact Lifecycle

1. Collect raw material in `.artifacts/investigation/<date-topic>/raw/`.
2. Distill reusable findings into tracked docs.
3. Move still-needed raw material to `.artifacts/archive/<date-topic>/`.
4. Delete archived raw material when it is no longer needed.

## Root Cleanliness

Do not leave temporary files, dumps, screenshots, or local machine state in the repository root.
```

Run: `git init`
Expected: repository initialized locally.

**Step 4: Run the verification again**

Run: `pwsh -File tests/bootstrap/verify-foundation.ps1`
Expected: PASS with `Foundation bootstrap checks passed.`

Run: `git rev-parse --is-inside-work-tree`
Expected: `true`

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add .gitignore .opencode/INSTALL.md .opencode/README.md README.md docs/roadmap.md docs/standards/repo-hygiene.md tests/bootstrap/verify-foundation.ps1
git commit -m "chore: bootstrap repository foundation"
```

### Task 2: Directory Scaffold And Repo-Bootstrap Agent

**Files:**
- Create: `tests/bootstrap/verify-layout.ps1`
- Create: `agents/repo-bootstrap/AGENT.md`
- Create: `commands/README.md`
- Create: `knowledge/README.md`
- Create: `research/summaries/README.md`
- Create: `templates/README.md`
- Create: `tools/README.md`
- Create: `mcps/README.md`
- Create: `tests/README.md`
- Create: `.artifacts/.gitkeep`

**Step 1: Write the failing layout verification script**

```powershell
$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "agents/repo-bootstrap/AGENT.md",
    "commands/README.md",
    "knowledge/README.md",
    "research/summaries/README.md",
    "templates/README.md",
    "tools/README.md",
    "mcps/README.md",
    "tests/README.md",
    ".artifacts/.gitkeep"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing layout files: $($missing -join ', ')"
}

$agent = Get-Content "agents/repo-bootstrap/AGENT.md" -Raw
foreach ($phrase in @("initialize git", "create directory scaffold", "prepare GitHub-facing files", "do not commit raw artifacts")) {
    if ($agent -notmatch [regex]::Escape($phrase)) {
        throw "agents/repo-bootstrap/AGENT.md is missing phrase: $phrase"
    }
}

Write-Host "Layout bootstrap checks passed."
```

**Step 2: Run the verification script to make sure it fails**

Run: `pwsh -File tests/bootstrap/verify-layout.ps1`
Expected: FAIL with missing layout files.

**Step 3: Write the minimal layout scaffolding and agent**

Create `agents/repo-bootstrap/AGENT.md`:

```markdown
# Repo Bootstrap Agent

## Mission

Bootstrap and maintain the local repository structure for this plugin.

## Responsibilities

- initialize git when needed
- create directory scaffold
- prepare GitHub-facing files
- write ignore rules and repo standards
- do not commit raw artifacts
- avoid destructive cleanup unless explicitly requested

## Stop Conditions

- stop if GitHub owner, repo name, visibility, or auth state are required and unavailable
- stop if cleanup would delete material without explicit approval
```

Create `commands/README.md`:

```markdown
# Commands

This directory will hold reusable command entrypoints for plugin workflows.
```

Create `knowledge/README.md`:

```markdown
# Knowledge

Store durable curator knowledge here after it has been distilled from raw research.
```

Create `research/summaries/README.md`:

```markdown
# Research Summaries

Keep small, durable investigation summaries here. Do not store raw artifacts in this directory.
```

Create `templates/README.md`:

```markdown
# Templates

This directory holds shipped template resources for user-facing modpack workflows.
```

Create `tools/README.md`:

```markdown
# Tools

This directory holds concrete automation such as the future `xedit-cli` wrapper.
```

Create `mcps/README.md`:

```markdown
# MCP Specs

This directory holds MCP placeholder specs and later implementation notes.
```

Create `tests/README.md`:

```markdown
# Tests

Bootstrap verification scripts live in `tests/bootstrap/`.
```

Create `.artifacts/.gitkeep` as an empty file.

**Step 4: Run the verification again**

Run: `pwsh -File tests/bootstrap/verify-layout.ps1`
Expected: PASS with `Layout bootstrap checks passed.`

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add agents/repo-bootstrap/AGENT.md commands/README.md knowledge/README.md research/summaries/README.md templates/README.md tools/README.md mcps/README.md tests/README.md .artifacts/.gitkeep tests/bootstrap/verify-layout.ps1
git commit -m "chore: add repository layout scaffold"
```

### Task 3: Core Skill Skeletons

**Files:**
- Create: `tests/bootstrap/verify-skills.ps1`
- Create: `skills/mod-evaluator/SKILL.md`
- Create: `skills/install-planner/SKILL.md`
- Create: `skills/conflict-auditor/SKILL.md`
- Create: `skills/write-dev-log/SKILL.md`
- Create: `skills/write-release-changelog/SKILL.md`
- Create: `skills/localization-assistant/SKILL.md`
- Create: `skills/test-session-guide/SKILL.md`

**Step 1: Write the failing skill verification script**

```powershell
$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "skills/mod-evaluator/SKILL.md",
    "skills/install-planner/SKILL.md",
    "skills/conflict-auditor/SKILL.md",
    "skills/write-dev-log/SKILL.md",
    "skills/write-release-changelog/SKILL.md",
    "skills/localization-assistant/SKILL.md",
    "skills/test-session-guide/SKILL.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing skill files: $($missing -join ', ')"
}

foreach ($path in $requiredPaths) {
    $content = Get-Content $path -Raw
    foreach ($heading in @("## Purpose", "## When To Use", "## Workflow", "## Outputs")) {
        if ($content -notmatch [regex]::Escape($heading)) {
            throw "$path is missing heading: $heading"
        }
    }
}

Write-Host "Skill bootstrap checks passed."
```

**Step 2: Run the verification script to make sure it fails**

Run: `pwsh -File tests/bootstrap/verify-skills.ps1`
Expected: FAIL with missing skill files.

**Step 3: Write the minimal skill skeletons**

Create `skills/mod-evaluator/SKILL.md`:

```markdown
# Skill: Mod Evaluator

## Purpose

Evaluate whether a candidate mod belongs in a curated BGS modpack.

## When To Use

Use when considering a new mod for Skyrim, Fallout 4, or Starfield.

## Workflow

1. Capture the mod source and version.
2. Check runtime and dependency compatibility.
3. Assess conflict class, overlap, maintenance state, and risk.
4. Record the decision and reasoning.

## Outputs

- accept, reject, or defer decision
- reasons for the decision
- follow-up checks if the decision is not final
```

Create `skills/install-planner/SKILL.md`:

```markdown
# Skill: Install Planner

## Purpose

Turn a chosen mod into a safe installation workflow.

## When To Use

Use after a mod has been accepted for possible inclusion.

## Workflow

1. Identify prerequisites and install method.
2. Determine manager install versus root-level install.
3. Define naming, ordering, and immediate smoke tests.
4. Identify likely conflicts before activation.

## Outputs

- installation steps
- ordering guidance
- first-pass test checklist
```

Create `skills/conflict-auditor/SKILL.md`:

```markdown
# Skill: Conflict Auditor

## Purpose

Separate file conflicts from plugin/data conflicts and guide the next inspection step.

## When To Use

Use when two or more mods overlap in files, records, or load-order behavior.

## Workflow

1. Classify the overlap as file, archive, or plugin-data conflict.
2. Check loose files versus BSA or BA2 precedence.
3. Identify whether load order or a patch is required.
4. Record unresolved hotspots for later xEdit work.

## Outputs

- conflict classification
- likely resolution path
- unresolved follow-up list
```

Create `skills/write-dev-log/SKILL.md`:

```markdown
# Skill: Write Dev Log

## Purpose

Maintain a strategic development log inside a user's modpack project.

## When To Use

Use after important modpack decisions, installs, rejections, conflict resolutions, or testing milestones.

## Workflow

1. Capture the action, reasoning, and impacted mods.
2. Mark the status as accepted, deferred, rejected, or unresolved.
3. Update the table of contents or index.
4. Preserve links to evidence when relevant.

## Outputs

- updated modpack development log
- updated index entries
- recorded unresolved items when applicable
```

Create `skills/write-release-changelog/SKILL.md`:

```markdown
# Skill: Write Release Changelog

## Purpose

Generate player-facing release notes for a modpack update.

## When To Use

Use when preparing a public release or release candidate for a modpack.

## Workflow

1. Gather the release scope from the project state.
2. Convert internal changes into player-readable categories.
3. Add upgrade or save warnings when needed.
4. Keep wording concise and public-facing.

## Outputs

- public changelog entry
- release warnings
- list of changes grouped by type
```

Create `skills/localization-assistant/SKILL.md`:

```markdown
# Skill: Localization Assistant

## Purpose

Guide modpack localization work and translation consistency.

## When To Use

Use when evaluating, preparing, or validating translated modpack content.

## Workflow

1. Check glossary and translation source precedence.
2. Identify untranslated or inconsistent strings.
3. Record whether translation should happen before or after patching.
4. Flag UI, font, and string-table risks.

## Outputs

- localization checklist
- translation gaps
- consistency risks
```

Create `skills/test-session-guide/SKILL.md`:

```markdown
# Skill: Test Session Guide

## Purpose

Help the user test newly installed or patched mods efficiently in game.

## When To Use

Use after installs, patching, or localization changes.

## Workflow

1. Identify what changed and what systems it affects.
2. Suggest focused in-game checks.
3. Suggest relevant console-command shortcuts when appropriate.
4. Record outcomes and remaining risks.

## Outputs

- focused test checklist
- fast validation steps
- follow-up risks to monitor
```

**Step 4: Run the verification again**

Run: `pwsh -File tests/bootstrap/verify-skills.ps1`
Expected: PASS with `Skill bootstrap checks passed.`

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add skills/mod-evaluator/SKILL.md skills/install-planner/SKILL.md skills/conflict-auditor/SKILL.md skills/write-dev-log/SKILL.md skills/write-release-changelog/SKILL.md skills/localization-assistant/SKILL.md skills/test-session-guide/SKILL.md tests/bootstrap/verify-skills.ps1
git commit -m "feat: add bootstrap skill skeletons"
```

### Task 4: Core Hook Skeletons

**Files:**
- Create: `tests/bootstrap/verify-hooks.ps1`
- Create: `hooks/runtime-compatibility.md`
- Create: `hooks/repo-cleanliness.md`
- Create: `hooks/scope-guard.md`
- Create: `hooks/dev-log-reminder.md`

**Step 1: Write the failing hook verification script**

```powershell
$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "hooks/runtime-compatibility.md",
    "hooks/repo-cleanliness.md",
    "hooks/scope-guard.md",
    "hooks/dev-log-reminder.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing hook files: $($missing -join ', ')"
}

foreach ($path in $requiredPaths) {
    $content = Get-Content $path -Raw
    foreach ($heading in @("## Trigger", "## Check", "## Action")) {
        if ($content -notmatch [regex]::Escape($heading)) {
            throw "$path is missing heading: $heading"
        }
    }
}

Write-Host "Hook bootstrap checks passed."
```

**Step 2: Run the verification script to make sure it fails**

Run: `pwsh -File tests/bootstrap/verify-hooks.ps1`
Expected: FAIL with missing hook files.

**Step 3: Write the minimal hook skeletons**

Create `hooks/runtime-compatibility.md`:

```markdown
# Runtime Compatibility Hook

## Trigger

Before advice about installing, ordering, patching, or testing a mod.

## Check

Identify the game, runtime branch, script extender state, and major toolchain assumptions.

## Action

Warn or stop when the workflow depends on incompatible runtime assumptions.
```

Create `hooks/repo-cleanliness.md`:

```markdown
# Repo Cleanliness Hook

## Trigger

Before creating, moving, staging, or committing files in this repository.

## Check

Reject raw artifacts, temporary dumps, local machine state, and noisy root-level files.

## Action

Move temporary output into `.artifacts/`, summarize durable findings in tracked docs, and keep the root clean.
```

Create `hooks/scope-guard.md`:

```markdown
# Scope Guard Hook

## Trigger

Whenever a workflow starts drifting toward general mod authoring.

## Check

Determine whether the task is curation, patching, diagnostics, or full content creation.

## Action

Keep the workflow centered on modpack curation unless the user explicitly requests authoring work.
```

Create `hooks/dev-log-reminder.md`:

```markdown
# Dev Log Reminder Hook

## Trigger

After significant modpack decisions in a user project.

## Check

Look for accepted, rejected, deferred, unresolved, or tested changes that should be recorded.

## Action

Prompt the workflow to update the user project's dev log with the strategic outcome.
```

**Step 4: Run the verification again**

Run: `pwsh -File tests/bootstrap/verify-hooks.ps1`
Expected: PASS with `Hook bootstrap checks passed.`

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add hooks/runtime-compatibility.md hooks/repo-cleanliness.md hooks/scope-guard.md hooks/dev-log-reminder.md tests/bootstrap/verify-hooks.ps1
git commit -m "feat: add bootstrap hook skeletons"
```

### Task 5: User-Modpack Template Resources

**Files:**
- Create: `tests/bootstrap/verify-templates.ps1`
- Create: `templates/modpack/dev-log-template.md`
- Create: `templates/modpack/dev-log-index-template.md`
- Create: `templates/modpack/release-changelog-template.md`

**Step 1: Write the failing template verification script**

```powershell
$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "templates/modpack/dev-log-template.md",
    "templates/modpack/dev-log-index-template.md",
    "templates/modpack/release-changelog-template.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing template files: $($missing -join ', ')"
}

$devLog = Get-Content "templates/modpack/dev-log-template.md" -Raw
foreach ($heading in @("# Modpack Development Log", "## Table of Contents", "## Active Decisions", "## Unresolved Issues")) {
    if ($devLog -notmatch [regex]::Escape($heading)) {
        throw "Dev log template is missing heading: $heading"
    }
}

$changelog = Get-Content "templates/modpack/release-changelog-template.md" -Raw
foreach ($heading in @("# Changelog", "## Added", "## Changed", "## Fixed", "## Upgrade Notes")) {
    if ($changelog -notmatch [regex]::Escape($heading)) {
        throw "Release changelog template is missing heading: $heading"
    }
}

Write-Host "Template bootstrap checks passed."
```

**Step 2: Run the verification script to make sure it fails**

Run: `pwsh -File tests/bootstrap/verify-templates.ps1`
Expected: FAIL with missing template files.

**Step 3: Write the minimal template resources**

Create `templates/modpack/dev-log-template.md`:

```markdown
# Modpack Development Log

## Table of Contents

- [Active Decisions](#active-decisions)
- [Installed Changes](#installed-changes)
- [Deferred Or Rejected Mods](#deferred-or-rejected-mods)
- [Conflict Work](#conflict-work)
- [Localization Work](#localization-work)
- [Testing Notes](#testing-notes)
- [Unresolved Issues](#unresolved-issues)

## Active Decisions

## Installed Changes

## Deferred Or Rejected Mods

## Conflict Work

## Localization Work

## Testing Notes

## Unresolved Issues
```

Create `templates/modpack/dev-log-index-template.md`:

```markdown
# Dev Log Index Companion

| Entry | Section | Status | Anchor |
| --- | --- | --- | --- |
| Example decision | Active Decisions | Deferred | `#active-decisions` |
```

Create `templates/modpack/release-changelog-template.md`:

```markdown
# Changelog

## Added

## Changed

## Fixed

## Removed

## Upgrade Notes
```

**Step 4: Run the verification again**

Run: `pwsh -File tests/bootstrap/verify-templates.ps1`
Expected: PASS with `Template bootstrap checks passed.`

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add templates/modpack/dev-log-template.md templates/modpack/dev-log-index-template.md templates/modpack/release-changelog-template.md tests/bootstrap/verify-templates.ps1
git commit -m "feat: add modpack documentation templates"
```

### Task 6: xEdit CLI Specs, MCP Placeholders, And Aggregate Verification

**Files:**
- Create: `tests/bootstrap/verify-specs.ps1`
- Create: `tests/bootstrap/verify-all.ps1`
- Create: `tools/xedit-cli/README.md`
- Create: `tools/xedit-cli/CONTRACT.md`
- Create: `mcps/nexus-metadata.md`
- Create: `mcps/loot-metadata.md`
- Create: `mcps/xedit-readonly.md`
- Create: `mcps/translation-memory.md`

**Step 1: Write the failing spec verification scripts**

Create `tests/bootstrap/verify-specs.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$requiredPaths = @(
    "tools/xedit-cli/README.md",
    "tools/xedit-cli/CONTRACT.md",
    "mcps/nexus-metadata.md",
    "mcps/loot-metadata.md",
    "mcps/xedit-readonly.md",
    "mcps/translation-memory.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing spec files: $($missing -join ', ')"
}

$contract = Get-Content "tools/xedit-cli/CONTRACT.md" -Raw
foreach ($heading in @("## Goals", "## Read-Only Commands", "## Future Write Commands", "## Safety Rules")) {
    if ($contract -notmatch [regex]::Escape($heading)) {
        throw "xedit-cli contract is missing heading: $heading"
    }
}

Write-Host "Spec bootstrap checks passed."
```

Create `tests/bootstrap/verify-all.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$checks = @(
    "tests/bootstrap/verify-foundation.ps1",
    "tests/bootstrap/verify-layout.ps1",
    "tests/bootstrap/verify-skills.ps1",
    "tests/bootstrap/verify-hooks.ps1",
    "tests/bootstrap/verify-templates.ps1",
    "tests/bootstrap/verify-specs.ps1"
)

foreach ($check in $checks) {
    & (Resolve-Path $check)
}

Write-Host "All bootstrap checks passed."
```

**Step 2: Run the spec verification script to make sure it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL with missing spec files.

**Step 3: Write the minimal tool and MCP specs**

Create `tools/xedit-cli/README.md`:

```markdown
# xedit-cli

This directory is reserved for a wrapper that orchestrates upstream xEdit through generated Pascal scripts.

The wrapper should keep xEdit external and treat it as the execution engine.
```

Create `tools/xedit-cli/CONTRACT.md`:

```markdown
# xedit-cli Contract

## Goals

- orchestrate upstream xEdit without forking it
- run generated Pascal scripts
- normalize output for agent consumption

## Read-Only Commands

- list masters
- inspect records
- scan overrides
- export filtered conflict reports

## Future Write Commands

- create compatibility patch shells
- apply controlled scripted edits to a new patch plugin

## Safety Rules

- never edit source mods in place
- default to read-only mode
- require explicit patch targets for write operations
```

Create `mcps/nexus-metadata.md`:

```markdown
# MCP: Nexus Metadata

Planned purpose: fetch mod metadata, requirements, versions, and changelog context for evaluation workflows.
```

Create `mcps/loot-metadata.md`:

```markdown
# MCP: LOOT Metadata

Planned purpose: fetch load-order warnings and compatibility notes for supported games.
```

Create `mcps/xedit-readonly.md`:

```markdown
# MCP: xEdit Read-Only

Planned purpose: expose read-only record, master, and conflict inspection from xEdit-backed workflows.
```

Create `mcps/translation-memory.md`:

```markdown
# MCP: Translation Memory

Planned purpose: provide reusable glossary and translation-memory lookups for localization workflows.
```

**Step 4: Run aggregate verification**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS with `Spec bootstrap checks passed.`

Run: `pwsh -File tests/bootstrap/verify-all.ps1`
Expected: PASS with `All bootstrap checks passed.`

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md mcps/nexus-metadata.md mcps/loot-metadata.md mcps/xedit-readonly.md mcps/translation-memory.md tests/bootstrap/verify-specs.ps1 tests/bootstrap/verify-all.ps1
git commit -m "feat: add bootstrap specs and aggregate verification"
```
