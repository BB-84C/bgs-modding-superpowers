# xedit-cli Step 1 Module Selection Hooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a no-fork xEdit hook path so `xedit-cli` can automate the Module Selection dialog using MO2-backed load order plus explicit `load all`, `load only`, and `load exclude` policies.

**Architecture:** `xedit-cli` stays the external orchestrator and launches xEdit through the existing MO-aware seam. A new native `hook.dll` is loaded in-process, reads a small selection policy from environment variables, detects `TfrmModuleSelect`, applies the requested selection against the MO2-backed module tree, and confirms the dialog while reporting success or failure back to the CLI. Because Delphi Community Edition on this machine does not support command-line compilation, native DLL tasks use a manual IDE build checkpoint: the assistant prepares code and expected outputs, the user clicks Build in Delphi, then the assistant resumes verification and debugging.

**Tech Stack:** PowerShell, native Windows hook DLL (Delphi/VCL-compatible preferred for direct xEdit form interaction), environment-variable session contract, xEdit VCL forms, Delphi IDE manual builds, Git

---

### Task 1: Document The Step 1 Hook Contract

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Modify: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects:

- a step-1 hook bridge for Module Selection
- `--load-mode all|only|exclude`
- repeatable `--plugin` args for `only` and `exclude`
- MO2 as the source of truth for full plugin order
- a no-fork `hook.dll` bridge loaded through the MO seam

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the docs do not yet describe the step-1 hook contract.

**Step 3: Write minimal implementation**

Update the docs so they clearly describe:

- the step-1 hook goal
- `--load-mode`
- repeatable `--plugin`
- MO2-backed selection baseline
- no-fork hook loading

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md tools/xedit-cli/live-integration.md tests/bootstrap/verify-specs.ps1
git commit -m "docs: define xedit step1 hook contract"
```

### Task 2: Add CLI-Side Load-Mode Contract Validation

**Files:**
- Create: `tests/xedit-cli/module-selection-contract.test.ps1`
- Modify: `tools/xedit-cli/lib/common.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/module-selection-contract.test.ps1` to verify:

- `process launch` accepts `--load-mode all`
- `process launch` rejects missing `--load-mode`
- `--load-mode all` rejects any `--plugin`
- `--load-mode only` requires one or more `--plugin`
- `--load-mode exclude` requires one or more `--plugin`
- duplicate `--plugin` args are deduplicated
- plugin names are treated as exact filenames for later hook use

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/module-selection-contract.test.ps1`
Expected: FAIL because `xedit-cli` does not yet understand `--load-mode` or repeatable `--plugin`.

**Step 3: Write minimal implementation**

Implement shared helpers for:

- repeatable `--plugin` parsing
- `--load-mode` validation
- normalized hook selection policy objects

Keep this task limited to CLI-side validation and parsing.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/module-selection-contract.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/module-selection-contract.test.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/process.ps1 tools/xedit-cli/bin/xedit-cli.ps1
git commit -m "feat: add xedit module selection cli contract"
```

### Task 3: Add CLI-Side Hook Session And Environment Contract

**Files:**
- Create: `tests/xedit-cli/hook-session.test.ps1`
- Create: `tools/xedit-cli/lib/hook-session.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/hook-session.test.ps1` to verify that:

- `process launch` derives environment variables for hook policy
- `all` produces a minimal policy payload
- `only` and `exclude` produce deduplicated plugin lists
- the environment contract does not attempt to reproduce the full MO2 plugin list
- the CLI can surface hook-session IDs/paths or equivalent run identity if needed for diagnostics

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/hook-session.test.ps1`
Expected: FAIL because no hook-session contract exists yet.

**Step 3: Write minimal implementation**

Add CLI-side helpers that:

- build hook environment variables
- pass selection policy through launch
- keep existing real launcher normalization intact

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/hook-session.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/hook-session.test.ps1 tools/xedit-cli/lib/hook-session.ps1 tools/xedit-cli/lib/process.ps1 tools/xedit-cli/bin/xedit-cli.ps1
git commit -m "feat: add xedit hook session environment contract"
```

### Task 4: Add The Hook DLL Skeleton And Handshake

**Files:**
- Create: `tools/xedit-hook-bridge/README.md`
- Create: `tools/xedit-hook-bridge/src/xEditHookBridge.dpr`
- Create: `tools/xedit-hook-bridge/src/HookMain.pas`
- Create: `tools/xedit-hook-bridge/src/HookSession.pas`
- Create: `tools/xedit-hook-bridge/src/HookStatus.pas`

**Step 1: Write the failing test**

Write a simple handshake test in the repo docs or a lightweight PowerShell verification script that expects:

- the hook DLL exports `Init`
- it can read the expected environment variables
- it can write a status marker proving it loaded

If a compiler is not available, the failing test should capture that as a tooling blocker before any deeper implementation.

**Step 2: Run test to verify it fails**

Run the chosen handshake verification command.
Expected: FAIL because the hook DLL project does not exist yet, or because no supported compiler/toolchain is available.

**Step 3: Write minimal implementation**

Create the DLL project skeleton and implement:

- exported `Init`
- hook-session environment read
- simple load-status reporting

Do not implement module-tree manipulation yet.

**Step 4: Re-run the verification**

Run the same handshake verification command.
Expected:
- If a compiler is available: PASS
- If Delphi Community Edition remains IDE-only for this machine: explicit tooling blocker captured in docs/output

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-hook-bridge
git commit -m "feat: add xedit hook bridge skeleton"
```

### Task 5: Implement `--load-mode all` Auto-Confirm

**Files:**
- Modify: `tools/xedit-hook-bridge/src/HookMain.pas`
- Modify: `tools/xedit-hook-bridge/src/HookSession.pas`
- Modify: `tools/xedit-hook-bridge/src/HookStatus.pas`
- Create: `tests/xedit-cli/module-selection-all.integration.ps1`
- Modify: `tools/xedit-hook-bridge/README.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/module-selection-all.integration.ps1` to verify that a hook-enabled xEdit launch can:

- detect Module Selection
- auto-confirm the MO2-backed active set for `--load-mode all`
- report success back to `xedit-cli`

This is expected to be a real integration test, not a pure fixture test.

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/module-selection-all.integration.ps1`
Expected: FAIL because the hook does not yet automate the dialog.

**Step 3: Write minimal implementation**

Implement the smallest viable behavior:

- detect the xEdit module-selection form
- if policy is `all`, confirm the current selection without changing it
- write explicit success/failure diagnostics

**Step 4: Prepare the manual Delphi build loop**

Update `tools/xedit-hook-bridge/README.md` with a “one click” build checkpoint that tells the user exactly:

- which Delphi project to open
- which target platform/configuration to select
- which Build button/menu item to click
- where the resulting DLL must appear

Also add a repo-side verification command that the assistant can run after the user clicks Build.

**Step 5: User build checkpoint**

The assistant stops and asks the user to:

- open the hook DLL project in Delphi CE
- click `Build`

If the build fails, the user may need to provide one screenshot or one copied error block.

**Step 6: Run post-build verification**

Run: `pwsh -File tests/xedit-cli/module-selection-all.integration.ps1`
Expected: PASS after the manual Delphi build succeeds.

### Task 6: Implement `only` And `exclude`

**Files:**
- Create: `tests/xedit-cli/module-selection-subset.integration.ps1`
- Modify: `tools/xedit-hook-bridge/src/HookMain.pas`
- Modify: `tools/xedit-hook-bridge/src/HookSession.pas`
- Modify: `tools/xedit-hook-bridge/src/HookStatus.pas`
- Modify: `tools/xedit-hook-bridge/README.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/module-selection-subset.integration.ps1` to verify:

- `only` selects the requested roots in MO2 order
- required masters remain selected
- `exclude` unchecks requested plugins when legal
- blocked exclusions are reported clearly when dependencies force the plugin back on

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/module-selection-subset.integration.ps1`
Expected: FAIL because subset policies are not implemented yet.

**Step 3: Write minimal implementation**

Implement policy application against `TfrmModuleSelect`:

- match filenames from the visible module tree
- apply `only` or `exclude`
- confirm the dialog
- capture final selected modules and forced dependencies

**Step 4: Update manual Delphi build instructions if needed**

Keep the same “open project, click Build” workflow, only adjusting instructions if the project layout changes.

**Step 5: User build checkpoint**

The assistant stops and asks the user to rebuild the DLL in Delphi CE.

**Step 6: Run post-build verification**

Run: `pwsh -File tests/xedit-cli/module-selection-subset.integration.ps1`
Expected: PASS after the manual Delphi build succeeds.

### Task 7: Real Verification Against MO2-Backed xEdit

**Files:**
- Test: `tools/xedit-cli/bin/xedit-cli.ps1`
- Test: `tools/xedit-hook-bridge/src/*`
- Modify: `tools/xedit-hook-bridge/README.md` if the real workflow needs clarification

**Step 1: Verify `load all` on a real MO2-backed launcher**

Run the real hook-enabled xEdit launch against the user’s MO2/xEdit setup with `--load-mode all`.

Expected: the Module Selection dialog is automatically confirmed and xEdit proceeds without manual clicking.

**Step 2: Verify `only` on a small real subset**

Run a real launch with a tiny safe subset such as one plugin plus masters.

Expected: only the requested roots plus required masters remain selected.

**Step 3: Verify `exclude` on a safe real subset**

Run a real launch excluding one or two non-master plugins.

Expected: exclusions apply unless xEdit dependency rules force re-selection, in which case the CLI reports it clearly.

Recommended first Fallout 4 probe for the current branch state:

- safe exclude target: `CraftingTools.esp`
- dependency-blocked exclude target: `ArmorKeywords.esm` while `RaiderOverhaul.esp` remains enabled

The purpose of this real probe is to resolve any remaining ambiguity between hook behavior and synthetic fixture behavior for `exclude`.

**Step 4: Verify cleanup and failure reporting**

Confirm that the CLI reports hook load failure, selection timeout, or blocked exclusions clearly when they occur.

**Step 5: User build checkpoints as needed**

If any native hook changes were required during verification, the assistant pauses for the same Delphi CE “click Build” step before re-running verification.

**Step 6: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli tools/xedit-cli tools/xedit-hook-bridge docs/plans
git commit -m "feat: add xedit module selection hook bridge"
```
