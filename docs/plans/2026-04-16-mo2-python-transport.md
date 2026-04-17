# MO2 Python Transport And Launch Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real local IPC transport to the Python MO2 plugin and use it to implement the smallest real `system.*` and `launch.*` command family against the live `.artifacts/mo2/` sandbox.

**Architecture:** Keep file-bootstrap discovery as the liveness and endpoint-discovery layer, but move actual command execution onto a Python-plugin-hosted named pipe transport. The broker remains the external CLI surface; the Python plugin becomes the real live command executor for `system.ping`, `system.capabilities`, and `launch.start/status/wait/stop`.

**Tech Stack:** PowerShell, Python plugin for MO2, Windows named pipes, JSON request/response envelopes, live MO2 sandbox at `.artifacts/mo2/`, git

---

### Task 1: Lock Named-Pipe Discovery Contract

**Files:**
- Create: `tests/mo2-control-plane/live-endpoint-contract.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Modify: `tools/mo2-control-plane/live-bridge/README.md`
- Modify: `tools/mo2-control-plane/live-integration.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-endpoint-contract.test.ps1` to lock the new endpoint discovery shape. It should assert that the live bridge source and docs now describe:

- `transport = named-pipe`
- a pipe name or endpoint field in `endpoint.json`
- file-bootstrap retained only as discovery/liveness, not as the command transport

Example assertion:

```powershell
$bridgeSource = Get-Content -Path (Join-Path $repoRoot "tools/mo2-control-plane/live-bridge/mo2_agent_control.py") -Raw
foreach ($phrase in @("named-pipe", "endpoint.json", "system.ping", "launch.start")) {
    if ($bridgeSource -notmatch [regex]::Escape($phrase)) {
        throw "Live bridge source is missing phrase: $phrase"
    }
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-endpoint-contract.test.ps1
```

Expected: FAIL because the bridge still describes file-bootstrap transport only.

**Step 3: Write minimal implementation**

Update the bridge constants/docs so endpoint discovery explicitly anchors named-pipe transport.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tools/mo2-control-plane/live-bridge/README.md tools/mo2-control-plane/live-integration.md tests/mo2-control-plane/live-endpoint-contract.test.ps1
git commit -m "feat: define mo2 named-pipe discovery contract"
```

### Task 2: Add Python Plugin Transport Skeleton

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Create: `tests/mo2-control-plane/live-transport-runtime.test.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-transport-runtime.test.ps1` to lock the Python-side transport skeleton. It should assert the bridge source now contains:

- a named-pipe server bootstrap helper
- a request dispatcher entry
- a place to register command handlers
- transport startup from plugin init

Keep this source-level at first.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-transport-runtime.test.ps1
```

Expected: FAIL because the plugin has no real transport skeleton yet.

**Step 3: Write minimal implementation**

Add the smallest viable transport skeleton in Python. Do not wire launch behavior yet; only establish the server, endpoint description, and dispatch shape.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tests/mo2-control-plane/live-transport-runtime.test.ps1
git commit -m "feat: add python transport skeleton"
```

### Task 3: Add Broker Named-Pipe Client For system.* Commands

**Files:**
- Create: `tools/mo2-control-plane/broker/lib/ipc-client.ps1`
- Create: `tests/mo2-control-plane/live-ipc-contract.test.ps1`
- Modify: `tools/mo2-control-plane/broker/bin/mo2-cli.ps1`
- Modify: `tools/mo2-control-plane/broker/lib/client.ps1`
- Modify: `tools/mo2-control-plane/broker/lib/live-bootstrap.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-ipc-contract.test.ps1` to verify that when endpoint discovery says `transport=named-pipe`, the broker sends `system.ping` and `system.capabilities` over IPC instead of directly reading bootstrap payload files.

Use a local fake pipe responder or a narrow shim fixture to avoid the real MO2 sandbox at first.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-ipc-contract.test.ps1
```

Expected: FAIL because broker has no named-pipe client path yet.

**Step 3: Write minimal implementation**

Add the broker named-pipe client and switch live `system.*` commands to prefer IPC when `endpoint.json` advertises named-pipe transport.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Run regression tests**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-broker-contract.test.ps1
pwsh -NoProfile -File tests/mo2-control-plane/mo2-cli-foundation.test.ps1
```

Expected: PASS

**Step 6: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/broker/lib/ipc-client.ps1 tools/mo2-control-plane/broker/bin/mo2-cli.ps1 tools/mo2-control-plane/broker/lib/client.ps1 tools/mo2-control-plane/broker/lib/live-bootstrap.ps1 tests/mo2-control-plane/live-ipc-contract.test.ps1
git commit -m "feat: add broker named-pipe client"
```

### Task 4: Add Minimal Python Command Handlers For system.*

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Create: `tests/mo2-control-plane/live-system-handler.test.ps1`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-system-handler.test.ps1` to lock the minimal handler behavior for:

- `system.ping`
- `system.capabilities`

It should verify real response envelope shaping on the Python side, not just transport presence.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-system-handler.test.ps1
```

Expected: FAIL because the plugin has no real system handlers yet.

**Step 3: Write minimal implementation**

Implement only the smallest correct handlers and envelope serialization.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tests/mo2-control-plane/live-system-handler.test.ps1
git commit -m "feat: add python system command handlers"
```

### Task 5: Lock Launch Contract And Registry Shape

**Files:**
- Create: `tests/mo2-control-plane/live-launch-contract.test.ps1`
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Modify: `tools/mo2-control-plane/live-bridge/README.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-launch-contract.test.ps1` to lock the minimal launch command and registry shape for:

- `launch.start`
- `launch.status`
- `launch.wait`
- `launch.stop`

Assertions should cover required payload/result fields and launch-registry bookkeeping shape.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-launch-contract.test.ps1
```

Expected: FAIL because the Python bridge has no real launch registry/handlers yet.

**Step 3: Write minimal implementation**

Add only the launch-registry structures and constants needed for the next task.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tools/mo2-control-plane/live-bridge/README.md tests/mo2-control-plane/live-launch-contract.test.ps1
git commit -m "feat: define python launch contract"
```

### Task 6: Implement Real Named-Pipe Transport In Plugin And Broker

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Modify: `tools/mo2-control-plane/broker/lib/ipc-client.ps1`
- Create: `tests/mo2-control-plane/live-ipc-runtime.test.ps1`
- Modify: `tools/mo2-control-plane/live-integration.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-ipc-runtime.test.ps1` to verify the transport path is no longer fixture-only.

The test should lock at least:

- Python bridge exposes a real named-pipe server bootstrap path, not only metadata
- broker IPC client can perform a real request/response round-trip against a local named-pipe endpoint
- `system.ping` can travel over that local named-pipe path without using `MO2_CONTROL_PLANE_FAKE_IPC_RESPONSE_PATH`

Use a local, non-MO2 harness first so the red/green cycle stays focused on transport.

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-ipc-runtime.test.ps1
```

Expected: FAIL because the transport is still skeleton/fixture backed.

**Step 3: Write minimal implementation**

Add the smallest correct real named-pipe server/client path.

Keep scope tight:

- only the transport runtime
- only the system command round-trip needed to prove the channel works
- no launch behavior yet

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tools/mo2-control-plane/broker/lib/ipc-client.ps1 tests/mo2-control-plane/live-ipc-runtime.test.ps1 tools/mo2-control-plane/live-integration.md
git commit -m "feat: add real named-pipe transport"
```

### Task 7: Implement Real launch.start/status/wait/stop In Python Plugin

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Create: `tests/mo2-control-plane/live-launch-flow.test.ps1`
- Modify: `tools/mo2-control-plane/live-integration.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-launch-flow.test.ps1` to verify a real end-to-end launch flow through the Python plugin transport using harmless targets.

Use at least:

- fast target: `cmd.exe /c exit 0`
- longer-lived target for stop/wait semantics if needed

Assertions should cover:

- `launch.start` returns `launch_id`, `pid`, `status`
- `launch.status` reflects a tracked launch
- `launch.wait` returns the real exit state
- `launch.stop` stops a long-lived harmless process and reports `stopped`

**Step 2: Run test to verify it fails**

Run:

```bash
pwsh -NoProfile -File tests/mo2-control-plane/live-launch-flow.test.ps1
```

Expected: FAIL because live launch handlers are not fully implemented yet.

**Step 3: Write minimal implementation**

Implement the smallest correct real launch handlers in the Python plugin using MO2-exposed APIs where possible.

**Step 4: Run test to verify it passes**

Run the same command again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tests/mo2-control-plane/live-launch-flow.test.ps1 tools/mo2-control-plane/live-integration.md
git commit -m "feat: add real python launch handlers"
```

### Task 8: Add Real Sandbox IPC And Launch Harness

**Files:**
- Create: `tests/mo2-control-plane/live-ipc-real.test.ps1`
- Modify: `tools/mo2-control-plane/live-integration.md`

**Step 1: Write the failing test**

Create `tests/mo2-control-plane/live-ipc-real.test.ps1` for the real `.artifacts/mo2/` sandbox. It should:

- deploy the bridge
- restart the sandbox serially
- wait for endpoint discovery
- verify `system.ping` and `system.capabilities` over real IPC
- verify a harmless real launch flow over real IPC using the sandboxed MO2 plugin path

**Step 2: Run test to verify it fails**

Run it before the full real IPC path is in place.

Expected: FAIL

**Step 3: Write minimal implementation**

Adjust docs/harness only as needed so the real IPC and harmless real launch path are reproducible.

**Step 4: Run test to verify it passes**

Run the same test again.

Expected: PASS

**Step 5: Commit**

Only if the user explicitly requests a commit:

```bash
git add tests/mo2-control-plane/live-ipc-real.test.ps1 tools/mo2-control-plane/live-integration.md
git commit -m "test: add real ipc harness"
```

### Task 9: Run Full Verification And Summarize The Slice

**Files:**
- Test: new `tests/mo2-control-plane/live-*.ps1`
- Test: existing `tests/mo2-control-plane/*.ps1`
- Test: `tests/bootstrap/verify-specs.ps1`
- Test: `tests/mo2-vfs-launcher/*.ps1`
- Test: relevant `tests/xedit-cli/*.ps1`

**Step 1: Run the fast contract suite**

Run all repo-local transport and launch contract tests.

**Step 2: Run real sandbox tests serially**

Run all real `.artifacts/mo2/` IPC and launch tests one after another, never in parallel.

**Step 3: Inspect output carefully**

Confirm:

- real IPC is being used
- launch records are real
- no stale-bootstrap-only success path is masking transport failures

**Step 4: Summarize actual state**

Report:

- what is now real over IPC
- what still remains on bootstrap discovery only
- what the next slice should be (likely `mo2-vfs-launcher` real transport wiring)
