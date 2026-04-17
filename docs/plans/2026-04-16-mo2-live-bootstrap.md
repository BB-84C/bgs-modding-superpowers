# MO2 Live Bootstrap Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first real MO2 integration slice by adding a minimal Python live bridge, deploying it into the real `.artifacts/mo2/` sandbox, publishing fresh bootstrap evidence files, and teaching the broker to return real `system.ping` and `system.capabilities` results from that live evidence.

**Architecture:** Keep the long-term C++ plugin kernel scaffold untouched as the future direction, but add a minimal Python bootstrap bridge for live validation. The bridge writes `status.json`, `capabilities.json`, and `endpoint.json` into the real MO2 sandbox when it loads, and the broker gains a live file-bootstrap path for `system.ping` and `system.capabilities` that fails closed when the evidence is missing or stale.

**Tech Stack:** PowerShell, Python plugin for MO2, JSON runtime files, real MO2 sandbox at `.artifacts/mo2/`, broker CLI PowerShell helpers, git

---

### Task 1: Add Live Bridge Source Scaffold And Deployment Contract

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/README.md`
- Create: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Create: `tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1`
- Create: `tests/mo2-control-plane/live-bridge-layout.test.ps1`
- Modify: `tests/bootstrap/verify-specs.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-bridge-layout.test.ps1` to assert that the live bridge source subtree exists and declares the expected deployment target under `.artifacts/mo2/plugins/`.

```powershell
$requiredPaths = @(
    "tools/mo2-control-plane/live-bridge/README.md",
    "tools/mo2-control-plane/live-bridge/mo2_agent_control.py",
    "tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1"
)

foreach ($path in $requiredPaths) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) {
        throw "Missing live bridge path: $path"
    }
}
```

Also extend `tests/bootstrap/verify-specs.ps1` so it anchors the live bridge subtree at a high level.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-bridge-layout.test.ps1
pwsh -NoProfile -File tests/bootstrap/verify-specs.ps1
```

Expected: FAIL because the live-bridge subtree does not exist yet.

**Step 3: Write minimal implementation**

Add the three scaffold files. The Python source can be skeletal, but it must clearly state the plugin intent and bootstrap file targets.

**Step 4: Run test to verify it passes**

Run the same two commands again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge tests/mo2-control-plane/live-bridge-layout.test.ps1 tests/bootstrap/verify-specs.ps1
git commit -m "feat: scaffold mo2 live bootstrap bridge"
```

### Task 2: Lock Fresh Runtime Evidence Contract

**Files:**
- Create: `tests/mo2-control-plane/live-bootstrap-contract.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Modify: `tools/mo2-control-plane/live-bridge/README.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-bootstrap-contract.test.ps1` to lock the expected runtime files and minimum JSON fields:

- `status.json`
- `capabilities.json`
- `endpoint.json`

Example assertions:

```powershell
$bridgeSource = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py") -Raw
foreach ($phrase in @("status.json", "capabilities.json", "endpoint.json", "system.ping", "system.capabilities")) {
    if ($bridgeSource -notmatch [regex]::Escape($phrase)) {
        throw "Live bridge source is missing phrase: $phrase"
    }
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-bootstrap-contract.test.ps1
```

Expected: FAIL because the source does not yet define the full bootstrap contract.

**Step 3: Write minimal implementation**

Expand the Python bridge source comments/constants/helpers so the contract is explicit and testable.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tools/mo2-control-plane/live-bridge/README.md tests/mo2-control-plane/live-bootstrap-contract.test.ps1
git commit -m "feat: define live bootstrap evidence contract"
```

### Task 3: Add Broker File-Bootstrap Helpers For Live Ping And Capabilities

**Files:**
- Create: `tools/mo2-control-plane/broker/lib/live-bootstrap.ps1`
- Create: `tests/mo2-control-plane/live-broker-contract.test.ps1`
- Modify: `tools/mo2-control-plane/broker/bin/mo2-cli.ps1`
- Modify: `tools/mo2-control-plane/broker/lib/client.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-broker-contract.test.ps1` to verify the broker can consume a file-bootstrap root and return live-style JSON for:

- `system ping --live-root <path>`
- `system capabilities --live-root <path>`

Use a temporary fixture directory that mimics the real runtime file layout.

Example setup:

```powershell
$runtimeRoot = Join-Path $tempRoot "mo2-agent-control"
$null = New-Item -ItemType Directory -Path $runtimeRoot -Force
@{ plugin = "Mo2AgentControl"; status = "ok" } | ConvertTo-Json | Set-Content (Join-Path $runtimeRoot "status.json")
@{ commands = @("system.ping", "system.capabilities") } | ConvertTo-Json | Set-Content (Join-Path $runtimeRoot "capabilities.json")
@{ transport = "file-bootstrap" } | ConvertTo-Json | Set-Content (Join-Path $runtimeRoot "endpoint.json")
```

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-broker-contract.test.ps1
```

Expected: FAIL because the broker has no live file-bootstrap path yet.

**Step 3: Write minimal implementation**

Add helpers that:

- resolve a runtime root
- read and validate `status.json`, `capabilities.json`, `endpoint.json`
- fail closed when files are missing or malformed
- return normal broker response envelopes

Keep this support limited to `system ping` and `system capabilities`.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/broker/lib/live-bootstrap.ps1 tools/mo2-control-plane/broker/bin/mo2-cli.ps1 tools/mo2-control-plane/broker/lib/client.ps1 tests/mo2-control-plane/live-broker-contract.test.ps1
git commit -m "feat: add live bootstrap broker readers"
```

### Task 4: Add Real-Sandbox Deployment Helper

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1`
- Create: `tests/mo2-control-plane/live-deploy-contract.test.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-deploy-contract.test.ps1` to verify the deployment helper can copy the bridge into a caller-provided MO2 root, targeting the correct plugin location under `.artifacts/mo2/plugins/`.

Use a temp sandbox tree in the test rather than the real MO2 root.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-deploy-contract.test.ps1
```

Expected: FAIL because the deploy helper does not yet perform a real copy/install step.

**Step 3: Write minimal implementation**

Implement only the minimal deployment logic needed to copy the bridge into the plugin folder and any fixed data subfolder needed for the bootstrap files.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1 tests/mo2-control-plane/live-deploy-contract.test.ps1
git commit -m "feat: add live bridge deployment helper"
```

### Task 5: Implement Real Runtime Bootstrap Writer In The Python Bridge

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Create: `tests/mo2-control-plane/live-bootstrap-runtime.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/README.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-bootstrap-runtime.test.ps1` to verify the Python bridge source and deployment target now support real runtime bootstrap behavior.

The contract should lock at least:

- writing `status.json`
- writing `capabilities.json`
- writing `endpoint.json`
- runtime root under the deployed plugin tree
- `system.ping` and `system.capabilities` in the published capabilities set

Use source-level assertions for the initial red/green cycle so the runtime-writing behavior is anchored before real MO2 execution is involved.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-bootstrap-runtime.test.ps1
```

Expected: FAIL because the bridge does not yet describe or implement runtime bootstrap writing.

**Step 3: Write minimal implementation**

Add the smallest real bootstrap behavior in `mo2_agent_control.py` that can, once loaded by MO2, create the runtime directory and write the three runtime files with the minimum required fields.

Keep scope tight:

- no real IPC server yet
- no launch control yet
- only bootstrap file publication

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tools/mo2-control-plane/live-bridge/README.md tests/mo2-control-plane/live-bootstrap-runtime.test.ps1
git commit -m "feat: add live bootstrap runtime writer"
```

### Task 6: Add Real Live-Test Harness For Fresh Plugin Load Evidence

**Files:**
- Create: `tests/mo2-control-plane/live-bootstrap-real.test.ps1`
- Modify: `tools/mo2-control-plane/live-integration.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-bootstrap-real.test.ps1` as a real-environment test harness that:

- targets `D:\awesome-bgs-mod-master\.artifacts\mo2`
- clears the bootstrap runtime directory
- verifies the runtime files are missing before MO2 starts
- then checks for fresh recreation after the operator starts or restarts MO2

This harness may require an explicit opt-in flag or parameter because it touches a live sandbox. The script should fail clearly if the runtime files are still absent after the expected live step.

**Step 2: Run test to verify it fails**

Run the real harness against the current sandbox before the bridge is deployed/loaded.

Expected: FAIL because no live bridge is present yet.

**Step 3: Write minimal implementation**

Implement the live harness plus concise operator guidance in `live-integration.md` so the sequence is repeatable.

**Step 4: Run test to verify it passes**

Run the real harness again after bridge deployment and MO2 restart.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/mo2-control-plane/live-bootstrap-real.test.ps1 tools/mo2-control-plane/live-integration.md
git commit -m "test: add real mo2 live bootstrap harness"
```

### Task 7: Add Real Ping/Capabilities Verification Against The Sandbox

**Files:**
- Create: `tests/mo2-control-plane/live-ping-real.test.ps1`
- Modify: `tools/mo2-control-plane/broker/bin/mo2-cli.ps1`
- Modify: `tools/mo2-control-plane/live-integration.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-ping-real.test.ps1` to call the broker against the real `.artifacts/mo2/` bootstrap runtime and verify:

- `system ping` succeeds from real runtime files
- `system capabilities` succeeds from real runtime files
- the returned command list includes `system.ping` and `system.capabilities`

**Step 2: Run test to verify it fails**

Run the real test before the live bridge writes valid runtime files.

Expected: FAIL

**Step 3: Write minimal implementation**

Make only the smallest broker/test adjustments needed so the broker can read the live bootstrap runtime and return normal response envelopes.

**Step 4: Run test to verify it passes**

Run the real test again after the bridge is deployed and MO2 has recreated the runtime files.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/mo2-control-plane/live-ping-real.test.ps1 tools/mo2-control-plane/broker/bin/mo2-cli.ps1 tools/mo2-control-plane/live-integration.md
git commit -m "feat: verify live mo2 ping bootstrap"
```

### Task 8: Run Full Verification And Summarize The Live Slice

**Files:**
- Test: `tests/mo2-control-plane/live-bridge-layout.test.ps1`
- Test: `tests/mo2-control-plane/live-bootstrap-contract.test.ps1`
- Test: `tests/mo2-control-plane/live-broker-contract.test.ps1`
- Test: `tests/mo2-control-plane/live-deploy-contract.test.ps1`
- Test: `tests/mo2-control-plane/live-bootstrap-real.test.ps1`
- Test: `tests/mo2-control-plane/live-ping-real.test.ps1`
- Test: relevant existing `tests/mo2-control-plane/*.ps1`
- Test: `tests/bootstrap/verify-specs.ps1`

**Step 1: Run the fast contract tests**

Run the repo-local control-plane tests for the live bridge and broker additions.

**Step 2: Run the real sandbox tests**

Run the live bootstrap and live ping tests against `.artifacts/mo2/`.

**Step 3: Inspect output carefully**

Confirm that the runtime evidence was freshly recreated, not reused from stale files.

**Step 4: Summarize actual status**

Report:

- what is now proven in the real MO2 sandbox
- what remains scaffold-only
- what the next live slice should be (likely real launch.start or mo2-vfs-launcher live transport)
