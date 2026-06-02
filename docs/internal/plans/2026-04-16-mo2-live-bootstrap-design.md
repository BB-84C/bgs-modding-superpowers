# MO2 Live Bootstrap Slice Design

## Goal

Define the first real MO2 integration slice for the control plane: prove that a plugin/bridge can be loaded by the real MO2 instance at `.artifacts/mo2/`, publish fresh runtime evidence from inside the MO2 process, and let the broker return real `system.ping` and `system.capabilities` results from that evidence.

This slice intentionally stops short of real `launch.start`, `mo2-vfs-launcher`, or `xedit-cli` live execution. The purpose is to establish a trustworthy live testing base before stacking more behavior on top.

## Why This Slice Comes First

The repository already has a strong contract-tested scaffold for the broker, launcher, and fake-kernel transport. What it does not yet have is a proven live foothold inside a real MO2 process.

Jumping directly to real launch or xEdit orchestration would combine too many unknowns at once:

- is the plugin actually loaded?
- is the runtime discovery path correct?
- is the endpoint/discovery information fresh?
- is the broker reading live evidence or stale leftovers?

The first live slice should therefore answer a smaller question with strong evidence:

> Can a real MO2 instance load our bridge and publish machine-readable bootstrap data that the broker can trust?

## Real Environment Context

The live sandbox already exists at:

- `D:\awesome-bgs-mod-master\.artifacts\mo2`

Key observed facts:

- the sandbox manages a real `Fallout 4`
- `plugins/` currently contains stock MO2 plugins but no `Mo2AgentControl` payload yet
- `ModOrganizer.ini` points at the sandbox-managed `Fallout 4`

So this slice starts from a clean live-bridge state rather than validating an already-installed control-plane plugin.

## Approaches Considered

### Option 1: Minimal Python live bridge plus file-bootstrap discovery

This adds a minimal Python plugin to the real MO2 sandbox. On plugin load it writes runtime evidence files that the broker can consume for `system.ping` and `system.capabilities`.

This is the recommended approach.

Why:

- fastest way to get real in-process MO2 evidence
- decouples plugin-load problems from transport-server problems
- excellent fit for live TDD because fresh runtime files are easy to observe and invalidate
- keeps the long-term C++ kernel direction intact

### Option 2: Pure C++ live plugin immediately

This would align directly with the long-term kernel, but it raises build/SDK/integration complexity before the project has even proven a minimal live load path.

### Option 3: UI/log-only proof without a live bridge

This is not sufficient. It can suggest that a plugin may have loaded, but it does not give the broker a real control-plane foothold.

## Recommended Architecture For This Slice

### Long-Term Kernel Remains C++

The existing C++ plugin scaffold remains the intended long-term kernel direction.

### Short-Term Live Bootstrap Uses Python

Add a minimal Python plugin/bridge specifically for the first live vertical slice.

Responsibilities of the Python bridge:

- be discoverable and loadable by the real MO2 instance
- receive `init(organizer)` successfully
- write fresh runtime evidence files on load
- describe the minimal command slice it supports
- emit diagnostics useful for live debugging

This Python bridge is a bootstrap bridge, not the final transport architecture.

## Source And Deployment Shape

### Repo Source

Add the Python bridge source under a dedicated subtree, for example:

- `tools/mo2-control-plane/live-bridge/`

This subtree should contain:

- the minimal Python plugin file
- deployment helper(s) if needed
- small docs explaining what is copied into the live MO2 sandbox

### Live Deployment Target

Deploy into the real sandbox under:

- `D:\awesome-bgs-mod-master\.artifacts\mo2\plugins\`

The bridge should be visible to MO2 as a real Python plugin.

## File-Bootstrap Discovery

The first live slice should publish evidence through files, not a live IPC server.

Recommended runtime file root:

- `D:\awesome-bgs-mod-master\.artifacts\mo2\plugins\data\mo2-agent-control\`

Recommended files:

- `status.json`
- `capabilities.json`
- `endpoint.json`

### status.json

Purpose: prove the plugin was actually loaded by the current MO2 process.

Suggested fields:

- plugin name
- bootstrap mode
- loaded timestamp
- MO2 process id
- game name
- selected profile

### capabilities.json

Purpose: describe the minimal live command surface.

Suggested fields:

- protocol version
- supported commands
- command classes or slice marker

For this slice the required commands are only:

- `system.ping`
- `system.capabilities`

### endpoint.json

Purpose: publish discovery information for the broker.

For this slice, `endpoint.json` can truthfully say that the transport is file-bootstrap based.

Suggested fields:

- `transport = file-bootstrap`
- runtime root path
- future endpoint placeholder

This keeps the broker-facing concept of endpoint discovery intact while avoiding premature IPC complexity.

## Broker Behavior In This Slice

The broker should gain a real-live mode for only two commands:

- `system.ping`
- `system.capabilities`

In live mode:

- `system.ping` reads `status.json`
- `system.capabilities` reads `capabilities.json`
- discovery information comes from `endpoint.json` or the agreed runtime root
- missing, stale, or malformed files must fail closed

The broker must not fabricate success if the live runtime evidence is absent.

## Freshness Requirement

This is the most important anti-false-positive rule for the slice.

Before claiming live success, tests should clear the runtime evidence directory and then require the plugin to recreate those files.

That means success evidence is:

1. runtime files absent
2. MO2 starts or restarts
3. runtime files reappear with fresh data
4. broker consumes that fresh data successfully

Without this rule, stale files could masquerade as current live success.

## Testing Strategy

### Contract Tests

Continue adding fast repo-local tests that lock:

- live bridge source layout
- deployment path rules
- broker file-bootstrap parsing
- fail-closed behavior when runtime evidence is missing or malformed

### Real Live Tests

The real live TDD loop for this slice should be:

1. remove existing runtime bootstrap files
2. start or restart `.artifacts/mo2/ModOrganizer.exe`
3. verify the plugin is listed in `Tools -> Tool Plugins`
4. verify fresh runtime files are recreated
5. run broker `system.ping`
6. run broker `system.capabilities`

This gives both human-visible and machine-readable evidence.

## Evidence For Slice Completion

This slice is complete only when all of the following are true:

1. the live Python bridge is installed under the real MO2 sandbox
2. the real MO2 instance loads it successfully
3. fresh `status.json`, `capabilities.json`, and `endpoint.json` are recreated after runtime cleanup
4. broker `system.ping` returns success from live bootstrap data
5. broker `system.capabilities` returns success from live bootstrap data

## Non-Goals For This Slice

This slice explicitly does not yet require:

- real IPC server transport
- real `launch.start`
- real `mo2-vfs-launcher`
- real `xedit-cli`
- full plugin management or mod/plugin list control in live mode

Those come later, after live plugin load and bootstrap discovery are stable.

## Why This Work Will Still Matter Later

Although this slice uses file-bootstrap discovery instead of real IPC, it is not throwaway if designed carefully.

The broker-facing meaning of:

- `system.ping`
- `system.capabilities`
- endpoint discovery

should remain stable. Later work can replace file-bootstrap internals with true IPC while preserving the same high-level command contracts.

## Summary

The live bootstrap slice is the smallest real MO2 integration that proves our control plane is no longer purely synthetic. It establishes a trustworthy, fresh, machine-readable foothold inside the real MO2 process and creates the base that later live transport and launch work can safely build on.
