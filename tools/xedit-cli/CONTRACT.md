# xedit-cli Contract

This document defines the production-launch target contract for later Phase 1 work. It is not a claim that every command below already exists in the current slice.

The runtime target is `xedit-cli -> control plane -> mo2-vfs-launcher -> xEdit`. xedit-cli should launch through the MO2 control plane, with mo2-vfs-launcher as the generic VFS-side child launcher. The control plane owns the brokered MO2 launch handshake, mo2-vfs-launcher owns the generic VFS-side child launch, MO2/usvfs owns the real plugin/file-tree semantics, and real verification uses the project-local MO2 sandbox at `.artifacts/mo2` as the authoritative real verification sandbox.

## Goals

- orchestrate upstream xEdit while keeping the wrapper external and no-fork
- keep xEdit external as the execution engine while the target CLI flow reaches xEdit only through the control plane and mo2-vfs-launcher chain
- run wrapper-owned Pascal scripts
- expose read-only conflict indexing and inspection as the primary public surface
- store run artifacts in a SQLite-backed query layer
- normalize output for progressive-disclosure agent consumption
- accept a caller-provided launcher path instead of discovering MO2 inside the CLI
- use raw PID addressing for launched-process control
- preserve a step-1 hook bridge for Module Selection as supporting launch/session plumbing with auto-confirm and diagnostics only

## Read-Only Commands

### `xedit-cli doctor env`

Current-slice implementation: `doctor env` is the standalone explicit-mode-launch preflight. It validates the caller-provided `--launcher-path` plus authoritative `--game-mode` before launch shaping and can validate an optional `--xedit-pid` when the caller already has one. Richer plugin-source and script validation stay planned for the production-launch target in later Phase 1 work.

### `xedit-cli conflicts index`

Target flow: run a read-only conflict indexing path. The first live `conflicts index` launch path requires both `--launcher-path` and authoritative `--game-mode`, routes launch through the MO2 control plane and mo2-vfs-launcher with the explicit mapped mode argument instead of filename inference, uses the mapping `Fallout4 -> -FO4`, `Skyrim -> -TES5`, `SkyrimSE -> -SSE`, and `Starfield -> -SF1`, and persists the results as run-scoped artifacts for later drilldown.

### `xedit-cli conflicts inspect`

Inspect one selected record from an indexed run and return a compact compare-style view instead of a whole-dataset dump.

### `xedit-cli process launch`

Target command surface: route xEdit launch through the MO2 control plane using a caller-provided launcher path and return the raw PID for later process control. Launcher-driven commands require authoritative `--game-mode`, and `--game-mode` is the primary trust and control signal for mode selection rather than executable-name-derived guessing. The CLI maps supported game modes to explicit xEdit mode arguments, specifically `Fallout4 -> -FO4`, `Skyrim -> -TES5`, `SkyrimSE -> -SSE`, and `Starfield -> -SF1`, including `SkyrimSE` to `-SSE`, then normalizes direct executables and simple `.bat`/`.cmd` wrappers to explicit launch commands while complex wrappers fail closed.

Step 1 established a step-1 hook bridge for `Module Selection`, but the launch contract now uses a single `load` semantic. The caller provides or implies the plugin set for the launch, `xedit-cli` writes a session-scoped `plugins.txt`, and xEdit is launched with the xEdit native `-P:` seam pointing at that session file. The real MO2 profile `plugins.txt` remains untouched. The MO2-backed environment remains the source of truth for full plugin order, hook.dll owns only xEdit in-process automation, and the hook contract is auto-confirm and diagnostics only. The hook is diagnostic only beyond auto-confirming the current selection. For real MO-backed launches, the minimal contract also accepts `--mo-profile <name>`, appends `-moprofile:"<name>"` to xEdit, and deploys the built bridge DLL to the xEdit-expected `..\Mod Organizer\hook.dll` path before the control-plane-mediated launch.

### `xedit-cli process status`

Target command surface: read process state by raw PID so callers can poll the launched xEdit instance directly.

### `xedit-cli process wait`

Target command surface: wait on a launched xEdit process by raw PID and surface timeout-aware completion status.

### `xedit-cli process stop`

Target command surface: stop a launched xEdit process by raw PID when the caller needs explicit cleanup.

## Future Write Commands

- create compatibility patch shells
- apply controlled scripted edits to a new patch plugin

## Safety Rules

- never edit source mods in place
- default to read-only mode
- require explicit patch targets for write operations
- keep SQLite as an internal artifact layer, not a user-facing dump format
- keep MO2 discovery outside the CLI and require callers to pass a launcher path in
- keep the MO2-backed environment as the source of truth for full plugin order during Module Selection
- keep the real MO2 profile `plugins.txt` untouched and write launch-specific state only into the session directory
