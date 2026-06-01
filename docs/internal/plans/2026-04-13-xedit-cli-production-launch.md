# xedit-cli Production Launch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `xedit-cli` launch xEdit itself from a caller-provided launcher path, manage multiple live xEdit processes by raw PID, and add a first live launcher-driven indexing path without requiring manual xEdit startup.

**Architecture:** Keep `xedit-cli` as the wrapper-owned orchestration layer. Add a small process-management library for launching and monitoring xEdit by raw PID, then extend `doctor env` and `conflicts index` to use launcher-path inputs and wrapper-controlled live runs while preserving the existing fixture-backed test path.

**Tech Stack:** PowerShell, Windows process inspection, SQLite, xEdit launcher scripts, Markdown, Git

---

### Task 1: Update The Contract For Launcher-Driven Production Usage

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Test: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects launcher-driven production signals such as:

- `tools/xedit-cli/README.md` mentions launcher paths and PID-based process handling
- `tools/xedit-cli/CONTRACT.md` includes `process launch`, `process status`, `process wait`, and `process stop`
- `tools/xedit-cli/live-integration.md` mentions caller-provided launcher paths and raw PID outputs

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the production-launch contract is not documented yet.

**Step 3: Write minimal implementation**

Update the docs so the contract clearly states:

- the CLI launches xEdit itself
- callers pass a launcher path in
- raw PIDs are the addressing model
- MO2 discovery stays outside the CLI

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md tools/xedit-cli/live-integration.md tests/bootstrap/verify-specs.ps1
git commit -m "docs: define xedit-cli production launch contract"
```

### Task 2: Add Launcher-Aware Doctor Env Validation

**Files:**
- Modify: `tests/xedit-cli/doctor-env.test.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`
- Modify: `tools/xedit-cli/lib/common.ps1`
- Modify: `tools/xedit-cli/lib/doctor-env.ps1`

**Step 1: Write the failing test**

Extend `tests/xedit-cli/doctor-env.test.ps1` to verify that:

- `doctor env` requires `--launcher-path` and `--game-mode`
- it accepts a batch launcher path as a valid production input
- it optionally validates `--xedit-pid` when provided
- it rejects missing or dead PIDs cleanly

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/doctor-env.test.ps1`
Expected: FAIL because the command still expects `--xedit-path` rather than launcher semantics.

**Step 3: Write minimal implementation**

Update `doctor env` to:

- parse `--launcher-path`
- recognize `.bat`, `.cmd`, and `.exe`
- keep the compact summary format
- validate optional `--xedit-pid` through Windows process inspection

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/doctor-env.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/doctor-env.test.ps1 tools/xedit-cli/bin/xedit-cli.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/doctor-env.ps1
git commit -m "feat: add launcher-aware doctor env"
```

### Task 3: Add XEdit Process Lifecycle Commands

**Files:**
- Create: `tests/xedit-cli/process-lifecycle.test.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`
- Modify: `tools/xedit-cli/lib/common.ps1`
- Create: `tools/xedit-cli/lib/process.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/process-lifecycle.test.ps1` to verify that:

- `process launch --launcher-path <path>` starts a safe test process and returns a PID
- `process status --xedit-pid <pid>` reports a live process
- `process wait --xedit-pid <pid> --timeout-seconds <n>` waits or times out cleanly
- `process stop --xedit-pid <pid>` terminates the chosen process

Use a harmless batch-file fixture for the automated test.

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/process-lifecycle.test.ps1`
Expected: FAIL because the process lifecycle commands do not exist yet.

**Step 3: Write minimal implementation**

Implement:

- launcher-path based process start
- PID extraction and compact summary output
- process status lookup by PID
- wait with timeout support
- explicit stop by PID

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/process-lifecycle.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/process-lifecycle.test.ps1 tools/xedit-cli/bin/xedit-cli.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/process.ps1
git commit -m "feat: add xedit-cli process lifecycle commands"
```

### Task 4: Add Live Conflict Index Launch Path

**Files:**
- Modify: `tests/xedit-cli/conflicts-index.test.ps1`
- Modify: `tools/xedit-cli/lib/conflicts-index.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`
- Modify: `tools/xedit-cli/live-integration.md`

**Step 1: Write the failing test**

Extend `tests/xedit-cli/conflicts-index.test.ps1` so it verifies that:

- live mode requires `--launcher-path`
- live mode creates run-scoped artifact paths before launch
- live mode reports the PID it launched
- live mode fails cleanly when the report file is missing or the launcher fails

Use a safe test launcher fixture for automation rather than the real FO4Edit launcher.

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/conflicts-index.test.ps1`
Expected: FAIL because the live launch path does not exist yet.

**Step 3: Write minimal implementation**

Implement a live launcher-driven branch in `conflicts index` that:

- builds run-scoped output paths
- launches xEdit through the caller-provided launcher path
- captures the PID used for the run
- waits for completion
- fails closed if the live report is not produced

Keep the existing fixture-backed ingestion path intact for deterministic test coverage.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/conflicts-index.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/conflicts-index.test.ps1 tools/xedit-cli/lib/conflicts-index.ps1 tools/xedit-cli/lib/process.ps1 tools/xedit-cli/live-integration.md
git commit -m "feat: add live xedit-cli conflict index launch path"
```

### Task 5: Verify Against A Real XEdit Launcher

**Files:**
- Test: `tools/xedit-cli/bin/xedit-cli.ps1`

**Step 1: Run the real preflight**

Run `doctor env` against the provided real launcher path.

Run: `pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 doctor env --launcher-path "B:\WastelandBlues 2.0\Stock Game\Fallout 4\Tools\FO4Edit\runFO4EditCN.bat" --game-mode Fallout4`
Expected: PASS with a compact launcher-aware summary.

**Step 2: Run the real process launch check**

Launch FO4Edit through the CLI and capture the PID.

Run: `pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process launch --launcher-path "B:\WastelandBlues 2.0\Stock Game\Fallout 4\Tools\FO4Edit\runFO4EditCN.bat" --game-mode Fallout4`
Expected: PASS with a real PID in the output.

**Step 3: Run the real process status check**

Run: `pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process status --xedit-pid <pid>`
Expected: PASS showing that the launched FO4Edit process is alive.

**Step 4: Run the real process cleanup**

Run: `pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process stop --xedit-pid <pid>`
Expected: PASS showing that the launched process was terminated intentionally.

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli tools/xedit-cli
git commit -m "feat: make xedit-cli launch xedit directly"
```
