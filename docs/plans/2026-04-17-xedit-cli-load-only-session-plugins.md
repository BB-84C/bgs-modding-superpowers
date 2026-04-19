# xedit-cli Load-Only Session Plugins Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current `all` / `only` / `exclude` launch semantics with a single load path that always materializes a session-scoped `plugins.txt`, passes it to xEdit through `-P:`, and uses the hook bridge only to auto-confirm `Module Selection` and emit diagnostics.

**Architecture:** Keep all implementation work inside the active worktree `D:\awesome-bgs-mod-master\.worktrees\xedit-step1-hooks`. Add one wrapper-owned helper for session plugin-file creation, update process launch so xEdit always receives a session `plugins.txt`, and shrink the hook bridge back to load-only behavior. Continue using root-level `.artifacts\mo2` as the real verification sandbox, but do not move this slice into `D:\TES5Edit-contrib`.

**Tech Stack:** PowerShell wrapper scripts, Delphi hook DLL, MO2 control-plane launch path, xEdit native `-P:` plugins file seam, Pester-style PowerShell tests, real sandbox verification under `.artifacts\mo2`.

---

### Task 1: Add a Wrapper-Owned Session Plugins Helper

**Files:**
- Create: `tools/xedit-cli/lib/session-plugins.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`
- Test: `tests/xedit-cli/session-plugins.test.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/session-plugins.test.ps1` with focused cases for:
- normalizing a caller-provided plugins file into a clean list
- deduplicating repeated plugin names
- rejecting an empty plugin list
- writing `plugins.txt` atomically inside a session directory

Example expectation shape:

```powershell
$result = New-XeditCliSessionPluginsFile -SessionPath $sessionPath -PluginLines @(
    '*ArmorKeywords.esm',
    '*RaiderOverhaul.esp',
    '*RaiderOverhaul.esp'
)

$written = Get-Content $result.PluginsFilePath
$written | Should -Be @('*ArmorKeywords.esm', '*RaiderOverhaul.esp')
```

**Step 2: Run the test to verify it fails**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/session-plugins.test.ps1
```

Expected: FAIL because the helper does not exist yet.

**Step 3: Write the minimal implementation**

Create `tools/xedit-cli/lib/session-plugins.ps1` with small helpers:
- resolve a caller file into normalized plugin lines
- derive plugin lines from the current profile when no caller file is provided
- write `plugins.txt.tmp` then rename to `plugins.txt`
- return the canonical session path object

Also dot-source the new file from `tools/xedit-cli/bin/xedit-cli.ps1`.

**Step 4: Run the test to verify it passes**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/session-plugins.test.ps1
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless the user explicitly asks for it.

### Task 2: Replace SelectionPolicy With Session Plugins Launch Input

**Files:**
- Modify: `tools/xedit-cli/lib/common.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`
- Modify: `tools/xedit-cli/lib/mo2-launch.ps1`
- Modify: `tools/xedit-cli/lib/hook-session.ps1`
- Test: `tests/xedit-cli/mo2-launch-adapter.test.ps1`
- Test: `tests/xedit-cli/hook-session.test.ps1`
- Test: `tests/xedit-cli/process-lifecycle.test.ps1`

**Step 1: Write the failing tests**

Add or update tests so they assert:
- `process launch` no longer requires `--load-mode`
- `process launch` optionally accepts `--plugins-file`
- wrapper always creates a session `plugins.txt`
- xEdit launch arguments always include `-P:<session plugins.txt>`
- hook session env no longer exports `XEDIT_CLI_HOOK_LOAD_MODE` or `XEDIT_CLI_HOOK_PLUGINS`

Example assertion shape:

```powershell
$launch = Invoke-XeditCliProcessLaunch -Arguments @(
  '--launcher-path', $launcher,
  '--game-mode', 'Fallout4',
  '--mo-profile', 'Default',
  '--plugins-file', $pluginsFile
)

$launch.LaunchArguments | Should -Contain ('-P:' + $launch.SessionPluginsFile)
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/hook-session.test.ps1
pwsh -NoProfile -File tests/xedit-cli/mo2-launch-adapter.test.ps1
```

Expected: FAIL because the current code still centers on `SelectionPolicy` and `--load-mode`.

**Step 3: Write the minimal implementation**

Implement these changes:
- in `common.ps1`, remove `Get-XeditCliNormalizedSelectionPolicy` and replace it with a plugins-file/source resolver
- in `process.ps1`, change `Invoke-XeditCliProcessLaunch` to require `--launcher-path` and `--game-mode`, accept optional `--plugins-file`, create the session plugins file, and stop parsing `--plugin` / `--load-mode`
- in `mo2-launch.ps1`, ensure the xEdit target arguments always include `-P:<session plugins.txt>`
- in `hook-session.ps1`, reduce environment variables to session identity and session path only, plus any remaining launch-only metadata that is still needed

**Step 4: Run the tests to verify they pass**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/hook-session.test.ps1
pwsh -NoProfile -File tests/xedit-cli/mo2-launch-adapter.test.ps1
pwsh -NoProfile -File tests/xedit-cli/process-lifecycle.test.ps1
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless the user explicitly asks for it.

### Task 3: Shrink the Hook Bridge Back to Load-Only Automation

**Files:**
- Modify: `tools/xedit-hook-bridge/src/HookMain.pas`
- Modify: `tools/xedit-hook-bridge/src/HookStatus.pas`
- Test: `tests/xedit-cli/module-selection-contract.test.ps1`
- Test: `tests/xedit-cli/module-selection-all.integration.ps1`

**Step 1: Write the failing test updates**

Update hook-facing contract tests so they expect:
- no model-layer subset semantics
- no `selection_method=model-layer`
- no `forced_dependencies`
- no `blocked_exclusions`
- hook status remains centered on detection, confirmation, and final selected modules

Example assertion shape:

```powershell
$status.selection_confirmed | Should -Be 'true'
$status.selected_modules | Should -Not -BeNullOrEmpty
$status.Values['selection_method'] | Should -BeNullOrEmpty
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/module-selection-contract.test.ps1
```

Expected: FAIL because the current hook still includes subset-era fields and adoption logic.

**Step 3: Write the minimal implementation**

In `HookMain.pas` and `HookStatus.pas`:
- remove model-layer result adoption
- remove subset-specific status plumbing
- keep only dialog detection, auto-confirm, heartbeat/checkpoint details, and final selected module evidence
- preserve the existing load-all dialog automation path

**Step 4: Run the tests to verify they pass**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/module-selection-contract.test.ps1
pwsh -NoProfile -File tests/xedit-cli/module-selection-all.integration.ps1
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless the user explicitly asks for it.

### Task 4: Replace the Real Subset Harness With a Session Plugins Harness

**Files:**
- Modify or replace: `tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1`
- Modify or delete: `tests/xedit-cli/mo2-sandbox-subset-real.test.ps1`
- Test against shared assets: `D:\awesome-bgs-mod-master\.artifacts\mo2`

**Step 1: Write the failing real test update**

Refactor the live harness so it verifies:
- a session directory is created
- a session `plugins.txt` is written
- xEdit is launched with `-P:<session plugins.txt>`
- hook auto-confirms `Module Selection`
- xEdit proceeds with the selected modules from that file-driven load set

Do not preserve `all` / `only` / `exclude` as named product semantics. Use one or more plugin-file scenarios instead.

**Step 2: Run the real harness to verify it fails for the old reason**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1 -AllowLiveSandbox -EnsureBridge -RestartMo2
```

Expected: FAIL because the current launch path still uses `SelectionPolicy` and does not always drive `-P:` from a session file.

**Step 3: Write the minimal implementation adjustments**

Update the harness to assert the new contract and preserve artifacts such as:
- `plugins.txt`
- `launch-request.json`
- `launch-response.json`
- `hook-status.txt`

If the file name becomes misleading after the rewrite, rename the test file and update any callers.

**Step 4: Run the real harness to verify it passes**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1 -AllowLiveSandbox -EnsureBridge -RestartMo2
```

Expected: PASS with evidence showing xEdit consumed the session `plugins.txt` and the hook auto-confirmed the selection dialog.

**Step 5: Commit**

Do not commit unless the user explicitly asks for it.

### Task 5: Rewrite Docs and Spec Checks Around a Single `load`

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Modify: `tests/bootstrap/verify-specs.ps1`
- Modify: `docs/plans/2026-04-17-xedit-cli-load-only-session-plugins-design.md` only if implementation details require a correction

**Step 1: Write the failing spec update**

Update `tests/bootstrap/verify-specs.ps1` so it expects:
- one `load` semantic instead of `all|only|exclude`
- session-scoped `plugins.txt`
- xEdit native `-P:` seam
- real profile `plugins.txt` remains untouched
- hook as auto-confirm plus diagnostics only

**Step 2: Run the spec check to verify it fails**

Run:

```powershell
pwsh -File tests/bootstrap/verify-specs.ps1
```

Expected: FAIL because the docs still describe `--load-mode all|only|exclude` and the subset experiment direction.

**Step 3: Write the minimal doc changes**

Bring all three docs into alignment:
- document a single `load` launch semantic
- describe session directory management and session `plugins.txt`
- document xEdit `-P:` as the native seam
- demote the hook to auto-confirm and diagnostics
- remove current repo claims that `only` / `exclude` are still the planned product contract

**Step 4: Run the spec check to verify it passes**

Run:

```powershell
pwsh -File tests/bootstrap/verify-specs.ps1
```

Expected: PASS.

**Step 5: Commit**

Do not commit unless the user explicitly asks for it.

### Task 6: Run Final End-to-End Verification For This Worktree Slice

**Files:**
- Verify current worktree only: `D:\awesome-bgs-mod-master\.worktrees\xedit-step1-hooks`
- Use shared sandbox assets under the repository root `.artifacts`

**Step 1: Run the local wrapper/test verification set**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/session-plugins.test.ps1
pwsh -NoProfile -File tests/xedit-cli/hook-session.test.ps1
pwsh -NoProfile -File tests/xedit-cli/mo2-launch-adapter.test.ps1
pwsh -NoProfile -File tests/xedit-cli/module-selection-contract.test.ps1
pwsh -File tests/bootstrap/verify-specs.ps1
```

Expected: PASS.

**Step 2: Run the real sandbox verification**

Run:

```powershell
pwsh -NoProfile -File tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1 -AllowLiveSandbox -EnsureBridge -RestartMo2
```

Expected: PASS with session-artifact evidence.

**Step 3: Verify output evidence manually**

Inspect the newest session directory under the temporary evidence root and confirm it contains at least:
- `plugins.txt`
- `launch-request.json`
- `launch-response.json`
- `hook-status.txt`

**Step 4: Summarize the verified state**

Record that this worktree now supports:
- no-fork xEdit launch
- wrapper-owned session plugin-file input
- hook-based auto-confirm for `Module Selection`

and explicitly does not promise:
- internal model-layer `only` / `exclude`
- patched xEdit semantics

**Step 5: Commit**

Do not commit unless the user explicitly asks for it.
