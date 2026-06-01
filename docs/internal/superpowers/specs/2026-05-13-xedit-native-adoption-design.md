# Native xEdit Adoption and External Client Consolidation Design

**Date:** 2026-05-13

## Summary

Adopt the native xEdit automation surface from `D:\TES5Edit-contrib` as the single owner of xEdit business semantics, remove the legacy `tools/xedit-hook-bridge` path entirely, and retire the xEdit-semantic portions of `tools/xedit-cli`.

The remaining external responsibilities — MO2/VFS bootstrap, session-scoped `plugins.txt` generation, launcher normalization, PID lifecycle, and run-artifact preservation — will be kept in this repo and moved into an xEdit-specific outer client layer adjacent to `tools/mo2-vfs-launcher`.

The resulting long-term chain is:

```text
caller / harness / future MCP
  -> tools/mo2-control-plane
  -> tools/mo2-vfs-launcher (generic launcher)
  -> tools/mo2-vfs-launcher xEdit outer client layer
  -> MO2-managed OpenCodeXEdit xEdit.exe
  -> native xEdit automation-serve / automation-call JSON protocol
```

## Problem Statement

This repo currently carries two older xEdit-side layers:

1. `tools/xedit-hook-bridge/` — a native DLL that auto-handles startup blockers around Module Selection and writes hook diagnostics.
2. `tools/xedit-cli/` — a PowerShell wrapper that mixes together:
   - MO2/control-plane launch plumbing,
   - session plugin-file preparation,
   - hook-session management,
   - PID lifecycle helpers,
   - wrapper-owned conflict indexing semantics,
   - placeholder Pascal-script-based external xEdit workflows.

Those layers were reasonable when the external wrapper had to compensate for missing native automation seams.

That is no longer the design center. The fork at `D:\TES5Edit-contrib` now already proves native automation against the current MO2 harness, including real patching and conflict-driven workflows. Keeping parallel xEdit control semantics in this repo would duplicate substrate, preserve obsolete scaffolding, and blur the boundary between xEdit logic and MO2 harness logic.

## Goals

- Make native xEdit automation the only owner of xEdit business semantics.
- Remove the hook-based startup automation path from this repo.
- Remove wrapper-owned xEdit semantic surfaces from `tools/xedit-cli`.
- Preserve the MO2/runtime harness responsibilities that still belong outside xEdit.
- Re-home the surviving external xEdit client logic next to `tools/mo2-vfs-launcher` rather than leaving it under a misleading `xedit-cli` identity.
- Keep the generic launcher generic; xEdit-specific logic should live in a neighboring outer client layer, not inside the generic launcher core.
- Preserve the current safety model: no Stock Game `Data` mutation, MO2 overlay/overwrite discipline, explicit runtime artifacts, and real semantic verification.

## Non-Goals

- Do not redesign the MO2 control plane itself.
- Do not move MO2/VFS responsibilities into xEdit.
- Do not preserve wrapper-owned xEdit semantics just for backward familiarity.
- Do not keep `tools/xedit-cli` as a second canonical API for records/conflicts/jobs/scripts.
- Do not keep a compatibility shim for `xedit-cli` after this migration.
- Do not mutate `Stock Game\Fallout 4\Data` as part of this refactor.

## Existing Roles To Preserve Versus Remove

### Remove entirely

#### `tools/xedit-hook-bridge`

Retire the full hook bridge path, including:

- the DLL build and deployment flow,
- hook-session environment variables and status files,
- Module Selection auto-confirm logic,
- startup interstitial dismissal logic,
- VCL/window probing that exists only to support the hook-driven startup path.

Rationale: the native xEdit automation fork already solves startup readiness structurally through native automation modes and autoload semantics. The hook bridge is no longer the least-intrusive seam.

### Remove from `tools/xedit-cli`

Retire every xEdit-semantic layer that duplicates or substitutes for the native automation surface, including:

- `doctor env` checks that exist only to police wrapper-era xEdit launch shapes,
- `conflicts index` and `conflicts inspect`,
- wrapper-owned Pascal-script orchestration,
- SQLite conflict indexing as a canonical external semantic layer,
- hook-session plumbing,
- schema and fixture layers whose purpose was to stabilize the wrapper contract rather than consume the native contract.

### Preserve, but re-home

Keep the external responsibilities that still belong to the harness side:

- generating a run-scoped `plugins.txt` when the run needs a custom plugin set without mutating the real MO2 profile,
- passing `-P:<path>` to xEdit,
- mapping approved game modes to xEdit startup arguments,
- resolving simple wrapper launchers into explicit executable launches,
- issuing MO2 control-plane launch requests,
- capturing PID and spawned-process lifecycle state,
- preserving request/response/readback artifacts for agentic verification.

These responsibilities remain real, but they should no longer live in a directory whose identity implies it owns xEdit semantics.

## Ownership Boundary

### Native xEdit owns

The xEdit fork at `D:\TES5Edit-contrib` is the single owner of:

- CLI / serve / call automation protocol,
- files / records / elements / scripts / jobs surfaces,
- conflict status and conflict drilldown semantics,
- validation, cleaning, patching, save, and mutation boundaries,
- any future xEdit-side business semantics.

### This repo owns

`D:\awesome-bgs-mod-master` remains the single owner of:

- MO2 runtime harness state under `.artifacts/mo2`,
- control-plane and launcher integration,
- session-scoped `plugins.txt` derivation from the current MO2 profile or run-local needs,
- launch-shaping and process lifecycle,
- orchestration artifacts and verification evidence,
- repo-local runtime discipline and non-destructive harness behavior.

### Two-stage `plugins.txt` responsibility

The custom plugin-list path remains intentionally split:

1. **External client responsibility in this repo**: decide whether a run needs a custom plugin list, generate the session-scoped `plugins.txt`, and pass `-P:<path>` during launch.
2. **Native xEdit responsibility**: parse `-P:`, read that file, and perform the actual plugin loading.

This keeps run-specific profile shaping outside xEdit while keeping actual load semantics inside xEdit.

## Selected Approach

### Approach B: Remove hook bridge, strip xEdit semantics from `xedit-cli`, and consolidate the surviving client into the `mo2-vfs-launcher` neighborhood

This is the selected approach.

The generic launcher remains generic:

- `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- `tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd`
- `tools/mo2-vfs-launcher/mo2-vfs-probe.ps1`

The xEdit-specific outer client becomes a neighboring layer rooted at:

- `tools/mo2-vfs-launcher/xedit-client.ps1`
- helper modules under `tools/mo2-vfs-launcher/lib/`

The outer client will:

- create or reuse a run-scoped session directory,
- derive a run-scoped `plugins.txt` when needed,
- shape launch args for native xEdit automation mode,
- call into the existing control-plane / VFS launcher stack,
- wait for the native automation endpoint to become ready,
- issue native JSON requests,
- preserve launch/request/response/readback artifacts.

It will not redefine xEdit semantics.

## Naming and Placement Decision

The new xEdit-specific outer client should live adjacent to `mo2-vfs-launcher`, not inside the generic launcher script.

Chosen default:

- entrypoint: `tools/mo2-vfs-launcher/xedit-client.ps1`
- helpers: `tools/mo2-vfs-launcher/lib/*.ps1` as needed

Rationale:

- `mo2-vfs-launcher` stays tool-agnostic,
- xEdit-specific launch/client logic remains easy to find,
- the repository boundary becomes honest: launcher core versus xEdit consumer layer.

## Compatibility Decision

No compatibility shim will be kept for `tools/xedit-cli/bin/xedit-cli.ps1`.

This migration intentionally removes the old command identity instead of leaving a thin forwarding shell.

Rationale:

- the old name implies a semantic role we are explicitly retiring,
- a shim would prolong dual-surface ambiguity,
- the caller and harness should be updated to the new boundary immediately.

## Affected Surfaces

### Remove

- `tools/xedit-hook-bridge/**`
- hook-related test files under `tests/xedit-cli/**`
- wrapper-owned conflict/schema/script/fixture surfaces under `tools/xedit-cli/**` that no longer belong in the long-term design

### Re-home / replace

- external launch/client logic currently under `tools/xedit-cli/bin/` and `tools/xedit-cli/lib/`
- docs that still describe `xedit-cli` as the semantic public surface
- test entrypoints that still call old wrapper commands instead of the new xEdit outer client

### Preserve as-is in role, not necessarily in exact file placement

- `tools/mo2-control-plane/**`
- `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- `tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd`
- `tools/mo2-vfs-launcher/mo2-vfs-probe.ps1`
- MO2 sandbox and OpenCodeXEdit target discipline under `.artifacts/mo2`

## Verification Strategy

Verification must prove the new boundary, not merely that files moved.

### Required proofs

1. `tools/xedit-hook-bridge` is no longer needed anywhere in the runtime path.
2. The new outer client can launch native xEdit under MO2 using the approved runtime chain.
3. A run-scoped `plugins.txt` can still be generated externally and consumed by native xEdit through `-P:`.
4. Native `automation-serve` readiness is detected from the external client path.
5. Native request/response workflows operate through the new outer client without falling back to old wrapper semantics.
6. Existing harness discipline remains intact: no direct Stock Game `Data` writes, no silent mutation of the real MO2 profile `plugins.txt`, and preserved runtime artifacts.

### Minimum semantic validation scenarios

- launch a real MO2-backed native xEdit automation session,
- verify the intended plugin view is seen through the external `plugins.txt` handoff path when a run-scoped list is required,
- issue at least one native read-side automation request through the new outer client,
- issue at least one native mutation-capable request only if the existing verification harness already has an approved safe target and readback path,
- confirm request/response/readback artifacts are preserved under a repo-local artifact root.

## Migration Sequencing

1. Remove hook-specific runtime and test dependencies from the design target.
2. Stand up the new xEdit outer client next to `mo2-vfs-launcher` using only the external responsibilities that remain valid.
3. Rewire callers and verification harnesses to launch native automation through the new outer client.
4. Remove the old `xedit-cli` semantic surfaces and the `xedit-hook-bridge` directory.
5. Rewrite docs/tests/contracts to reflect the new boundary truth.

This order keeps the boundary transition legible and avoids preserving legacy identities longer than needed.

## Rejected Alternatives

### Keep the hook bridge and use the native fork only for some commands

Rejected because it preserves two in-process startup-control models at once and keeps obsolete GUI automation alive after the native fork already proved the real path.

### Keep `xedit-cli` mostly intact and just re-point its internals

Rejected because the name and contract would continue to imply that this repo owns an xEdit semantic wrapper. That is exactly the ambiguity this migration is meant to remove.

### Delete `xedit-cli` wholesale and rewrite a brand new client from scratch before reusing any current harness logic

Rejected because the surviving launch/process/plugin-list logic is still useful and already grounded in the repo's MO2 control-plane environment. The goal is boundary correction, not ceremonial reimplementation.

## Final Design Decision

Proceed with the following end state:

1. remove `tools/xedit-hook-bridge` entirely,
2. retire the xEdit-semantic surfaces of `tools/xedit-cli`,
3. keep only the external MO2/harness responsibilities,
4. move those responsibilities into an xEdit-specific outer client adjacent to `tools/mo2-vfs-launcher`,
5. treat native xEdit automation from `D:\TES5Edit-contrib` as the sole owner of xEdit business semantics.

This keeps the long-term seam narrow, honest, and maintainable.
