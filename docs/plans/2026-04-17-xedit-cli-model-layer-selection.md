# xedit-cli Model-Layer Selection Experiment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prove whether xEdit's own internal module-selection model (`AllModules`, `SelectFlag`, `SimulateLoad`) can reliably express agent-facing `only` and `exclude` semantics in the real MO2 sandbox.

**Architecture:** This is an experiment slice, not the final production implementation. Instead of continuing to push on tree-widget control, we validate xEdit's semantic model directly and use the result to decide whether the long-term solution should be a small xEdit-side seam, a host-method hook seam, or a rethought no-fork strategy.

**Tech Stack:** xEdit upstream source experiment, Delphi/Win32 build, project-local MO2 sandbox, PowerShell verification harnesses, Git

---

### Task 1: Document The Model-Layer Experiment Contract

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Modify: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects:

- the next `only/exclude` investigation to target xEdit's own model layer
- `AllModules`, `SelectFlag`, and `SimulateLoad` as the semantic seam
- the current HWND/tree probing path to be described as diagnostic, not as the final semantic solution

**Step 2: Run test to verify it fails**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the docs do not yet describe the model-layer experiment.

**Step 3: Write minimal implementation**

Update the docs so they clearly state:

- why the tree path is no longer the primary semantic target
- what the model-layer experiment is trying to prove
- how that result will guide the next architecture decision

**Step 4: Run test to verify it passes**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit.

### Task 2: Add A Real `only` Experiment Harness

**Files:**
- Create: `tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1`
- Modify: `tests/xedit-cli/mo2-sandbox-subset-real.test.ps1` only if shared helpers should move

**Step 1: Write the failing test**

Create a real sandbox harness that can verify a model-layer `only` experiment under:

- `.artifacts\mo2`
- profile `Default`

The first real target should be:

- requested root: `RaiderOverhaul.esp`

The harness should capture:

- launch request/response
- launch state
- hook/session status
- final selected modules

**Step 2: Run test to verify it fails**

Run: `pwsh -NoProfile -File tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1 -AllowLiveSandbox -EnsureBridge -RestartMo2`
Expected: FAIL until the model seam is wired.

**Step 3: Write minimal harness implementation**

Do not change xEdit behavior yet. Only build the real verification harness so it is ready for the experiment seam.

**Step 4: Run test to verify it still fails for the intended reason**

Run the same command and confirm the failure is now clean and attributable to the missing model seam.

**Step 5: Commit**

Only if the user explicitly requests a commit.

### Task 3: Add A Minimal xEdit-Side Model Experiment Seam

**Files:**
- Modify: local xEdit experiment source tree used for validation (for example under `.artifacts/TES5Edit-source/...` or another explicit experiment location)
- Modify: any local build/readme instructions needed for the experiment

**Step 1: Write the failing real test**

Use the real harness from Task 2 as the failing test.

Expected failure: no model-layer only behavior exists yet.

**Step 2: Implement the smallest experiment seam**

The seam should do only this:

- read requested roots from environment or a simple session payload
- `AllModules.ExcludeAll(SelectFlag)`
- set `SelectFlag` on requested roots
- call `SimulateLoad`
- expose resulting selected modules in a machine-readable way

Do not try to finalize the production no-fork hook design in this task.

**Step 3: Run the real test to verify it passes**

Run: `pwsh -NoProfile -File tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1 -AllowLiveSandbox -EnsureBridge -RestartMo2`

Expected evidence:

- final selected modules include `RaiderOverhaul.esp`
- final selected modules include required master `ArmorKeywords.esm`

**Step 4: Commit**

Only if the user explicitly requests a commit.

### Task 4: Extend The Experiment To `exclude`

**Files:**
- Modify: `tests/xedit-cli/mo2-sandbox-model-selection-real.test.ps1`
- Modify: the local xEdit experiment seam from Task 3

**Step 1: Add the two real exclude cases**

- safe exclusion: `CraftingTools.esp`
- dependency-blocked exclusion: `ArmorKeywords.esm` while `RaiderOverhaul.esp` remains active

**Step 2: Run test to verify current behavior**

Expected: likely FAIL until exclude semantics are added to the model seam.

**Step 3: Implement the smallest model-layer exclude behavior**

Use the current active baseline, clear the requested `SelectFlag` values, then call `SimulateLoad`.

**Step 4: Run the real test to verify it passes**

Expected evidence:

- `CraftingTools.esp` absent from final selected set when legal
- `ArmorKeywords.esm` retained when dependency rules require it

**Step 5: Commit**

Only if the user explicitly requests a commit.

### Task 5: Decide Long-Term Integration Direction

**Files:**
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/live-integration.md`
- Optionally add a short decision note under `docs/plans/`

**Step 1: Evaluate the experiment outcome**

Use the real evidence from Tasks 3 and 4 to answer:

- xEdit semantics good, access strategy bad?
- or semantics themselves unsuitable?

**Step 2: Record the decision**

Capture one of these conclusions explicitly:

- continue no-fork, but target a model-layer seam instead of tree/UI control
- or move to a small xEdit-side patch / fork because the model seam is only realistically available there

**Step 3: Verify docs are consistent**

Run: `pwsh -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 4: Commit**

Only if the user explicitly requests a commit.
