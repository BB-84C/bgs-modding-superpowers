# xedit-cli MO2 Control Plane Integration Design

## Goal

Integrate `xedit-cli` with the newly completed MO2 control plane and `mo2-vfs-launcher` so real xEdit launches happen under MO2/usvfs semantics, while our `hook.dll` continues to provide xEdit-specific in-process automation.

## Problem Statement

Directly launching `FO4Edit.exe` (or other xEdit executables) is insufficient for real modpack workflows because it bypasses MO2's virtual file system. That means xEdit only sees the physical game directory and default plugin state instead of the profile-managed view used in actual modding work.

The upstream xEdit `hook.dll` seam is useful for in-process automation, but it is not a substitute for MO2/usvfs. Real plugin visibility, profile-local `plugins.txt`, and equivalent file-tree semantics come from the MO2 launch chain.

The design therefore needs to separate:

- **MO2/usvfs launch semantics**
- **xEdit process automation semantics**

## Architecture Decision

### Recommended Runtime Chain

The correct runtime chain is:

```text
xedit-cli
  -> MO2 control plane broker
    -> MO2 agent control plugin
      -> launch mo2-vfs-launcher
        -> mo2-vfs-launcher launches xEdit
          -> xEdit loads our hook.dll
            -> hook automates Module Selection and later xEdit UI behaviors
```

### Responsibilities By Layer

#### `xedit-cli`

Responsible for xEdit business semantics only:

- `load all|only|exclude`
- repeatable `--plugin`
- hook session creation
- later FormID / EditorID navigation
- later record read / diff / conflict scan

It should **not** be responsible for reimplementing MO2 VFS or usvfs mapping logic.

#### MO2 Control Plane

Responsible for agent-to-MO2 control semantics only:

- selecting the profile context
- launching a configured executable under that context
- reporting launch state / PID / stop / wait

It should **not** understand xEdit business rules.

#### `mo2-vfs-launcher`

Responsible for the generic “launch a target process inside the already-established MO2/usvfs context” behavior.

It is intentionally tool-agnostic so other future tools can reuse it.

#### `xEdit + hook.dll`

Responsible for xEdit-only in-process automation:

- Module Selection automation
- later FormID / EditorID jump
- later data extraction support

## Why This Architecture

### Why Not Direct `ModOrganizer.exe -p ... run -e FO4Edit`

That path is useful as a minimal probe, but it is not the long-term architecture because:

- it is not reusable for future tools
- it makes xedit-cli own too much MO2 launch knowledge
- it provides weaker places to inject our own session/env/control data

### Why Not Direct xEdit Launch + `hook.dll`

Because the hook seam alone does not recreate MO2/usvfs. Real plugin/profile visibility requires MO2/usvfs launch semantics, not just the presence of our DLL.

### Why Not Call usvfs Directly Ourselves

That would duplicate the most complex part of MO2's launch stack and would be much higher risk than reusing the already-completed control plane and VFS launcher.

## Interface Boundary

### xedit-cli -> Control Plane Request

The request should be a generic launch request, not an xEdit-specific control-plane API.

Suggested payload fields:

- `profile`
- `runner` = `OpenCodeVfsLauncher`
- `target_path`
- `target_args`
- `target_cwd`
- `env`
- `session_id`
- `state_file`
- `wait_mode`
- `timeout_seconds`

### xedit-cli-Specific Semantics

Remain outside the control plane and are translated into launch env/args by xedit-cli:

- `--load-mode all|only|exclude`
- repeatable `--plugin`
- xEdit hook session variables
- later `--formid`, `--editorid`, etc.

### mo2-vfs-launcher Input/Output

It should remain generic and process-oriented:

**Input**
- target path
- args
- cwd
- env
- state file

**Output**
- spawned PID
- launch state
- exit state (if waiting)
- error details

## Functional Slices

### Slice 1: xedit-cli -> control plane launch adapter

xedit-cli no longer launches xEdit directly. It emits a launch request through the MO2 control plane targeting `OpenCodeVfsLauncher`.

### Slice 2: VFS launcher passthrough for xEdit hook context

`mo2-vfs-launcher` must preserve and forward the xEdit hook env/session values into the real xEdit child process.

### Slice 3: Real `load all`

Under the project-local MO2 sandbox (`D:\awesome-bgs-mod-master\.artifacts\mo2`), real xEdit should launch under VFS and auto-confirm Module Selection.

### Slice 4: Real `only`

The same integrated chain should successfully load only the requested subset plus required masters.

### Slice 5: Real `exclude`

Run the two concrete Fallout 4 probes:

- `CraftingTools.esp` should be safely excluded
- `ArmorKeywords.esm` should be blocked by dependency when `RaiderOverhaul.esp` remains enabled

This slice resolves any remaining ambiguity between synthetic fixture behavior and real xEdit behavior.

## Test Environment

All real verification for this integration should use the project-local MO2 sandbox only:

`D:\awesome-bgs-mod-master\.artifacts\mo2`

This keeps verification reproducible and prevents accidental dependence on a developer's personal MO2/modpack state.

The currently selected profile there is:

- `Default`

If xEdit-specific plugin scenarios require a different profile later, that profile change should be explicit and recorded.

## Real End-to-End Verification Standard

This integration must not be accepted on smoke tests alone.

### Required Proof For Each Real Scenario

At minimum keep:

- control-plane launch request/response
- VFS launcher state file
- xEdit hook session/status file
- target process PID
- final selected module set
- explicit failure reason when a scenario fails

### What Must Be Proven

1. **MO2 semantics are present**
- the launched xEdit process must see the sandbox profile/plugin view, not only base game/DLC

2. **Hook semantics are present**
- the xEdit hook must write its own status and show that it automated the Module Selection flow

3. **xEdit business semantics are correct**
- `load all` passes
- `only` passes
- `exclude` is validated on the two real FO4 scenarios

### What Does Not Count As Success

- a synthetic fixture alone
- “xEdit started” without proof of profile/VFS semantics
- DLL deployed but not loaded
- `Init` called but no real hook behavior

## Deliverables

The next implementation slice should produce:

1. xedit-cli launch adapter over the MO2 control plane
2. xEdit hook env passthrough through `mo2-vfs-launcher`
3. real `load all` verification under `.artifacts\mo2`
4. real `only` verification under `.artifacts\mo2`
5. real `exclude` verification under `.artifacts\mo2`
6. updated docs showing the new runtime chain

## Recommendation

Do **not** continue to optimize direct xEdit launch as the primary path.

The correct next step is to integrate xedit-cli with the already-built MO2 control plane and `mo2-vfs-launcher`, then re-run real xEdit verification inside the project-local MO2 sandbox.
