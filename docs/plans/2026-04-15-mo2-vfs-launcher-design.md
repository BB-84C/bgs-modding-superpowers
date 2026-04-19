# mo2-vfs-launcher Design

## Goal

Add a reusable `mo2-vfs-launcher` layer that is started by Mod Organizer 2, inherits MO2/usvfs context, launches an arbitrary target tool inside that context, writes stable machine-readable launch state, and gives `xedit-cli` a clean integration point without moving MO2 discovery into the CLI itself.

## Problem Summary

The current repo already treats `xedit-cli` as an external orchestrator that accepts an explicit launcher path and keeps MO2 discovery outside the CLI. That boundary works for direct launcher execution, but it is not sufficient when the launched process must see MO2 profile semantics and the usvfs-backed virtual file tree.

Directly launching `FO4Edit.exe`, `SSEEdit.exe`, or `SF1Edit64.exe` does not provide MO2 profile or VFS semantics by itself, even if xEdit later loads its own `hook.dll` seam. The missing piece is the MO2/usvfs launch chain. The new launcher therefore needs to run inside MO2's already-established context, not recreate that context itself.

## Recommended Approach

Create a new `tools/mo2-vfs-launcher/` tool implemented first as PowerShell plus a `.cmd` wrapper.

Responsibilities are split as follows:

- MO2 remains responsible for selecting the profile, establishing usvfs, and exposing the virtualized filesystem view.
- `mo2-vfs-launcher` is responsible for parsing launcher arguments, applying environment variables, starting the target process, writing a structured state file, and surfacing failure clearly.
- The target tool is responsible for doing its own work after launch.
- `xedit-cli` remains an upper-layer orchestrator and only gains the minimum MO2-facing call path needed to ask MO2 to start the reusable launcher.

This keeps the current repo contract intact: MO2-aware launching becomes reusable infrastructure instead of special-case logic embedded inside `xedit-cli`.

## Alternatives Considered

### Option 1: Direct `ModOrganizer.exe run -e <tool>` calls everywhere

This is useful as a temporary proof that MO2/usvfs semantics are reachable, but it is too thin for stable reuse. Every caller would need to rebuild state-file handling, environment injection, and target launch shaping independently.

### Option 2: Fold MO2/VFS launch logic into `xedit-cli`

This looks smaller at first, but it breaks the repo's existing design boundary that keeps MO2 discovery outside the CLI and makes the result much less reusable for future non-xEdit tools.

### Option 3: Call usvfs APIs directly

This would be the most independent solution, but it is far too complex for the current stage and duplicates work MO2 already does reliably.

## Architecture

### Files

- `tools/mo2-vfs-launcher/mo2-vfs-launcher.ps1`
- `tools/mo2-vfs-launcher/mo2-vfs-launcher.cmd`
- `tools/mo2-vfs-launcher/mo2-vfs-probe.ps1`
- `tools/mo2-vfs-launcher/README.md`

Likely supporting tests and docs:

- `tests/mo2-vfs-launcher/*.ps1`
- targeted updates under `tools/xedit-cli/`

### Runtime Model

The launcher is started by MO2 as a configured executable, for example `OpenCodeVfsLauncher`.

External callers invoke MO2 with a profile and configured executable name:

```text
ModOrganizer.exe -p "CK与调试" run -e "OpenCodeVfsLauncher" -a "<launcher-args>"
```

By the time `mo2-vfs-launcher.ps1` begins execution, MO2/usvfs must already be active. The script does not discover mods, reconstruct plugin order, or call usvfs directly. It only launches the real target while preserving the inherited context.

## Input Contract

The first implementation should support the following arguments:

- `--target-path <absolute path>` required
- `--target-arg <value>` repeatable
- `--target-cwd <absolute path>` optional
- `--env KEY=VALUE` repeatable
- `--session-id <id>` required
- `--state-file <path>` required
- `--stdout-file <path>` optional
- `--stderr-file <path>` optional
- `--wait-mode spawned|exit` optional, default `spawned`
- `--timeout-seconds <n>` optional

The launcher must validate these inputs conservatively and fail closed on malformed or incomplete requests.

## Output Contract

The state file is the primary contract because standard output may be redirected or swallowed by MO2.

The state file format is JSON.

For `spawned` mode, the first successful write should contain at least:

```json
{
  "status": "spawned",
  "session_id": "abc123",
  "pid": 12345,
  "target_path": "B:\\...\\runFO4EditCN.bat",
  "target_cwd": "B:\\...\\Tools\\FO4Edit",
  "args": ["-some", "-args"],
  "started_at": "2026-04-16T02:10:00Z",
  "error": null
}
```

If `--wait-mode exit` is requested and the target finishes normally, the launcher updates the state with at least:

```json
{
  "status": "exited",
  "exit_code": 0,
  "finished_at": "2026-04-16T02:11:03Z"
}
```

If the launcher cannot start the target or the run times out, it must still write a final failure state such as:

```json
{
  "status": "failed",
  "session_id": "abc123",
  "error": "message..."
}
```

The launcher must prefer writing explicit failure state over silent termination.

## xedit-cli Integration

`xedit-cli` should not absorb MO2/VFS responsibility. It should remain an upper-layer business tool.

Its job in this slice is:

1. decide which real target it wants to run
2. prepare xEdit hook environment variables if needed
3. call MO2 with explicit launcher information so MO2 starts `OpenCodeVfsLauncher`
4. pass the launcher arguments needed by `mo2-vfs-launcher`
5. read the resulting state file and continue from the reported PID/session

The integration should be minimal and additive. Existing direct-launch behavior should not be broken just to introduce the MO2-aware path.

## Error Handling

The launcher should fail closed for at least the following cases:

- missing `--target-path`
- missing `--session-id`
- missing `--state-file`
- malformed `--env` values
- nonexistent target path
- invalid working directory
- process start failure
- timeout while waiting in `exit` mode
- inability to write the state file

Errors should remain compact and operationally useful. The state file should capture enough detail for callers to distinguish launch failure from target failure.

## Testing Strategy

### Repo-Level Automated Tests

Add PowerShell tests for:

- argument parsing and validation
- repeatable `--target-arg` handling
- repeatable `--env` handling
- `spawned` mode state-file creation
- `exit` mode exit-code capture
- timeout failure behavior
- `xedit-cli` minimum MO2-launcher handoff behavior

These tests should be self-contained and not require a live MO2 instance.

### Real End-To-End Verification

Real validation is required because the feature is about inherited runtime semantics, not just script execution.

Use the supplied MO2 instance and profile:

- MO2 instance root: `B:\WastelandBlues 2.0`
- profile: `CK与调试`

Verification should proceed in this order.

#### A. VFS Probe Validation

Run a probe directly from a normal shell and record that it cannot see the chosen mod-only artifact.

Then run the same probe through:

```text
ModOrganizer.exe -p "CK与调试" run -e "OpenCodeVfsLauncher" -a "..."
```

The probe should report both:

- visibility of a file that exists only through the active mod stack
- the observed `%LOCALAPPDATA%\Fallout4\plugins.txt` content or summary for the selected profile

This proves the launcher is actually executing inside MO2's semantic view rather than merely starting a script.

#### B. Real xEdit Launch Validation

Launch real FO4Edit through `mo2-vfs-launcher` without relying on the new selection hook logic.

The goal is to confirm that xEdit sees the MO2-backed plugin universe rather than only base game and DLC state.

#### C. Real xEdit Plus Hook Validation

After B succeeds, run the existing or newly wired hook/session logic through the MO2-backed launcher path and verify:

- `load all`
- `only`
- `exclude CraftingTools.esp`
- `exclude ArmorKeywords.esm` while preserving dependency-required plugins

The resulting hook/session evidence should show whether exclusions were honored or forced back on by dependency rules.

## Non-Goals

This slice does not:

- replace MO2
- recreate usvfs
- parse MO2's internal mod mapping itself
- provide a GUI
- implement complex process-tree orchestration beyond what is needed for the state contract
- move MO2 discovery into `xedit-cli`

## Delivery Target

Completion for this slice means:

1. the repo contains the reusable launcher, wrapper, probe, and docs
2. automated tests cover the launcher contract and the CLI handoff
3. real probe evidence shows a profile/VFS-only view through MO2
4. real FO4Edit launch evidence shows MO2-backed plugin visibility
5. `xedit-cli` can continue its hook/session work on top of this launcher path

This design intentionally prioritizes the smallest reusable infrastructure that proves real MO2/usvfs semantics end to end.
