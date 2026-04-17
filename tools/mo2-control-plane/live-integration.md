# MO2 Control Plane Live Integration

## Live Sandbox

- Use the existing live sandbox root at `.artifacts/mo2/`.
- Keep `.external-resource/Mod.Organizer-2.5.3dev7.exe` immutable; use it only if the sandbox must be reprovisioned.
- The current sandbox already manages a real `Fallout 4` instance.

## Plugin Install

- Build the plugin binary from `tools/mo2-control-plane/plugin/`.
- Install the built plugin payload under `.artifacts/mo2/plugins/Mo2AgentControl/`.
- Deploy `mo2_agent_control.py` to `.artifacts/mo2/plugins/mo2_agent_control.py` so MO2 scans it on startup.
- Keep the plugin payload inside the sandboxed MO2 tree, not in source control.
- Deploy the Python live bridge with `pwsh -NoProfile -File tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1 -Mo2Root D:\awesome-bgs-mod-master`.
- Treat the built MO2 plugin payload and `mo2_agent_control.py` as separate requirements for the green run; the Python bridge belongs at the plugin root, while runtime files are recreated under `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime`.

## Live Bootstrap Harness

- Run the real bootstrap harness only with explicit opt-in because it clears `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime`.
- Red check before deployment/load: `pwsh -NoProfile -File tests/mo2-control-plane/live-bootstrap-real.test.ps1 -AllowLiveSandbox`.
- Green check with bridge deployment and an MO2 restart: `pwsh -NoProfile -File tests/mo2-control-plane/live-bootstrap-real.test.ps1 -AllowLiveSandbox -DeployBridge -RestartMo2`.
- The harness targets `D:\awesome-bgs-mod-master\.artifacts\mo2`, verifies `status.json`, `capabilities.json`, and `endpoint.json` are missing before startup, then waits for fresh recreation after MO2 starts or restarts.
- `status.json` now includes `mo2Pid` so the broker can reject stale bootstrap evidence from a dead MO2 process.
- `endpoint.json` now locks `transport: named-pipe` plus an endpoint field carrying the pipe name or endpoint value.
- File-bootstrap remains the discovery and liveness layer; local `system.*` broker requests now use the named-pipe endpoint for real request/response transport.
- If MO2 is already open, close it first or use `-RestartMo2` so the bootstrap evidence comes from the current live load instead of stale runtime files.

## Broker Endpoint

- Automatic endpoint discovery now feeds a real local named-pipe runtime for `system.ping`, `system.capabilities`, and `launch.*`.
- The discovery contract is `endpoint.json` with `transport: named-pipe` plus a pipe name or endpoint field.
- The published named-pipe endpoint must be instance-specific to the current live MO2 process so discovery cannot accidentally bind to another MO2 instance on the same machine.
- File-bootstrap remains the local discovery/liveness source, not as the command transport.
- The Python plugin now tracks real `launch.start/status/wait/stop` state over named-pipe transport using harmless local targets for verification.
- `tests/mo2-control-plane/live-ipc-real.test.ps1` deploys those harmless `.cmd` targets under `.artifacts/mo2/plugins/Mo2AgentControl/harness/` so the launch flow stays inside the sandboxed MO2 plugin tree while still using benign `cmd.exe /c` entry points.
- The real harnesses share the same named system mutex keyed to `.artifacts/mo2/ModOrganizer.exe` before deploy/restart/discovery work so the live sandbox remains serial and single-instance-safe across bootstrap, ping, and IPC checks.
- Scope stays tight in this slice: the named-pipe round-trip now covers `system.*` plus harmless `launch.*` process control. Real `usvfs`-aware launch behavior remains for later slices.
- The endpoint stays local-only; do not treat it as a remote service.

## Verify Plugin Load

1. Start `.artifacts/mo2/ModOrganizer.exe`.
2. Open `Tools -> Tool Plugins` and confirm the MO2 control-plane plugin is listed and enabled.
3. Confirm fresh `status.json`, `capabilities.json`, and `endpoint.json` recreation under `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime`.
4. Confirm `status.json` carries `schemaVersion: 1`, `state: ok`, and an `mo2Pid` that matches the running `ModOrganizer.exe` process.
