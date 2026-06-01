# xedit-cli Explicit Game-Mode Launch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `xedit-cli` launch supported xEdit targets through explicit game-mode arguments so Fallout 4, Skyrim, and Starfield launcher forms work without relying on executable-name inference as the primary contract.

**Architecture:** Keep `--launcher-path` as the caller input and make `--game-mode` the explicit intent signal. Normalize direct executables and simple batch wrappers into a concrete xEdit command plus mapped mode argument, then reuse the existing PID-resolution and lifecycle flow on that normalized launch command.

**Tech Stack:** PowerShell, Windows process inspection, xEdit launcher scripts, Markdown, Git

---

### Task 1: Update The Launcher Contract For Explicit Game Modes

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Test: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects:

- `--game-mode` as part of launcher-driven process launch
- explicit xEdit mode arguments as the preferred control surface
- support for direct `.exe` launchers and simple `.bat/.cmd` wrappers

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the docs do not yet describe explicit game-mode launch as the main contract.

**Step 3: Write minimal implementation**

Update the docs so they clearly say:

- launcher-driven commands require `--game-mode`
- the CLI maps game modes to xEdit args like `-FO4`, `-TES5`, and `-SF1`
- direct executables and simple wrappers are normalized to explicit launch commands
- complex wrappers fail closed

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md tools/xedit-cli/live-integration.md tests/bootstrap/verify-specs.ps1
git commit -m "docs: define explicit xedit game mode launch contract"
```

### Task 2: Add Game-Mode Mapping And Doctor Env Validation

**Files:**
- Modify: `tests/xedit-cli/doctor-env.test.ps1`
- Modify: `tools/xedit-cli/lib/common.ps1`
- Modify: `tools/xedit-cli/lib/doctor-env.ps1`

**Step 1: Write the failing test**

Extend `tests/xedit-cli/doctor-env.test.ps1` to verify:

- `doctor env` rejects missing `--game-mode`
- supported game modes map cleanly for at least `Fallout4`, `Skyrim`, and `Starfield`
- unsupported game modes fail cleanly
- `.exe`, `.bat`, and `.cmd` launcher inputs remain accepted when paired with a valid game mode

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/doctor-env.test.ps1`
Expected: FAIL because mode mapping and explicit game-mode validation are not implemented yet.

**Step 3: Write minimal implementation**

Add a shared game-mode mapping helper in `tools/xedit-cli/lib/common.ps1` and update `doctor env` to use it.

Keep the current summary compact.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/doctor-env.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/doctor-env.test.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/doctor-env.ps1
git commit -m "feat: add explicit xedit game mode validation"
```

### Task 3: Normalize Launcher Commands For Process Launch

**Files:**
- Modify: `tests/xedit-cli/process-lifecycle.test.ps1`
- Modify: `tools/xedit-cli/lib/common.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`

**Step 1: Write the failing test**

Extend `tests/xedit-cli/process-lifecycle.test.ps1` so it verifies:

- `process launch` requires `--game-mode`
- direct `.exe` launchers receive the mapped explicit mode arg
- simple `.bat/.cmd` wrappers are normalized and launched with the mapped explicit mode arg
- unsupported wrapper shapes fail closed

Use harmless launcher fixtures rather than real game tools for the automated test.

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/process-lifecycle.test.ps1`
Expected: FAIL because process launch does not yet normalize explicit game-mode commands.

**Step 3: Write minimal implementation**

Implement:

- launcher normalization helpers
- explicit mode-arg appending
- direct `.exe` normalized launch
- simple wrapper parsing and resolution
- fail-closed rejection for unsupported wrapper complexity

Keep `status`, `wait`, and `stop` behavior intact except for any necessary shared validation updates.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/process-lifecycle.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/process-lifecycle.test.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/process.ps1 tools/xedit-cli/bin/xedit-cli.ps1
git commit -m "feat: normalize xedit launcher commands by game mode"
```

### Task 4: Verify Real Fallout 4, Skyrim, And Starfield Launchers

**Files:**
- Test: `tools/xedit-cli/bin/xedit-cli.ps1`

**Step 1: Run the real Fallout 4 verification**

Run:

```powershell
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 doctor env --launcher-path "B:\WastelandBlues 2.0\Stock Game\Fallout 4\Tools\FO4Edit\runFO4EditCN.bat" --game-mode Fallout4
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process launch --launcher-path "B:\WastelandBlues 2.0\Stock Game\Fallout 4\Tools\FO4Edit\runFO4EditCN.bat" --game-mode Fallout4
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process status --xedit-pid <pid>
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process stop --xedit-pid <pid>
```

Expected: PASS with real PID reporting and clean stop.

**Step 2: Run the real Skyrim verification**

Run:

```powershell
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 doctor env --launcher-path "C:\softwares\TES Skyrim JL V3\Mod Organizer 2\Stock Game\Skyrim Special Edition\Tools\TES5Edit\runTES5EditCN.bat" --game-mode Skyrim
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process launch --launcher-path "C:\softwares\TES Skyrim JL V3\Mod Organizer 2\Stock Game\Skyrim Special Edition\Tools\TES5Edit\runTES5EditCN.bat" --game-mode Skyrim
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process status --xedit-pid <pid>
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process stop --xedit-pid <pid>
```

Expected: PASS with real PID reporting and clean stop.

**Step 3: Run the real Starfield verification**

Run:

```powershell
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 doctor env --launcher-path "D:\SteamLibrary\steamapps\common\Starfield\Tools\xEdit\SF1Edit64.exe" --game-mode Starfield
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process launch --launcher-path "D:\SteamLibrary\steamapps\common\Starfield\Tools\xEdit\SF1Edit64.exe" --game-mode Starfield
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process status --xedit-pid <pid>
pwsh -File tools/xedit-cli/bin/xedit-cli.ps1 process stop --xedit-pid <pid>
```

Expected: PASS with real PID reporting and clean stop.

**Step 4: Verify no extra xEdit instances remain**

Run a process listing for xEdit-like executables and confirm only pre-existing user-owned instances remain.

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli tools/xedit-cli docs/plans
git commit -m "feat: add explicit xedit game mode launch support"
```
