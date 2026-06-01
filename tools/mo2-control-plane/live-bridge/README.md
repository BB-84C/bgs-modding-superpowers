# MO2 Live Bridge

This subtree holds the live bridge source for the current named-pipe discovery and real IPC slice.

- Source lives in `tools/mo2-control-plane/live-bridge/`.
- The expected deployment target for `mo2_agent_control.py` is `<MO2_Root>/plugins/mo2_agent_control.py`.
- The earlier scaffold-only slice was a source-level contract only.
- `mo2_agent_control.py` now exposes `createPlugin()` as a real MO2 Python plugin entrypoint.
- Support files stay under `<MO2_Root>/plugins/Mo2AgentControl/`.
- This slice now publishes bootstrap runtime files into `<MO2_Root>/plugins/Mo2AgentControl/bootstrap/runtime` during plugin initialization in `init(organizer)`, not at bare import.
- Scope stays tight: the bridge now runs a real local named-pipe server for `system.*` and harmless `launch.*` checks, but broader `usvfs`-aware launch behavior remains for later slices.
- File-bootstrap is retained only as discovery and liveness, not as the command transport.
- Locked runtime file names: `status.json`, `capabilities.json`, and `endpoint.json`.
- Locked command-handler method anchors in the Python bridge: `system.ping`, `system.capabilities`, `launch.start`, `launch.status`, `launch.wait`, and `launch.stop`.
- Locked minimum JSON fields:
  - `status.json`: `schemaVersion`, `state`, `mo2Pid`
  - `capabilities.json`: `schemaVersion`, `methods`
  - `endpoint.json`: `schemaVersion`, `transport`, and the endpoint field `endpoint`
- Published minimum bootstrap payloads currently use `schemaVersion: 1`, `state: ok`, a live-runtime identity field `mo2Pid`, `methods` that advertise both `system.*` and `launch.*`, `transport: named-pipe`, and an instance-specific endpoint value that carries the current MO2 process pipe name.
- This remains a source-level contract only: endpoint.json now describes named-pipe discovery, while file-bootstrap remains the local discovery/liveness layer.
- Launch support now includes the earlier contract scaffolding plus real harmless-process handling in this slice:
  - `LAUNCH_COMMAND_CONTRACTS` locks required payload/result fields for `launch.start/status/wait/stop`.
  - `create_launch_registry()` returns `{ "launches": {} }`.
  - `create_launch_registry_entry()` reserves bookkeeping fields `launch_id`, `session_id`, `target_path`, `args`, `cwd`, `env`, `pid`, `process_handle`, `status`, `started_at`, `updated_at`, `exit_code`, and `artifacts`.
  - Locked registry status values are `pending`, `running`, `completed`, and `stopped`.
  - Newly created registry entries still begin in a pending/scaffold state before a real pid/process handle is attached.
  - Launch handlers now implement real `launch.start/status/wait/stop` behavior for organizer-backed or narrow local harmless targets.
