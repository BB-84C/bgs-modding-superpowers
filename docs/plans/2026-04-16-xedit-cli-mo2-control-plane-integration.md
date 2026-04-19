# xedit-cli MO2 Control Plane Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route real xEdit launches through the completed MO2 control plane and `mo2-vfs-launcher` so xEdit runs under the project-local MO2/usvfs sandbox while preserving our xEdit hook automation.

**Architecture:** `xedit-cli` stops launching xEdit directly and instead issues a generic launch request through the MO2 control plane targeting `OpenCodeVfsLauncher`. `mo2-vfs-launcher` then launches xEdit inside the already-established MO2 VFS context, while xEdit still loads our `hook.dll` and uses the existing hook session environment for Module Selection automation.

**Tech Stack:** PowerShell, MO2 control plane broker/plugin, `mo2-vfs-launcher`, xEdit hook DLL, project-local MO2 sandbox, Git

---

### Task 1: Document The New Runtime Chain

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Modify: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects:

- xedit-cli to launch through the MO2 control plane
- `mo2-vfs-launcher` as the generic VFS-side child launcher
- xEdit hook automation layered on top of MO2/usvfs semantics, not direct xEdit launch
- the project-local MO2 sandbox at `.artifacts/mo2` as the real verification environment

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the docs do not yet describe the new runtime chain.

**Step 3: Write minimal implementation**

Update the docs to clearly state:

- `xedit-cli -> control plane -> mo2-vfs-launcher -> xEdit`
- MO2/usvfs owns the real plugin/file-tree semantics
- `hook.dll` owns only xEdit in-process automation
- real verification uses `.artifacts/mo2`

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md tools/xedit-cli/live-integration.md tests/bootstrap/verify-specs.ps1
git commit -m "docs: define xedit mo2 control plane runtime"
```

### Task 2: Add xedit-cli Launch Adapter Over The Control Plane

**Files:**
- Create: `tests/xedit-cli/mo2-launch-adapter.test.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`
- Create: `tools/xedit-cli/lib/mo2-launch.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`

**Step 1: Write the failing test**

Create `tests/xedit-cli/mo2-launch-adapter.test.ps1` to verify that:

- xedit-cli can translate an xEdit launch request into a control-plane launch request
- the launch request targets `OpenCodeVfsLauncher`
- xEdit-specific parameters are passed through as generic target/env payload, not baked into the control-plane schema
- `.artifacts/mo2` is treated as the default real verification sandbox root

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/mo2-launch-adapter.test.ps1`
Expected: FAIL because no adapter exists yet.

**Step 3: Write minimal implementation**

Add an adapter that builds a control-plane launch request containing:

- profile
- runner = `OpenCodeVfsLauncher`
- target xEdit launcher path
- target args
- target cwd
- hook session env
- state file/session metadata

Keep the adapter isolated from the low-level broker transport for now.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/mo2-launch-adapter.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/mo2-launch-adapter.test.ps1 tools/xedit-cli/bin/xedit-cli.ps1 tools/xedit-cli/lib/mo2-launch.ps1 tools/xedit-cli/lib/process.ps1
git commit -m "feat: add xedit mo2 launch adapter"
```

### Task 3: Pass Hook Session Environment Through mo2-vfs-launcher

**Files:**
- Modify: `tests/mo2-vfs-launcher/launcher-contract.test.ps1`
- Modify: `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- Modify: `tools/mo2-vfs-launcher/README.md`

**Step 1: Write the failing test**

Extend `tests/mo2-vfs-launcher/launcher-contract.test.ps1` to verify that:

- arbitrary env passthrough survives the launcher boundary
- xEdit hook env/session keys are preserved unmodified
- PID/state output remains stable while passing env through

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/mo2-vfs-launcher/launcher-contract.test.ps1`
Expected: FAIL because current launcher behavior is not yet explicitly tested or shaped for xEdit hook session passthrough.

**Step 3: Write minimal implementation**

Update `mo2-vfs-launcher` so it reliably forwards:

- hook session env vars
- xEdit hook policy env vars
- any other caller-specified env

without understanding xEdit business semantics.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/mo2-vfs-launcher/launcher-contract.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/mo2-vfs-launcher/launcher-contract.test.ps1 tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1 tools/mo2-vfs-launcher/README.md
git commit -m "feat: pass xedit hook env through mo2 vfs launcher"
```

### Task 4: Add A Real MO2-Sandbox Probe For xEdit Visibility

**Files:**
- Create: `tests/xedit-cli/mo2-sandbox-launch-real.test.ps1`
- Modify: `tools/xedit-cli/README.md`

**Step 1: Write the failing real test**

Create `tests/xedit-cli/mo2-sandbox-launch-real.test.ps1` to validate against:

- `D:\awesome-bgs-mod-master\.artifacts\mo2`
- profile `Default`

It should verify that a real xEdit launch through control plane + VFS launcher:

- returns a PID
- writes hook/session state
- sees the sandbox plugin set instead of only base game/DLC

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/mo2-sandbox-launch-real.test.ps1`
Expected: FAIL until the adapter and launcher path are fully wired.

**Step 3: Write minimal implementation**

Hook up the real launch path so the test can:

- target `.artifacts/mo2`
- target the correct configured executable entry / runner chain
- keep xEdit hook automation active

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/mo2-sandbox-launch-real.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/mo2-sandbox-launch-real.test.ps1 tools/xedit-cli/README.md tools/xedit-cli/lib tools/xedit-cli/bin
git commit -m "feat: wire xedit launch through mo2 sandbox"
```

### Task 5: Real xEdit `load all`

**Files:**
- Test: `tests/xedit-cli/mo2-sandbox-launch-real.test.ps1`
- Test: `tools/xedit-hook-bridge/src/*`

**Step 1: Run the real `load all` verification**

Use the project-local MO2 sandbox only:

- root: `D:\awesome-bgs-mod-master\.artifacts\mo2`
- profile: `Default`

Expected:

- xEdit launches under MO2 semantics
- hook status file is written
- Module Selection is automatically confirmed

**Step 2: Capture evidence**

Preserve:

- launch request/response
- launcher state file
- hook status file
- process PID
- visible plugin set evidence

**Step 3: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli tools/xedit-hook-bridge
git commit -m "feat: verify real xedit load-all under mo2 sandbox"
```

### Task 6: Real xEdit `only`

**Files:**
- Create or extend: `tests/xedit-cli/mo2-sandbox-subset-real.test.ps1`
- Test: `tools/xedit-hook-bridge/src/*`

**Step 1: Write the real subset test**

Add a real `only` scenario under `.artifacts/mo2`.

Expected:

- requested roots remain selected
- required masters remain selected
- final selected set is captured in hook/session evidence

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/xedit-cli/mo2-sandbox-subset-real.test.ps1`
Expected: FAIL until real subset integration is confirmed.

**Step 3: Write minimal fixes if needed**

Adjust only what is required to make real `only` work through the integrated launch chain.

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/xedit-cli/mo2-sandbox-subset-real.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli tools/xedit-hook-bridge
git commit -m "feat: verify real xedit only under mo2 sandbox"
```

### Task 7: Real xEdit `exclude`

**Files:**
- Modify: `tests/xedit-cli/mo2-sandbox-subset-real.test.ps1`
- Test: `tools/xedit-hook-bridge/src/*`

**Step 1: Add the two required real FO4 exclude probes**

Under the sandbox profile, verify:

- safe exclude target: `CraftingTools.esp`
- dependency-blocked exclude target: `ArmorKeywords.esm`

**Step 2: Run test to verify current behavior**

Run: `pwsh -File tests/xedit-cli/mo2-sandbox-subset-real.test.ps1`
Expected: This may fail initially.

**Step 3: Fix hook logic or integration only if the real evidence requires it**

Do not optimize for the old synthetic fixture. Let real xEdit behavior drive the fix.

**Step 4: Run test to verify it passes**

Expected:

- `CraftingTools.esp` is excluded when legal
- `ArmorKeywords.esm` remains selected if dependency rules require it
- blocked exclusion is explicitly reflected in hook/session status

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli tools/xedit-hook-bridge
git commit -m "feat: verify real xedit exclude under mo2 sandbox"
```
