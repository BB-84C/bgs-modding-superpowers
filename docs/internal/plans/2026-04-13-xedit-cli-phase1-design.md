# xedit-cli Phase 1 Design

## Goal

Design the first real implementation phase for `xedit-cli` as a comprehensive long-term wrapper around upstream xEdit, while keeping Phase 1 narrowly focused on conflict reading.

The Phase 1 deliverable is not a giant export tool and not a write-capable patching system. It is a safe, queryable, read-only conflict-reading workflow that can scale to Bethesda Game Studios load orders containing very large numbers of records.

## Product Position

`xedit-cli` is the primary public surface for xEdit automation in this repo.

It should:

- keep upstream xEdit external
- drive xEdit via its supported command-line and Pascal scripting surfaces
- own the report schema and query model at the wrapper layer
- act as the infrastructure/tool layer beneath workflow skills such as `conflict-auditor`

It should not:

- recompile or fork xEdit
- expose raw giant dumps as the primary user or agent experience
- jump straight to write-capable mutation or patch generation

## Upstream xEdit Constraint Model

Research in the official docs and upstream repo established:

1. xEdit supports external automation through command-line switches and Pascal scripts.
2. `-script`, `-autoload`, `-autoexit`, path overrides, and log-path overrides are viable wrapper-facing controls.
3. xEdit already exposes conflict-related APIs to Pascal scripts.
4. Built-in conflict-display modes are useful, but they are not a clean machine-readable contract by themselves.
5. xEdit is fundamentally GUI-first, so the wrapper must own the durable automation contract.

## Core Architecture

Phase 1 should use a `script-owned report wrapper` architecture.

### Layers

1. `xedit-cli`
   Public tool surface and orchestration layer.

2. `Pascal report script`
   Wrapper-owned read-only xEdit script that extracts conflict information from xEdit's internal APIs.

3. `Intermediate report`
   Stable script output produced by the Pascal layer.

4. `SQLite artifact store`
   Wrapper-owned run-scoped store for indexed conflict data.

5. `Workflow consumers`
   Skills such as `conflict-auditor` that interpret tool output into curator decisions.

## Why SQLite

Large BGS game data sets can contain tens or hundreds of thousands of records. A monolithic JSON output is both operationally clumsy and dangerous for agent context limits.

SQLite is recommended as the internal report store because it:

- supports large result sets safely
- enables drilldown instead of bulk dump behavior
- allows compact command outputs backed by indexed queries
- keeps the wrapper, not the agent, responsible for scale handling

SQLite is not the primary user-facing output. It is the internal artifact/query layer.

## Information Architecture

Phase 1 should borrow xEdit's presentation logic rather than its GUI widgets.

The important xEdit pattern is `progressive disclosure`:

- tree/navigation first
- scoped comparison second
- references/dependencies as focused follow-ups
- explicit filters and noise reduction
- no monolithic dump of everything at once

### Agent-facing model

1. `Navigation layer`
   Compact conflict index with files, groups, counts, and hotspots.

2. `Inspection layer`
   One chosen record or small chosen set shown as a side-by-side compare.

3. `Projection layer`
   Task-shaped outputs such as conflict summary or reference slice.

## Phase 1 Public Commands

Phase 1 should expose a task-oriented command surface.

- `xedit-cli doctor env`
  Validate executable path, game mode, plugins source, script path, and other preconditions.
- `xedit-cli conflicts index`
  Build a compact read-only conflict index for the chosen scan scope.
- `xedit-cli conflicts inspect --record <id>`
  Show a scoped compare view for a chosen record.
- `xedit-cli conflicts refs --record <id>`
  Show a narrow dependency or referenced-by slice if supported in Phase 1.
- `xedit-cli conflicts summary`
  Present a compact human-oriented summary over the current or selected run.

Internal or later commands may support more generic script execution, but that should not be the public headline in Phase 1.

## Execution Model

### Phase 1 run flow

1. Resolve game, paths, and xEdit executable.
2. Run environment preflight.
3. Materialize or select the wrapper-owned Pascal report script.
4. Launch xEdit externally with controlled arguments.
5. Wait for script completion.
6. Read the script's intermediate report.
7. Ingest the report into SQLite.
8. Serve compact command outputs from SQLite-backed queries.

### Preferred xEdit launch pattern

The recommended backend pattern is based on repo and docs evidence:

- `-script`
- `-autoload`
- `-autoexit`
- `-R:` for a controlled log path
- `-S:` for script path override when needed
- path overrides like `-D:` and `-P:` for deterministic environment control

## Script vs Wrapper Responsibilities

### Pascal script should do

- use xEdit-native APIs to enumerate conflicts and override chains
- stay read-only
- emit a stable intermediate report

### Wrapper should do

- path and environment resolution
- run management
- report ingestion
- SQLite schema ownership
- compact result rendering
- log capture and timeout/error handling

This split keeps schema evolution in the wrapper rather than embedding too much long-term contract logic in Pascal.

## Phase 1 Artifact Model

Each scan should create a run-scoped artifact set.

Recommended core SQLite tables:

- `runs`
- `files`
- `groups`
- `records`
- `overrides`
- `inspections`
- `refs` if Phase 1 includes dependency slices

Recommended additional artifacts:

- xEdit session log
- raw intermediate report for debugging

## Output Strategy

The wrapper should not emit one giant full-data output by default.

### Instead it should emit

1. compact summaries
2. scoped drilldowns
3. stable record identifiers for follow-up inspection

### The Phase 1 report should at least cover

- scanned game/mode
- load-order source
- files/plugins scanned
- group/signature counts
- indexed conflict records
- override chain or winning-override context where feasible
- lightweight next-action hints such as inspect further, likely ordering candidate, or likely patch candidate

## Boundary With conflict-auditor

`xedit-cli` is the infrastructure layer.

`conflict-auditor` is the workflow/policy layer.

That means:

- `xedit-cli` answers what conflict data exists and how to query it
- `conflict-auditor` answers what a curator should do next with that information

The skill should wrap the tool, not duplicate the tool's storage or extraction logic.

## What Stays Out Of Phase 1

- write-capable patch generation
- general plugin mutation
- cleaning as the main public workflow
- archive/file conflict reasoning as a full feature
- metadata integrations as a dependency for the first real slice
- save-safety automation
- localization workflows
- release/changelog workflows

## Risks And Anti-Patterns

### Avoid

- giant monolithic JSON dumps
- log scraping as the primary stable contract
- exposing generic script-running as the main public UX too early
- treating xEdit conflict-display UI modes as if they were already a complete CLI contract
- adding write automation before read-only conflict inspection is proven

### Major risks

- unattended script runs may still be destabilized by bad environment assumptions unless preflight is strong
- script-mode exit codes may not be reliable enough to be the only success signal
- conflict data breadth can overwhelm agents unless the wrapper enforces scoped drilldown

## Success Criteria

Phase 1 is successful when:

1. `xedit-cli` can perform environment validation for a chosen game/toolchain context.
2. `xedit-cli conflicts index` can produce a compact indexed conflict run without mutating anything.
3. `xedit-cli conflicts inspect` can show a scoped record comparison suitable for curator decision-making.
4. The wrapper scales through SQLite-backed drilldown rather than giant raw dumps.
5. `conflict-auditor` can later consume this surface cleanly instead of inventing its own xEdit integration path.
