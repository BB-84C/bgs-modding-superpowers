# BGS Modpack Superpowers Design

## Goal

Create an OpenCode plugin that acts as `superpowers for Bethesda Game Studios modpack development`, focused on professional modpack curation for Skyrim, Fallout 4, and Starfield.

The plugin is for modpack development and maintenance, not general mod authoring. Its center of gravity is workflow guidance, decision support, safety checks, and targeted automation for evaluating mods, planning installs, resolving file and data conflicts, localizing content, testing installs, and documenting modpack progress.

## Context And Scope

The initial knowledge base comes from:

- local Fallout 4 tutorial directories
- a Fallout 4 integration workflow folder
- a sparse Starfield tutorial directory
- Bilibili playlist/article/video sources
- current best-practice verification gathered online

Those sources strongly support a curator-oriented workflow built around `MO2`, `xEdit`, archive awareness, translation discipline, incremental testing, and careful conflict reasoning. They also contain outdated or Fallout 4-specific material, so the plugin design must separate shared curator logic from per-game policy.

This plugin should help users build and maintain modpacks. It should not default into Creation Kit, Papyrus, asset authoring, or quest-mod creation workflows except where diagnostic context requires it.

## Chosen Approach

The selected architecture is a `skill-first plugin` with a shared curator core and game-specific policy overlays.

Alternative approaches considered:

1. `MCP-first automation platform`
   Powerful later, but too heavy for bootstrap and too likely to encode stale assumptions too early.
2. `Game-siloed plugin`
   Easier to reason about at first, but duplicates shared curator workflows and risks overfitting to Fallout 4.

The skill-first approach best matches the desired `superpowers`-style workflow: the plugin should be useful even when only the workflow documents and a small amount of tooling exist.

## Repository Architecture

The repository should mirror the workflow-first philosophy seen in `superpowers`, adapted for BGS modpack curation.

Primary tracked areas:

- `.opencode/` for OpenCode-specific installation and plugin metadata
- `skills/` for workflow definitions
- `hooks/` for mandatory guardrails
- `agents/` for operational sub-agents such as repo bootstrap
- `commands/` for reusable command entrypoints
- `tools/` for concrete automation such as the future `xedit-cli`
- `mcps/` for integration specs and later adapters
- `templates/` for shipped modpack-documentation and workflow templates
- `knowledge/` for stable curated guidance
- `research/summaries/` for distilled research outputs worth keeping
- `docs/plans/` for design and implementation plans
- `docs/standards/` for project rules and repo hygiene
- `docs/roadmap.md` for the plugin project's roadmap
- `tests/` for validating scripts, templates, and future tooling where practical

Ignored working area:

- `.artifacts/` for raw research output, OCR captures, scratch files, temporary reports, and experimental agent-generated artifacts

## Core Product Model

The plugin has three layers.

### 1. Core curator skills

These are the main product surface.

- `mod-evaluator`
  Evaluate whether a mod should be included in a curated list.
- `install-planner`
  Turn a chosen mod into a safe installation and verification workflow.
- `conflict-auditor`
  Separate file conflicts from plugin/data conflicts and explain what to inspect or patch next.
- `localization-assistant`
  Support translation workflow, glossary consistency, untranslated string review, and ordering relative to patching.
- `test-session-guide`
  Help the user test newly installed or patched mods efficiently in-game.
- `write-dev-log`
  Maintain the user's modpack development log inside the actual modpack project.
- `write-release-changelog`
  Produce player-facing release notes inside the actual modpack project.

### 2. Protective hooks

- `runtime-compatibility`
  Detect game/runtime/toolchain compatibility before advice is given.
- `save-safety-guard`
  Warn on risky mid-save changes, removals, or version jumps.
- `repo-cleanliness`
  Prevent raw investigation artifacts or local-only state from leaking into the plugin repo.
- `scope-guard`
  Keep the agent focused on modpack curation rather than full mod authoring.
- `dev-log-reminder`
  Encourage strategic logging when shipped later as part of the modpack-development workflows.

### 3. Deferred MCPs and integration tracks

These should be scaffolded as placeholders first.

- `nexus-metadata`
- `loot-metadata`
- `xedit-readonly`
- `translation-memory`

## Repo Bootstrap Sub-Agent

The plugin should include a dedicated operational workflow for repository initialization and GitHub-facing hygiene.

`repo-bootstrap` should:

- initialize the repo locally
- create the directory scaffold
- establish ignore rules and standards docs
- prepare GitHub-facing project files
- keep raw research material out of tracked history
- avoid destructive cleanup by default

If GitHub remote details and local authentication are available, the workflow can wire the remote. If not, it should leave a clear next step rather than guessing.

## Documentation Separation

Three different documentation concerns must stay separate.

### A. Plugin project management

This repository itself should maintain:

- `docs/roadmap.md` for the plugin roadmap
- design docs
- standards docs
- research summaries
- tool and module specs

### B. Plugin-delivered modpack workflows

The plugin should ship skills and templates for modpack projects to create and maintain:

- a modpack development log
- a public modpack changelog

These are outputs that belong in the user's modpack workspace after the plugin is installed, not baseline artifacts for this repository.

### C. Optional plugin release documentation

If the plugin later needs its own release notes, that is a separate concern from the modpack-dev-log and modpack-changelog skills.

## Modpack Dev Log Design

The dev log is a shipped workflow for user modpack projects, not this repository.

It should capture strategically important decisions such as:

- mods considered and rejected
- mods downloaded but intentionally not installed
- version pinning decisions
- conflict findings and resolutions
- known unresolved issues
- localization status decisions
- testing findings and follow-up items

Recommended behavior:

- write to a markdown log in the user's project
- keep a stable heading-based table of contents at the top
- avoid relying only on raw line numbers in the markdown file
- if machine navigation is needed, generate a companion index file mapping entries to current ranges or anchors

## Public Modpack Changelog Design

The public changelog is also a shipped workflow for user modpack projects.

It should transform internal development history into concise release notes covering:

- added content
- changed content
- fixes
- compatibility notes
- upgrade or save warnings
- removals or deferred items worth surfacing publicly

## xEdit Automation Track

`xedit-cli` should be a major tool track in this project, but it should not fork or recompile xEdit.

Instead, the plugin should:

- keep upstream xEdit external
- generate Pascal scripts
- invoke xEdit through those scripts
- collect and normalize output for agent consumption

Planned capability tiers:

1. `Read-only inspection`
   record lookup, master listing, override detection, conflict scans, filtered reports
2. `Analysis helpers`
   structured summaries of common conflict patterns
3. `Controlled patch generation`
   scripted creation of compatibility patches with explicit safety constraints

This makes xEdit the execution engine while the plugin provides orchestration and workflow control.

## Artifact Lifecycle

The repository should stay clean even when investigations are noisy.

Lifecycle for investigation artifacts:

1. Collect raw material in `.artifacts/investigation/<date-topic>/raw/`
2. Distill durable findings into `research/summaries/` or `knowledge/`
3. Move still-useful raw material to `.artifacts/archive/<date-topic>/`
4. Delete archived raw material once the durable summary is trusted and no longer depends on the raw capture

`repo-cleanliness` should enforce that raw investigation files, local machine paths, temporary dumps, and bulky media do not get committed by accident.

## Roadmap

Because this plugin cannot be finished in one pass, the project itself needs a roadmap.

`docs/roadmap.md` should track:

- current phase
- near-term priorities
- later modules
- blocked research items
- completed foundations

Each roadmap entry should record the objective, why it matters, dependencies, and related skills or tools.

## First-Session Bootstrap Deliverables

For the first implementation session after planning, the target outcome is `repo + structure`, not full feature completion.

That bootstrap should produce:

- local git repo initialization
- directory scaffold aligned to the design
- OpenCode plugin scaffolding and installation metadata
- ignore rules and standards docs
- project `README.md`
- plugin roadmap document
- first-wave workflow files for core bootstrap skills and hooks
- placeholder specs for MCPs and `xedit-cli`
- modpack template resources for future shipped workflows
- `.artifacts/` ignored from Git from day one

Recommended first-wave assets:

- `agents/repo-bootstrap`
- `skills/mod-evaluator`
- `skills/install-planner`
- `skills/conflict-auditor`
- `skills/write-dev-log`
- `skills/write-release-changelog`
- `hooks/runtime-compatibility`
- `hooks/repo-cleanliness`
- `hooks/scope-guard`
- `hooks/dev-log-reminder`
- placeholder drafts for `localization-assistant` and `test-session-guide`
- `tools/xedit-cli/` specification area
- `mcps/` placeholder specs

## Design Principles

- workflow-first before heavy automation
- curator focus over mod-author focus
- shared logic first, per-game policy second
- evidence over assumptions
- repo cleanliness by default
- durable summaries instead of raw clutter
- automation should assist judgement, not replace it

## Success Criteria For Bootstrap

After bootstrap, a fresh agent session should be able to open the repo and immediately understand:

- the project goal
- the plugin scope boundary
- where active investigation output goes
- where durable knowledge goes
- which core skills and hooks exist first
- how the repo stays clean
- where the future `xedit-cli` work will live

That is the correct first milestone for this project.
