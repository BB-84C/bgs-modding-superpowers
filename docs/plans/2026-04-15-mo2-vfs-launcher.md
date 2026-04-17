# mo2-vfs-launcher Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reusable MO2-started launcher that preserves inherited usvfs semantics, writes stable launch state, includes a real VFS probe, and adds the minimum `xedit-cli` handoff needed to use it.

**Architecture:** `mo2-vfs-launcher` is a PowerShell-first runner plus `.cmd` entrypoint under `tools/mo2-vfs-launcher/`. The runner validates an explicit launch contract, starts a target process inside already-established MO2/usvfs context, writes JSON state to disk, and optionally waits for exit. `xedit-cli` remains an external orchestrator and only gains an additive MO2-facing path that shells through `ModOrganizer.exe ... run -e OpenCodeVfsLauncher`.

**Tech Stack:** PowerShell, Windows process APIs exposed through PowerShell, JSON state files, Mod Organizer 2, xEdit CLI PowerShell modules, Git

---

### Task 1: Lock The Launcher Contract With Failing Tests

**Files:**
- Create: `tests/mo2-vfs-launcher/launcher-contract.test.ps1`
- Create: `tests/mo2-vfs-launcher/fixtures/target-ok.ps1`
- Create: `tests/mo2-vfs-launcher/fixtures/target-sleep.ps1`
- Create: `tests/mo2-vfs-launcher/fixtures/target-fail.ps1`
- Create: `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-vfs-launcher/launcher-contract.test.ps1` to verify:

- missing `--target-path`, `--session-id`, or `--state-file` fails cleanly
- repeated `--target-arg` values are preserved in order
- repeated `--env` values are accepted
- `--wait-mode spawned` writes JSON with `status=spawned`
- `--wait-mode exit` writes JSON with `status=exited`
- malformed `--env` and invalid `--wait-mode` fail closed

Use lightweight PowerShell fixture scripts under `tests/mo2-vfs-launcher/fixtures/` as safe targets.

**Step 2: Run test to verify it fails**

Run: `pwsh -NoProfile -File tests/mo2-vfs-launcher/launcher-contract.test.ps1`
Expected: FAIL because the launcher and fixtures do not exist yet.

**Step 3: Write minimal implementation**

Create `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1` with the minimum parsing and launch behavior needed for the first contract pass.

**Step 4: Run test to verify it passes**

Run: `pwsh -NoProfile -File tests/mo2-vfs-launcher/launcher-contract.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/mo2-vfs-launcher/launcher-contract.test.ps1 tests/mo2-vfs-launcher/fixtures tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1
git commit -m "feat: add mo2 vfs launcher contract"
```

### Task 2: Add Exit, Timeout, And Stream Capture Behavior

**Files:**
- Modify: `tests/mo2-vfs-launcher/launcher-contract.test.ps1`
- Modify: `tests/mo2-vfs-launcher/fixtures/target-ok.ps1`
- Modify: `tests/mo2-vfs-launcher/fixtures/target-sleep.ps1`
- Modify: `tests/mo2-vfs-launcher/fixtures/target-fail.ps1`
- Modify: `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`

**Step 1: Write the failing test**

Extend `tests/mo2-vfs-launcher/launcher-contract.test.ps1` so it also verifies:

- `--stdout-file` captures standard output
- `--stderr-file` captures standard error
- target non-zero exit becomes `status=failed` or `status=exited` with explicit error information as designed
- `--timeout-seconds` in `exit` mode writes a deterministic failure state

**Step 2: Run test to verify it fails**

Run: `pwsh -NoProfile -File tests/mo2-vfs-launcher/launcher-contract.test.ps1`
Expected: FAIL because output capture and timeout handling are incomplete.

**Step 3: Write minimal implementation**

Add the smallest correct stream redirection and timeout handling that satisfies the test.

**Step 4: Run test to verify it passes**

Run: `pwsh -NoProfile -File tests/mo2-vfs-launcher/launcher-contract.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/mo2-vfs-launcher/launcher-contract.test.ps1 tests/mo2-vfs-launcher/fixtures tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1
git commit -m "feat: add launcher timeout and stream capture"
```

### Task 3: Add Stable Wrapper And Documentation

**Files:**
- Create: `tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd`
- Create: `tools/mo2-vfs-launcher/README.md`
- Modify: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Strengthen `tests/bootstrap/verify-specs.ps1` so it expects:

- `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- `tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd`
- `tools/mo2-vfs-launcher/README.md`
- launcher contract phrases for target path, environment injection, state file, wait mode, and failure behavior

**Step 2: Run test to verify it fails**

Run: `pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1`
Expected: FAIL because the new launcher files and phrasing are not documented yet.

**Step 3: Write minimal implementation**

Add the wrapper and README with concise usage examples, including the MO2 `run -e OpenCodeVfsLauncher` pattern.

**Step 4: Run test to verify it passes**

Run: `pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd tools/mo2-vfs-launcher/README.md tests/bootstrap/verify-specs.ps1
git commit -m "docs: define mo2 vfs launcher surface"
```

### Task 4: Add A Real VFS Probe Tool

**Files:**
- Create: `tools/mo2-vfs-launcher/mo2-vfs-probe.ps1`
- Create: `tests/mo2-vfs-launcher/probe-contract.test.ps1`
- Modify: `tools/mo2-vfs-launcher/README.md`

**Step 1: Write the failing test**

Create `tests/mo2-vfs-launcher/probe-contract.test.ps1` to verify the probe can:

- inspect a caller-provided file path
- report whether the file is visible
- inspect `%LOCALAPPDATA%\Fallout4\plugins.txt`
- emit compact JSON suitable for evidence capture

**Step 2: Run test to verify it fails**

Run: `pwsh -NoProfile -File tests/mo2-vfs-launcher/probe-contract.test.ps1`
Expected: FAIL because the probe tool does not exist yet.

**Step 3: Write minimal implementation**

Implement the probe as a small PowerShell script that reports observable filesystem and plugins.txt state without modifying anything.

**Step 4: Run test to verify it passes**

Run: `pwsh -NoProfile -File tests/mo2-vfs-launcher/probe-contract.test.ps1`
Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-vfs-launcher/mo2-vfs-probe.ps1 tests/mo2-vfs-launcher/probe-contract.test.ps1 tools/mo2-vfs-launcher/README.md
git commit -m "feat: add mo2 vfs probe"
```

### Task 5: Add The xedit-cli MO2 Handoff Contract

**Files:**
- Create: `tests/xedit-cli/mo2-launch.test.ps1`
- Create: `tools/xedit-cli/lib/mo2-launch.ps1`
- Modify: `tools/xedit-cli/lib/common.ps1`
- Modify: `tools/xedit-cli/lib/process.ps1`
- Modify: `tools/xedit-cli/bin/xedit-cli.ps1`
- Modify: `tools/xedit-cli/README.md`
- Modify: `tools/xedit-cli/CONTRACT.md`
- Modify: `tools/xedit-cli/live-integration.md`

**Step 1: Write the failing test**

Create `tests/xedit-cli/mo2-launch.test.ps1` to verify that the CLI can:

- require explicit `--mo2-path`, `--mo2-profile`, and launcher-facing target inputs for the MO2-backed path
- shape a `ModOrganizer.exe -p <profile> run -e <name> -a <args>` command without embedding MO2 discovery
- pass a state-file path and session ID down to `mo2-vfs-launcher`
- keep existing direct-launch commands intact

**Step 2: Run test to verify it fails**

Run: `pwsh -NoProfile -File tests/xedit-cli/mo2-launch.test.ps1`
Expected: FAIL because `xedit-cli` does not yet expose the MO2-backed handoff.

**Step 3: Write minimal implementation**

Add the smallest additive MO2 launch path. Keep old direct launcher behavior unchanged.

**Step 4: Run test to verify it passes**

Run: `pwsh -NoProfile -File tests/xedit-cli/mo2-launch.test.ps1`
Expected: PASS

**Step 5: Run related regression tests**

Run:

- `pwsh -NoProfile -File tests/xedit-cli/doctor-env.test.ps1`
- `pwsh -NoProfile -File tests/xedit-cli/process-lifecycle.test.ps1`

Expected: PASS

**Step 6: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/xedit-cli/mo2-launch.test.ps1 tools/xedit-cli/lib/mo2-launch.ps1 tools/xedit-cli/lib/common.ps1 tools/xedit-cli/lib/process.ps1 tools/xedit-cli/bin/xedit-cli.ps1 tools/xedit-cli/README.md tools/xedit-cli/CONTRACT.md tools/xedit-cli/live-integration.md
git commit -m "feat: add xedit cli mo2 launcher handoff"
```

### Task 6: Run Real Probe Verification Against The User MO2 Instance

**Files:**
- Test: `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- Test: `tools/mo2-vfs-launcher/mo2-vfs-probe.ps1`

**Step 1: Identify a mod-only probe target in the `CK与调试` profile**

Run the minimum inspection needed against `B:\WastelandBlues 2.0` to choose one file that is visible through MO2/profile semantics and absent from the plain game view.

**Step 2: Capture the normal-shell baseline**

Run the probe directly outside MO2 and save the output.
Expected: the chosen mod-only file is not visible or the plugins view differs from the MO2-backed result.

**Step 3: Run the probe through MO2 and the launcher**

Run a real command shaped like:

```bash
& "B:\WastelandBlues 2.0\ModOrganizer.exe" -p "CK与调试" run -e "OpenCodeVfsLauncher" -a "..."
```

Expected: the probe now sees the mod-only file and reports the profile-backed `plugins.txt` state.

**Step 4: Save evidence**

Preserve the command, probe JSON, and state file under a run-scoped artifact location such as `.artifacts/mo2-vfs-launcher/`.

### Task 7: Run Real xEdit Launch Verification

**Files:**
- Test: `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- Test: `tools/xedit-cli/*`

**Step 1: Run real FO4Edit through the launcher path**

Use the user’s MO2 instance and `CK与调试` profile to start the real target through `OpenCodeVfsLauncher`.

**Step 2: Verify plugin visibility evidence**

Capture the strongest available evidence that the launched xEdit instance sees the profile plugin set rather than only base game and DLC state.

**Step 3: Save evidence**

Preserve command summaries, state files, and any hook/session evidence under `.artifacts/mo2-vfs-launcher/`.

### Task 8: Run Full Verification Before Completion

**Files:**
- Test: `tests/mo2-vfs-launcher/launcher-contract.test.ps1`
- Test: `tests/mo2-vfs-launcher/probe-contract.test.ps1`
- Test: `tests/bootstrap/verify-specs.ps1`
- Test: `tests/xedit-cli/mo2-launch.test.ps1`
- Test: `tests/xedit-cli/doctor-env.test.ps1`
- Test: `tests/xedit-cli/process-lifecycle.test.ps1`

**Step 1: Run the automated verification suite**

Run each command above and confirm all pass.

**Step 2: Re-run the real verification commands if needed**

Confirm that the saved probe/xEdit evidence still matches the final code.

**Step 3: Summarize outcome**

Report code changes, automated test results, real-environment evidence, and any residual risks.
