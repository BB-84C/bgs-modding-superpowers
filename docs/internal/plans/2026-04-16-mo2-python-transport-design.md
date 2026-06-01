# MO2 Python Transport And Launch Slice Design

## Goal

Define the next real MO2 control-plane slice: replace file-bootstrap as the command transport with a real local IPC channel implemented in the Python plugin, and add the smallest real `launch.start/status/wait/stop` family on top of that transport.

This slice builds directly on the completed live bootstrap work. The bootstrap files remain, but only as discovery and liveness evidence. Actual command execution moves to a real broker-to-plugin transport.

## Current State

The worktree already has:

- broker/session/protocol scaffolding
- primitive command contracts
- fake-kernel launch flow
- `mo2-vfs-launcher` and `xedit-cli` rebased onto the control-plane architecture
- a real Python plugin that loads in the live MO2 sandbox
- fresh runtime evidence files under `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime`
- real broker `system.ping` and `system.capabilities` using file-bootstrap evidence

What is still missing is real command transport and real launch execution from inside the live MO2 plugin.

## Why Python-First Is The Right Next Step

The current MO2 installation and upstream code show that Python plugins are first-class citizens for many plugin categories.

Observed examples in the live sandbox include:

- `FNISTool.py` implementing `mobase.IPluginTool`
- `Form43Checker.py` implementing `mobase.IPluginDiagnose`
- `pyCfg.py` implementing `mobase.IPluginTool`

These Python plugins already use capabilities such as:

- `organizer.startApplication(...)`
- `organizer.waitForApplication(...)`
- `organizer.profile()`
- `organizer.pluginList()`
- `organizer.modList()`

That means the shortest correct path is not to switch immediately to a C++ DLL. The shortest correct path is to keep the real live implementation in Python and use the existing C++ scaffold only as a future option.

## Approaches Considered

### Option 1: Python plugin plus real local IPC plus minimal launch family

This keeps the current live bridge and upgrades it into a true command transport endpoint for the broker.

This is the recommended approach.

### Option 2: Python plugin plus file queue transport

This avoids IPC server implementation, but it turns file-bootstrap into an oversized command channel and makes `launch.wait/stop` awkward and fragile.

### Option 3: Switch primary implementation to C++ now

This could eventually provide a harder native kernel, but it adds unnecessary build and integration complexity before the Python route has hit a real capability wall.

## Recommended Architecture

### Bootstrap Discovery Remains

The existing runtime files stay in place:

- `status.json`
- `capabilities.json`
- `endpoint.json`

But their role changes.

They are no longer treated as the main transport. They become:

- plugin liveness evidence
- endpoint discovery
- minimal bootstrap/fallback data

### Real Transport Becomes Local IPC

The Python plugin starts a local IPC server after successful plugin initialization.

The broker reads `endpoint.json`, discovers the local IPC endpoint, and then sends real request/response envelopes over that channel.

### Why Named Pipe

The recommended transport is a local named pipe.

Reasons:

- local-only semantics fit the control-plane model
- native fit for the Windows environment in which MO2 is running
- request/response behavior is straightforward
- much better suited than file polling for `launch.wait`, `launch.stop`, and structured error propagation

## Command Scope For This Slice

This slice should expose only the smallest real transport command family:

- `system.ping`
- `system.capabilities`
- `launch.start`
- `launch.status`
- `launch.wait`
- `launch.stop`

It does not yet need:

- `mo2-vfs-launcher` live transport wiring
- `xedit-cli` live transport wiring
- profile switching through live IPC
- broad mod/plugin write control

## Transport Contract

The request/response envelope should stay compatible with the current control-plane protocol.

Request:

```json
{
  "protocol_version": "1",
  "request_id": "req-...",
  "session_id": "sess-...",
  "command": "launch.start",
  "payload": {}
}
```

Response:

```json
{
  "protocol_version": "1",
  "request_id": "req-...",
  "session_id": "sess-...",
  "ok": true,
  "result": {},
  "error": null
}
```

The broker remains free to expose richer CLI UX, but the transport contract should remain small, rigid, and versioned.

## Launch Contract

### launch.start

Payload:

- `target_path`
- `args`
- `cwd`
- `env`
- `session_id`

Result:

- `launch_id`
- `pid`
- `status`
- `started_at`
- `artifacts`

### launch.status

Payload:

- `launch_id`

Result:

- current status
- pid
- known exit metadata if available

### launch.wait

Payload:

- `launch_id`
- optional timeout

Result:

- final or current status after waiting

### launch.stop

Payload:

- `launch_id`

Result:

- stop outcome

## Launch Registry

The Python plugin should maintain a minimal launch registry in memory.

The registry only needs to know enough to support the commands above:

- `launch_id`
- session association
- pid or process handle reference
- current status
- timestamps
- optional exit code

This slice should not introduce complex process-tree management.

## Safety Constraints

- broker must not fabricate launch success
- plugin must fail closed on malformed commands or missing launch ids
- all real MO2 live tests that restart the sandbox must run serially
- only the sandboxed `ModOrganizer.exe` path may be stopped/restarted by tests
- transport discovery should remain local-only and not drift toward network-service semantics

## Testing Strategy

### Contract Tests

Lock:

- endpoint.json named-pipe discovery shape
- broker/client pipe request and response handling
- launch envelope and result fields
- fail-closed behavior on bad payloads, missing launch ids, unsupported commands, and timeouts

### Plugin-Local Tests

Lock Python plugin behavior for:

- server bootstrap lifecycle
- command dispatch
- launch registry transitions
- `launch.wait` and `launch.stop` semantics

### Real Live Tests

Run serially only.

Suggested order:

1. deploy bridge
2. clear bootstrap/runtime
3. restart sandboxed MO2
4. wait for fresh runtime evidence and endpoint discovery
5. broker `system.ping` over real IPC
6. broker `system.capabilities` over real IPC
7. broker `launch.start` using a harmless target such as `cmd.exe /c exit 0`
8. broker `launch.status`
9. broker `launch.wait`
10. broker `launch.stop` where applicable using a longer-lived harmless target

## Slice Completion Criteria

This slice is complete only when all of the following are true:

1. bootstrap discovery still works in the real MO2 sandbox
2. broker `system.ping` works over real IPC, not just file-bootstrap
3. broker `system.capabilities` works over real IPC
4. broker `launch.start/status/wait/stop` work against the real live plugin
5. at least one harmless real target process is launched and tracked through the full launch lifecycle

## Non-Goals

This slice does not yet require:

- real `mo2-vfs-launcher` transport wiring
- real `xedit-cli` transport wiring
- xEdit live launch
- high-risk mod/plugin write workflows
- replacing the C++ scaffold entirely

## Summary

The next phase upgrades the control plane from live bootstrap evidence to a real command plane. Python remains the practical implementation language because MO2 already exposes the needed organizer-facing APIs there. The file-bootstrap layer remains useful, but only as discovery and liveness evidence; the real control surface moves to local IPC plus the smallest real launch family.
