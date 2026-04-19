# xedit-cli Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first usable `xedit-cli` workflow as a safe, read-only conflict-reading tool that wraps upstream xEdit via Pascal scripts and serves compact drilldown results through a SQLite-backed artifact store.

**Architecture:** Keep xEdit external and use a wrapper-owned Pascal report script plus a wrapper-owned ingestion/query layer. Phase 1 should expose environment preflight, conflict indexing, and scoped record inspection while deliberately excluding write-capable automation, cleaning-first workflows, and broad metadata coupling.

**Tech Stack:** PowerShell, SQLite, Markdown, xEdit Pascal scripts, Git

---

### Task 1: Expand The xedit-cli Contract And Roadmap References

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `mcps/xedit-readonly.md`
- Modify: `skills/conflict-auditor/SKILL.md`
- Test: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects Phase 1 contract signals such as:

- `tools/xedit-cli/README.md` mentions conflict indexing, inspection, and SQLite-backed drilldown
- `tools/xedit-cli/CONTRACT.md` includes command-level sections for `doctor env`, `conflicts index`, and `conflicts inspect`
- `mcps/xedit-readonly.md` describes MCP as a later or supporting integration around the primary `xedit-cli` surface
- `skills/conflict-auditor/SKILL.md` references `xedit-cli` as its tool layer for read-only conflict inspection

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the existing spec files are still too shallow for the Phase 1 design.

**Step 3: Write minimal implementation**

Update the spec docs so they reflect the approved Phase 1 design, including:

- `xedit-cli` as the primary public surface
- SQLite as an internal artifact/query layer
- progressive-disclosure outputs rather than giant dumps
- clear boundary between `xedit-cli`, `conflict-auditor`, and later MCP usage

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md mcps/xedit-readonly.md skills/conflict-auditor/SKILL.md tests/bootstrap/verify-specs.ps1
git commit -m "docs: define xedit-cli phase 1 contract"
```

### Task 2: Create Script And Artifact Layout Skeleton

**Files:**
- Create: `tests/xedit-cli/verify-layout.ps1`
- Create: `tools/xedit-cli/scripts/README.md`
- Create: `tools/xedit-cli/schema/README.md`
- Create: `tools/xedit-cli/fixtures/README.md`
- Create: `tools/xedit-cli/output/README.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/verify-layout.ps1` to require:

- `tools/xedit-cli/scripts/README.md`
- `tools/xedit-cli/schema/README.md`
- `tools/xedit-cli/fixtures/README.md`
- `tools/xedit-cli/output/README.md`

And check that these READMEs clearly distinguish:

- Pascal scripts
- SQLite/report schema
- fixtures/sample outputs
- wrapper-owned run artifacts

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/verify-layout.ps1`
Expected: FAIL with missing file errors.

**Step 3: Write minimal implementation**

Create the directory skeleton and README contracts for:

- script location
- schema location
- fixtures location
- output/artifact location

Keep the descriptions concise and phase-specific.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/verify-layout.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/verify-layout.ps1 tools/xedit-cli/scripts/README.md tools/xedit-cli/schema/README.md tools/xedit-cli/fixtures/README.md tools/xedit-cli/output/README.md
git commit -m "chore: scaffold xedit-cli phase 1 layout"
```

### Task 3: Define The Phase 1 SQLite Schema And Intermediate Report Contract

**Files:**
- Create: `tests/xedit-cli/verify-schema.ps1`
- Create: `tools/xedit-cli/schema/intermediate-report.md`
- Create: `tools/xedit-cli/schema/sqlite-schema.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/verify-schema.ps1` to require:

- `tools/xedit-cli/schema/intermediate-report.md`
- `tools/xedit-cli/schema/sqlite-schema.md`

And verify stable headings for:

- scan metadata
- file/plugin rows
- group/signature summaries
- record/conflict index rows
- override chain rows
- inspection detail strategy

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/verify-schema.ps1`
Expected: FAIL with missing schema docs.

**Step 3: Write minimal implementation**

Document:

- what the Pascal script emits
- what the wrapper ingests
- recommended SQLite tables for Phase 1
- what is stored as index vs on-demand detail

Keep the schema concrete enough to implement against, but do not over-specify future write workflows.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/verify-schema.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/verify-schema.ps1 tools/xedit-cli/schema/intermediate-report.md tools/xedit-cli/schema/sqlite-schema.md
git commit -m "docs: define xedit-cli phase 1 schema"
```

### Task 4: Add The Phase 1 Pascal Script Contract

**Files:**
- Create: `tests/xedit-cli/verify-script-contract.ps1`
- Create: `tools/xedit-cli/scripts/conflicts-index.pas.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/verify-script-contract.ps1` to require a script contract doc that covers:

- read-only behavior
- xEdit launch assumptions
- required lifecycle hooks (`Initialize`, `Process`, `Finalize` as applicable)
- expected intermediate report fields
- prohibited mutation APIs or behaviors

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/verify-script-contract.ps1`
Expected: FAIL because the contract doc does not yet exist.

**Step 3: Write minimal implementation**

Create a script contract document for the first conflict-indexing Pascal script.

This is still a spec document, not the script implementation itself.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/verify-script-contract.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/verify-script-contract.ps1 tools/xedit-cli/scripts/conflicts-index.pas.md
git commit -m "docs: define xedit-cli script contract"
```

### Task 5: Implement Environment Preflight Command Skeleton

**Files:**
- Create: `tests/xedit-cli/doctor-env.test.ps1`
- Create: `tools/xedit-cli/bin/xedit-cli.ps1`
- Create: `tools/xedit-cli/lib/common.ps1`
- Create: `tools/xedit-cli/lib/doctor-env.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/doctor-env.test.ps1` to verify that:

- `tools/xedit-cli/bin/xedit-cli.ps1 doctor env` accepts a minimal set of parameters or config assumptions
- it fails with a clear non-zero result when required xEdit path/game mode inputs are missing
- it emits a compact summary instead of dumping environment noise

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/doctor-env.test.ps1`
Expected: FAIL because the command skeleton does not yet exist.

**Step 3: Write minimal implementation**

Implement a narrow command skeleton that:

- parses `doctor env`
- resolves basic input options
- validates presence of xEdit executable path and game mode inputs
- prints a compact preflight summary

Do not implement full conflict scanning yet.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/doctor-env.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/doctor-env.test.ps1 tools/xedit-cli/bin/xedit-cli.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/doctor-env.ps1
git commit -m "feat: add xedit-cli doctor env skeleton"
```

### Task 6: Implement Conflict Index Command Skeleton With Fixture Ingestion

**Files:**
- Create: `tests/xedit-cli/conflicts-index.test.ps1`
- Create: `tools/xedit-cli/lib/conflicts-index.ps1`
- Create: `tools/xedit-cli/lib/sqlite-store.ps1`
- Create: `tools/xedit-cli/fixtures/sample-conflicts-report.txt`

**Step 1: Write the failing test**

Create `tests/xedit-cli/conflicts-index.test.ps1` to verify that:

- `xedit-cli conflicts index` can ingest a sample intermediate report fixture
- it creates a SQLite-backed run artifact
- it prints a compact index summary rather than a giant dump
- it records core entities such as run metadata, plugins/files, and record index rows

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/conflicts-index.test.ps1`
Expected: FAIL because the command and ingestion/store layers do not yet exist.

**Step 3: Write minimal implementation**

Implement a fixture-backed skeleton for:

- `conflicts index`
- SQLite artifact creation
- minimal ingestion path from a sample report fixture
- compact summary output

This task should prove the wrapper-owned artifact model before live xEdit integration.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/conflicts-index.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/conflicts-index.test.ps1 tools/xedit-cli/lib/conflicts-index.ps1 tools/xedit-cli/lib/sqlite-store.ps1 tools/xedit-cli/fixtures/sample-conflicts-report.txt
git commit -m "feat: add xedit-cli conflict index skeleton"
```

### Task 7: Implement Scoped Inspection Command Skeleton

**Files:**
- Create: `tests/xedit-cli/conflicts-inspect.test.ps1`
- Create: `tools/xedit-cli/lib/conflicts-inspect.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/conflicts-inspect.test.ps1` to verify that:

- `xedit-cli conflicts inspect --record <id>` queries a previously indexed run
- it emits a scoped compare-like result rather than the whole dataset
- it fails cleanly when the record ID is unknown

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/conflicts-inspect.test.ps1`
Expected: FAIL because the inspection command does not yet exist.

**Step 3: Write minimal implementation**

Implement a narrow inspection command that queries the SQLite store and renders one compact record-level view.

Use fixture-backed data first.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/conflicts-inspect.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/conflicts-inspect.test.ps1 tools/xedit-cli/lib/conflicts-inspect.ps1
git commit -m "feat: add xedit-cli scoped inspection skeleton"
```

### Task 8: Add Live xEdit Invocation Plan And Safety Notes

**Files:**
- Create: `tests/xedit-cli/verify-live-integration-plan.ps1`
- Create: `tools/xedit-cli/live-integration.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/verify-live-integration-plan.ps1` to require a live-integration doc covering:

- xEdit launch arguments for Phase 1
- report-script execution flow
- log capture and timeout handling
- read-only constraints
- known unknowns and fallback behavior

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/verify-live-integration-plan.ps1`
Expected: FAIL because the live integration plan doc does not yet exist.

**Step 3: Write minimal implementation**

Document the Phase 1 live-integration path clearly enough that a later task can replace fixture-backed behavior with live xEdit execution safely.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/verify-live-integration-plan.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/verify-live-integration-plan.ps1 tools/xedit-cli/live-integration.md
git commit -m "docs: define xedit-cli live integration path"
```
