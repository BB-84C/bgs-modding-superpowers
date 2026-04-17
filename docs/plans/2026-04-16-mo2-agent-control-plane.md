# MO2 Agent Control Plane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first MO2 automation scaffold: a plugin-kernel source tree, a broker CLI scaffold, a versioned local RPC contract, session/artifact handling, and the first launch-family primitives that can later host `mo2-vfs-launcher` and other agent-facing tools.

**Architecture:** The work is split into two halves. The broker half is implemented first in PowerShell so the repo gets a stable agent-facing CLI, test harness, protocol helpers, and session/artifact model quickly. The MO2 half is introduced as a plugin source scaffold with a narrow kernel surface and command registry so later live integration grows on a stable substrate rather than ad hoc seams.

**Tech Stack:** PowerShell, JSON, local IPC contract design, MO2 C++/Qt plugin source scaffold, repo bootstrap verification, git

**Local sandbox for live testing:** Use the user-provided installer at `.external-resource/Mod.Organizer-2.5.3dev7.exe` only as a fallback source. The current live MO2 test instance is already provisioned at `.artifacts/mo2/` and manages a real Fallout 4. Keep installers immutable in `.external-resource/`, and keep extracted/tested MO2 instances in `.artifacts/` so they stay project-local but git-ignored.

---

### Task 1: Scaffold The Control-Plane Layout And Spec Guards

**Files:**
- Create: `tools/mo2-control-plane/README.md`
- Create: `tools/mo2-control-plane/broker/README.md`
- Create: `tools/mo2-control-plane/plugin/README.md`
- Create: `tests/mo2-control-plane/layout.test.ps1`
- Modify: `tests/bootstrap/verify-specs.ps1`
- Modify: `tools/README.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/layout.test.ps1` to assert that the new control-plane scaffold exists and that the docs use the approved architecture terms.

```powershell
$requiredPaths = @(
    "tools/mo2-control-plane/README.md",
    "tools/mo2-control-plane/broker/README.md",
    "tools/mo2-control-plane/plugin/README.md"
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) {
        throw "Missing control-plane scaffold path: $path"
    }
}
```

Also extend `tests/bootstrap/verify-specs.ps1` so the repo spec starts guarding phrases such as `control plane`, `plugin kernel`, `broker CLI`, `capability discovery`, and `session/artifact`.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/layout.test.ps1
pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1
```

Expected: FAIL because the scaffold files and spec phrases do not exist yet.

**Step 3: Write minimal implementation**

Add the new directories and short READMEs that define the split between broker and plugin.

Example README seed:

```markdown
# MO2 Control Plane

This subtree holds the MO2 automation substrate.

- `broker/` contains the agent-facing CLI and protocol helpers.
- `plugin/` contains the in-process MO2 plugin kernel.
```

**Step 4: Run test to verify it passes**

Run the same two commands again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane tools/README.md tests/mo2-control-plane/layout.test.ps1 tests/bootstrap/verify-specs.ps1
git commit -m "docs: scaffold mo2 control plane layout"
```

### Task 2: Add Broker Protocol And Session Helpers

**Files:**
- Create: `tools/mo2-control-plane/broker/lib/common.ps1`
- Create: `tools/mo2-control-plane/broker/lib/protocol.ps1`
- Create: `tools/mo2-control-plane/broker/lib/session.ps1`
- Create: `tests/mo2-control-plane/protocol.test.ps1`
- Create: `tests/mo2-control-plane/session.test.ps1`

**Step 1: Write the failing tests**

Create `tests/mo2-control-plane/protocol.test.ps1` and `tests/mo2-control-plane/session.test.ps1` for the versioned envelope and session/artifact layout.

Protocol assertions should cover:

- required `protocol_version`, `request_id`, `session_id`, `command`, `payload`
- structured error object shape
- command class metadata support for `safe-read`, `controlled-write`, `dangerous-write`

Example protocol expectation:

```powershell
$request = New-Mo2ControlPlaneRequest -SessionId "sess-1" -Command "system.ping" -Payload @{}
if ($request.protocol_version -ne "1") { throw "Expected protocol version 1" }
if ($request.command -ne "system.ping") { throw "Expected system.ping" }
```

Session assertions should cover:

- deterministic session root creation
- launch/artifact child paths
- ability to re-open the same session safely

**Step 2: Run tests to verify they fail**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/protocol.test.ps1
pwsh -NoProfile -File tests/mo2-control-plane/session.test.ps1
```

Expected: FAIL because the helper libraries do not exist yet.

**Step 3: Write minimal implementation**

Implement small helpers such as:

```powershell
function New-Mo2ControlPlaneRequest {
    param([string]$SessionId, [string]$Command, [object]$Payload)

    return [ordered]@{
        protocol_version = "1"
        request_id = "req-" + [guid]::NewGuid().ToString("N")
        session_id = $SessionId
        command = $Command
        payload = $Payload
    }
}
```

and:

```powershell
function Get-Mo2ControlPlaneSessionRoot {
    param([string]$SessionId)
    return Join-Path $env:TEMP "mo2-control-plane\$SessionId"
}
```

**Step 4: Run tests to verify they pass**

Run the same two commands again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/broker/lib tests/mo2-control-plane/protocol.test.ps1 tests/mo2-control-plane/session.test.ps1
git commit -m "feat: add mo2 control plane protocol helpers"
```

### Task 3: Build The Broker CLI Skeleton For Foundation Commands

**Files:**
- Create: `tools/mo2-control-plane/broker/bin/mo2-cli.ps1`
- Create: `tools/mo2-control-plane/broker/lib/client.ps1`
- Create: `tests/mo2-control-plane/mo2-cli-foundation.test.ps1`
- Create: `tests/mo2-control-plane/fixtures/fake-kernel-response.json`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/mo2-cli-foundation.test.ps1` to verify the broker can expose at least:

- `system ping`
- `system capabilities`
- `session open`
- `session artifacts`

Use a fake client transport first so the broker surface is locked before a real plugin connection exists.

Example invocation shape:

```powershell
$result = & "tools/mo2-control-plane/broker/bin/mo2-cli.ps1" system ping
if ($LASTEXITCODE -ne 0) { throw "mo2-cli system ping should succeed" }
```

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/mo2-cli-foundation.test.ps1
```

Expected: FAIL because the CLI entrypoint does not exist yet.

**Step 3: Write minimal implementation**

Implement a small command router in `mo2-cli.ps1` that uses the protocol/session helpers and a temporary fake client.

Example command branch:

```powershell
switch ("$group $command") {
    "system ping" {
        Write-Host "system ping"
        Write-Host "status: ok"
        exit 0
    }
}
```

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/broker/bin tools/mo2-control-plane/broker/lib/client.ps1 tests/mo2-control-plane/mo2-cli-foundation.test.ps1 tests/mo2-control-plane/fixtures
git commit -m "feat: add mo2 broker foundation commands"
```

### Task 4: Add Plugin Kernel Source Scaffold And Command Registry

**Files:**
- Create: `tools/mo2-control-plane/plugin/CMakeLists.txt`
- Create: `tools/mo2-control-plane/plugin/src/Mo2AgentControlPlugin.h`
- Create: `tools/mo2-control-plane/plugin/src/Mo2AgentControlPlugin.cpp`
- Create: `tools/mo2-control-plane/plugin/src/CommandRegistry.h`
- Create: `tools/mo2-control-plane/plugin/src/CommandRegistry.cpp`
- Create: `tools/mo2-control-plane/plugin/src/ProtocolTypes.h`
- Create: `tests/mo2-control-plane/plugin-contract.test.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/plugin-contract.test.ps1` to verify that the plugin scaffold defines:

- a plugin entry class
- a command registry
- foundation command names `system.ping`, `system.capabilities`, `system.status`
- a place to classify commands by safety level

Example assertion:

```powershell
$content = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/plugin/src/CommandRegistry.cpp") -Raw
foreach ($name in @("system.ping", "system.capabilities", "system.status")) {
    if ($content -notmatch [regex]::Escape($name)) {
        throw "Command registry is missing $name"
    }
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/plugin-contract.test.ps1
```

Expected: FAIL because the plugin source tree does not exist yet.

**Step 3: Write minimal implementation**

Add the plugin source scaffold with a narrow registry shape.

Example registry seed:

```cpp
struct RegisteredCommand {
  std::string name;
  std::string safetyClass;
};
```

and:

```cpp
static const std::vector<RegisteredCommand> kCommands = {
  {"system.ping", "safe-read"},
  {"system.capabilities", "safe-read"},
  {"system.status", "safe-read"},
};
```

**Step 4: Run test to verify it passes**

Run the same contract test again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/plugin tests/mo2-control-plane/plugin-contract.test.ps1
git commit -m "feat: scaffold mo2 plugin kernel registry"
```

### Task 5: Add Read / Control Primitive Contracts To The Registry And Broker

**Files:**
- Modify: `tools/mo2-control-plane/broker/bin/mo2-cli.ps1`
- Modify: `tools/mo2-control-plane/broker/lib/client.ps1`
- Modify: `tools/mo2-control-plane/plugin/src/CommandRegistry.cpp`
- Create: `tests/mo2-control-plane/primitives-contract.test.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/primitives-contract.test.ps1` to lock the initial primitive families:

- `profile.list`
- `profile.get-current`
- `profile.set-current`
- `executables.list`
- `executables.get`
- `mods.list`
- `plugins.list`
- `organizer.refresh`
- `launch.start`
- `launch.status`
- `launch.wait`
- `launch.stop`

Use source-level registry checks plus broker command routing checks.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/primitives-contract.test.ps1
```

Expected: FAIL because the registry and broker do not contain all primitive commands yet.

**Step 3: Write minimal implementation**

Extend the broker router and plugin registry with stubbed primitive declarations. Keep command bodies minimal if live behavior is not yet available.

Example registration:

```cpp
{"launch.start", "controlled-write"},
{"launch.status", "safe-read"},
{"organizer.refresh", "controlled-write"},
```

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/broker/bin/mo2-cli.ps1 tools/mo2-control-plane/broker/lib/client.ps1 tools/mo2-control-plane/plugin/src/CommandRegistry.cpp tests/mo2-control-plane/primitives-contract.test.ps1
git commit -m "feat: define mo2 control plane primitive commands"
```

### Task 6: Add Launch-State Helpers And Fake-Kernel Launch Flow

**Files:**
- Create: `tools/mo2-control-plane/broker/lib/launch.ps1`
- Create: `tests/mo2-control-plane/launch-flow.test.ps1`
- Create: `tests/mo2-control-plane/fixtures/fake-kernel.ps1`
- Modify: `tools/mo2-control-plane/broker/bin/mo2-cli.ps1`
- Modify: `tools/mo2-control-plane/broker/lib/client.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/launch-flow.test.ps1` to verify a fake-kernel-backed flow for:

- `launch.start`
- `launch.status`
- `launch.wait`
- `launch.stop`

The fake kernel should return launch IDs, PIDs, status transitions, and artifact paths through the same JSON shape expected later from the real plugin.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/launch-flow.test.ps1
```

Expected: FAIL because the launch helper and fake-kernel flow do not exist yet.

**Step 3: Write minimal implementation**

Add launch-state helpers that normalize result objects like:

```powershell
[ordered]@{
    launch_id = "launch-1"
    pid = 12345
    status = "spawned"
    artifacts = @{ state_file = "..." }
}
```

and teach the broker to print stable summaries plus JSON when needed.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/broker/lib/launch.ps1 tools/mo2-control-plane/broker/bin/mo2-cli.ps1 tools/mo2-control-plane/broker/lib/client.ps1 tests/mo2-control-plane/launch-flow.test.ps1 tests/mo2-control-plane/fixtures/fake-kernel.ps1
git commit -m "feat: add mo2 control plane launch scaffold"
```

### Task 7: Rebase `mo2-vfs-launcher` Onto The New Launch Family

**Files:**
- Modify: `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- Modify: `tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd`
- Modify: `tools/mo2-vfs-launcher/README.md`
- Modify: `tools/xedit-cli/lib/mo2-launch.ps1`
- Modify: `tests/mo2-vfs-launcher/launcher-contract.test.ps1`
- Modify: `tests/xedit-cli/mo2-launch.test.ps1`

**Step 1: Write the failing test**

Update the launcher and xEdit tests so they expect the MO2-facing path to go through the broker launch family instead of directly assuming `ModOrganizer.exe run ...` is the long-term transport.

At this stage the real MO2 transport may still be fake-kernel-backed in tests; the important thing is to prove that `mo2-vfs-launcher` is now a consumer of the control-plane launch abstraction rather than the architecture center itself.

**Step 2: Run tests to verify they fail**

Run:

```bash
pwsh -NoProfile -File tests/mo2-vfs-launcher/launcher-contract.test.ps1
pwsh -NoProfile -File tests/xedit-cli/mo2-launch.test.ps1
```

Expected: FAIL because the new broker-backed path is not wired yet.

**Step 3: Write minimal implementation**

Keep `mo2-vfs-launcher` as a launch consumer. The broker should own transport, while launcher-specific state shaping remains in the launcher tool.

**Step 4: Run tests to verify they pass**

Run the same two commands again.

Expected: PASS

**Step 5: Run regression tests**

Run:

```bash
pwsh -NoProfile -File tests/xedit-cli/doctor-env.test.ps1
pwsh -NoProfile -File tests/xedit-cli/process-lifecycle.test.ps1
pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1
```

Expected: PASS

**Step 6: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-vfs-launcher tools/xedit-cli/lib/mo2-launch.ps1 tests/mo2-vfs-launcher/launcher-contract.test.ps1 tests/xedit-cli/mo2-launch.test.ps1
git commit -m "feat: rebase mo2 vfs launcher on control plane"
```

### Task 8: Add Live Integration Notes And Verification Hooks

**Files:**
- Create: `tools/mo2-control-plane/live-integration.md`
- Modify: `tests/bootstrap/verify-specs.ps1`
- Create: `tests/mo2-control-plane/live-plan.test.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-plan.test.ps1` to verify the repo documents:

- the live sandbox root `.artifacts/mo2/`
- use of `.external-resource/Mod.Organizer-2.5.3dev7.exe` as a fallback immutable installer input
- where the plugin binary should be installed inside MO2
- how the broker discovers or is pointed at the local IPC endpoint
- how to verify plugin load
- how to verify a real launch in MO2/usvfs context

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-plan.test.ps1
```

Expected: FAIL because the live-integration notes do not exist yet.

**Step 3: Write minimal implementation**

Document the live verification path and update bootstrap spec guards so the new control plane docs stay anchored.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-integration.md tests/mo2-control-plane/live-plan.test.ps1 tests/bootstrap/verify-specs.ps1
git commit -m "docs: define mo2 control plane live verification"
```

### Task 9: Run Full Verification Before Claiming Completion

**Files:**
- Test: `tests/mo2-control-plane/layout.test.ps1`
- Test: `tests/mo2-control-plane/protocol.test.ps1`
- Test: `tests/mo2-control-plane/session.test.ps1`
- Test: `tests/mo2-control-plane/mo2-cli-foundation.test.ps1`
- Test: `tests/mo2-control-plane/plugin-contract.test.ps1`
- Test: `tests/mo2-control-plane/primitives-contract.test.ps1`
- Test: `tests/mo2-control-plane/launch-flow.test.ps1`
- Test: `tests/mo2-control-plane/live-plan.test.ps1`
- Test: `tests/bootstrap/verify-specs.ps1`
- Test: existing `tests/mo2-vfs-launcher/*.ps1`
- Test: existing `tests/xedit-cli/*.ps1` relevant regressions

**Step 1: Run the full test set**

Run each of the above PowerShell tests.

**Step 2: Inspect output carefully**

Confirm every test exits zero and no stale assumptions remain from the old launcher-only design.

**Step 3: Summarize the actual state**

Report what is verified, what is still scaffold-only, and what still requires a real MO2 live environment to confirm.
