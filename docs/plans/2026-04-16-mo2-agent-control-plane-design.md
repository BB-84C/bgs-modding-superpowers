# MO2 Agent Control Plane Design

## Goal

Define a durable MO2 automation substrate that lets future agents control Mod Organizer 2 through structured commands rather than fragile GUI-driving or ad hoc command-line seams.

This control plane must be broad enough to eventually support high-value curator workflows across the repo, including launch orchestration, profile-aware runtime control, mod/plugin inspection, and later higher-risk write operations, while keeping the first shipped slice deliberately narrow and safe.

## Why This Supersedes The Earlier Launcher-Only View

The earlier `mo2-vfs-launcher` design correctly identified a real need: tools such as `xedit-cli` need a reusable way to launch inside MO2/usvfs semantics.

What changed is the system-level understanding. The repository is not trying to solve one launch problem in isolation. Its mission is to support end-to-end BGS modpack curation workflows for future agents. In that context, MO2 launch control is only one member of a larger family of organizer control needs.

Therefore the correct abstraction is no longer a single launcher entrypoint. It is an MO2 control plane, with `mo2-vfs-launcher` repositioned as one early consumer built on top of that control plane.

## Product Context

The repo mission and roadmap already point in this direction:

- the project exists for workflow-first BGS modpack curation across Skyrim, Fallout 4, and Starfield
- MO2 execution is a named workflow step in the roadmap
- the current xEdit work intentionally keeps MO2 discovery outside `xedit-cli`
- the repo needs stable, agent-facing command surfaces rather than brittle manual procedures

The resulting architecture should treat MO2 as a controllable subsystem in the larger agent ecosystem, not just a GUI tool the agent occasionally launches.

## Alternatives Considered

### Option 1: Keep expanding `ModOrganizer.exe run ...` and wrapper tools

This is the lightest apparent path, but it leaves the architecture dependent on MO2's existing command forwarding and CLI behavior. That behavior is already proving brittle in the current environment and does not provide a stable, broad control plane.

### Option 2: MO2 plugin kernel plus external broker CLI

This creates a thin in-process control kernel inside MO2 and a separate agent-facing broker outside MO2. The kernel owns access to MO2 internals; the broker owns stable RPC contracts, session handling, and future workflow composition.

This is the recommended design.

### Option 3: Full plugin monolith

This puts both low-level primitives and high-level workflow semantics into a single large MO2 plugin. It is technically possible, but it would entangle UI-hosted plugin code with evolving agent workflow behavior and make long-term maintenance harder.

## Recommended Architecture

### Layer 1: MO2 Plugin Kernel

The MO2 plugin kernel runs inside the primary MO2 instance and is the only layer that directly touches MO2 internals.

Responsibilities:

- register supported commands
- validate command payloads at the MO2 boundary
- access profiles, executables, mod list, plugin list, and refresh facilities
- launch tools in MO2/usvfs context through MO2's own internal APIs
- return structured status and error results

Non-responsibilities:

- broad modpack workflow orchestration
- agent-facing UX shaping
- long-form reporting or workflow semantics
- repository-specific business rules that do not need MO2 internals

### Layer 2: Local RPC Transport

The plugin kernel exposes a strictly local transport. This is not a network service and should not be designed as one.

Requirements:

- local-only communication
- request/response in structured JSON
- stable framing for command invocation
- predictable connection behavior for automated tooling

The exact local transport can be chosen during implementation, but the architecture assumes a robust local IPC primitive such as a named pipe or socket-style endpoint rather than GUI automation.

### Layer 3: External Broker CLI

The external broker CLI is the repo-facing and agent-facing command surface.

Responsibilities:

- shape agent-friendly CLI commands into RPC requests
- own session IDs, request IDs, and artifact layout
- normalize output into machine-readable responses
- preserve state and evidence for later tools and workflows
- become the stable integration point for future skills, MCPs, and tool adapters

This broker is where future agents should primarily integrate. Agents should not speak directly to MO2 internals.

### Layer 4: Tool Adapters And Workflows

Examples:

- `mo2-vfs-launcher`
- `xedit-cli`
- future install planner executors
- localization helpers
- test-session tooling

These consumers should build on broker commands instead of re-implementing MO2 control independently.

## Scaffold-First Principle

The first deliverable should be the control-plane scaffold, not a collection of isolated features.

The scaffold must include:

1. plugin kernel bootstrap and registration
2. local RPC transport
3. versioned request/response envelope
4. capability discovery
5. session and artifact model
6. broker CLI
7. test harness

This ensures that later features can be added quickly because they share the same protocol, state model, and evidence path.

## Initial Command Families

### Foundation Commands

These commands prove the substrate exists and let agents discover what is available.

- `system.ping`
- `system.capabilities`
- `system.status`
- `session.open`
- `session.close`
- `session.artifacts`

### Read / Control Primitives

These commands form the first useful MO2 control surface.

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

This set is broad enough to support the first meaningful consumers without prematurely opening dangerous write-heavy automation.

### Higher Workflow Consumers

These should be built on top of the primitives rather than fused into the kernel.

- `mo2-vfs-launcher`
- `xedit-cli` live launch integration
- install execution workflows
- conflict resolution helpers
- localization flows
- testing flows

`mo2-vfs-launcher` should be the first consumer implemented on top of the new control plane.

## Protocol Contract

All commands should use a versioned envelope.

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

The broker should be free to expose richer CLI UX, but the kernel-facing protocol should stay compact and rigid.

## Error Model

Failures must be structured, not free-text-only.

At minimum the model should distinguish:

- `transport_error`
- `protocol_error`
- `validation_error`
- `mo2_state_error`
- `launch_error`
- `unsupported_command`
- `internal_error`

This allows future agents to distinguish between retryable transport issues, bad requests, unsupported features, and real MO2 runtime failures.

## Session And Artifact Model

Sessions are first-class objects.

Within a session, launches and other operations should produce durable artifacts such as:

- request snapshots
- response snapshots
- structured state files
- logs
- exported probe results
- downstream tool outputs

This shared model is important because it turns the control plane into a reusable evidence spine for many later workflows.

## Safety And Future Dangerous Operations

The first slice should not expose dangerous bulk operations such as broad install/remove automation or complex order rewriting.

However, the scaffold must still be designed so those operations can be added later without architectural rework.

The control plane should therefore support, from the beginning:

- command metadata and capability discovery
- command classes such as `safe-read`, `controlled-write`, and `dangerous-write`
- policy-gated execution
- dry-run planning where appropriate
- structured validation and precondition reporting
- stable artifact capture for later auditability

This is the key design principle: the initial surface stays conservative, but the substrate is shaped for future growth into higher-risk automation.

In other words, the system should be born extensible even if it initially ships cautiously.

## Why Not Mirror Every GUI Action First

A full command-control surface does not mean mechanically mirroring every current MO2 GUI interaction.

That would risk creating a thin textual shell around the existing UI instead of a stable automation substrate.

The kernel should expose meaningful primitives, not button-click emulations. Higher workflows can compose those primitives into agent-relevant behavior.

## Testing Strategy

Testing should be layered.

### Protocol Tests

Verify:

- schema correctness
- capability discovery
- error-code stability
- session and launch state transitions

### Plugin Integration Tests

Verify:

- plugin load/bootstrap behavior
- command registration
- access to profile, executable, mod, and plugin state
- launch primitive behavior under controlled conditions

### Real MO2 Environment Tests

Verify:

- real profile switching
- real executable launch
- real MO2/usvfs-backed launch semantics
- session/artifact persistence in live runs

`mo2-vfs-launcher` should become one of the earliest real end-to-end consumers used to prove the launch family.

## Delivery Direction

The next implementation phase should focus on:

1. creating the plugin kernel scaffold
2. creating the local RPC and capability discovery path
3. creating the broker CLI scaffold
4. wiring the first read/control primitives
5. rebuilding `mo2-vfs-launcher` as the first real consumer on top of the scaffold

This sequence matches the repo's long-term mission better than continuing to add isolated MO2-facing seams one tool at a time.

## Summary

The control-plane direction changes the center of gravity of the design:

- from a single launcher tool
- to a reusable MO2 automation substrate

That substrate should begin conservatively but be explicitly shaped for future broad control. If the scaffold is correct, later features can be added quickly without rethinking transport, state, safety, and artifact handling each time.
