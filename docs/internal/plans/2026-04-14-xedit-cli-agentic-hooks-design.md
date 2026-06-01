# xedit-cli Agentic Hooks Design

## Goal

Add a no-fork hook layer for xEdit so `xedit-cli` can close the startup automation loop, then build record-level reads and later conflict scanning on top of that control path.

## Problem Statement

Launching xEdit is not sufficient for agentic automation because every session begins at the `Module Selection` interface. If the agent cannot get past that screen reliably, there is no real closed-loop xEdit automation.

After startup control is solved, the next milestone is record-level reading by FormID or EditorID, including a CLI-native override diff that mirrors the meaning of xEdit's side-by-side compare view without depending on GUI output.

## Constraints

- Hooks are mandatory for step 1.
- No xEdit fork is allowed for this slice.
- MO2 remains the source of truth for the full plugin list and order.
- The CLI may still request `load all`, `load only`, or `load excluding` behaviors against that MO2-backed set.
- Step 1, step 2, and step 3 are sequential, not a one-shot implementation.

## Repo Findings

### Startup And Module Selection

The xEdit repo exposes the startup dialog as `TfrmModuleSelect` in `xEdit/xeModuleSelectForm.pas` and `xEdit/xeModuleSelectForm.dfm`.

Important internal controls and behavior:

- `vstModules: TVirtualStringTree` holds the module tree
- `edFilter` handles filtering
- `cbPreset` and preset actions support saved selections, including `<plugins.txt>`
- `btnOK` confirms selection
- `SimulateLoad` resolves master implications and final enabled state

This means module selection is a real Delphi/VCL form with a custom tree control, not a plain Win32 list box.

### Existing Automation Surfaces

The repo does contain a few no-fork seams:

- command-line switches in `xEdit/xeInit.pas`
- startup script execution via `-script`
- `GameLink` / `PluggyLink` style record-sync paths in `xeMainForm.pas`
- the Mod Organizer hook load path triggered by `-moprofile`

The most important no-fork seam for step 1 is the existing MO hook path. The repo shows that when `-moprofile` is used, xEdit loads `..\Mod Organizer\hook.dll` and calls its exported `Init(...)` entry point.

### What Does Not Exist

The repo does not provide a general external automation API such as:

- COM automation
- REST or sockets
- named-pipe control server
- a general external message protocol for arbitrary commands

That means there is no stock “remote control” API to call from the CLI.

### Navigation And Record Control

The main form source (`xEdit/xeMainForm.pas`) already contains usable internal seams for later phases:

- FormID search control and handlers
- EditorID search control and handlers
- `JumpTo(...)`
- active-record and view-refresh logic
- Referenced By population
- `GameLink`-based record activation flows

This makes step 2 materially more feasible once startup control exists.

## Recommended Architecture

### Step 1 Core Mechanism

Use the existing MO hook load seam as the primary no-fork control point.

The architecture is:

1. `xedit-cli` remains the external orchestrator.
2. A new native `xedit-hook-bridge.dll` is loaded by xEdit through the MO hook path.
3. That DLL waits for `TfrmModuleSelect` and controls the startup selection flow from inside the process.

This is the strongest source-grounded path for step 1 without forking xEdit.

### Why Not Pure UI Macros

Out-of-process UI automation remains a fallback option, but it is not the preferred architecture because the module tree is a custom `TVirtualStringTree`. Plain accessibility or coordinate-driven input would be much more brittle than in-process VCL-aware control.

### Why Not Scripts For Step 1

Scripts are still useful, but they start too late to solve the module-selection blocker cleanly. They should be treated as a later in-process adapter for record reading and data extraction, not the primary step-1 mechanism.

## Step 1 Command Contract

MO2 provides the full ordered plugin universe.

The hook does not rebuild that list. Instead, the CLI sends a selection policy against the MO2-backed set.

### Supported Policies

- `--load-mode all`
- `--load-mode only`
- `--load-mode exclude`

### Plugin List Contract

For `only` and `exclude`, use repeatable plugin filename arguments:

```text
--plugin Fallout4.esm --plugin MyPatch.esp --plugin Another.esl
```

This is preferred over comma-separated blobs because it avoids escaping problems and is easy for agents to generate.

### Semantics

- `all`
  - accept the MO2-provided active set as-is
- `only`
  - treat listed plugins as requested roots
  - preserve MO2 order among those roots
  - let xEdit master-resolution keep required masters loaded
- `exclude`
  - start from the MO2-provided active set
  - uncheck the listed plugins
  - if xEdit re-selects a plugin because of dependency rules, report that explicitly

### Validation Rules

- plugin names are case-insensitive exact filename matches
- unknown plugin names fail closed
- duplicate plugin args are deduplicated
- `all` forbids any `--plugin`
- `only` and `exclude` require at least one `--plugin`

## Step 1 Hook Data Flow

The CLI does not need to send a full plugin list.

Instead, it provides only the subset-selection policy.

Recommended first transport:

- environment variables for action, mode, and plugin names

Example shape:

```text
XEDIT_HOOK_ACTION=module-select
XEDIT_HOOK_POLICY=only
XEDIT_HOOK_PLUGINS=Foo.esm;Bar.esp;Baz.esl
```

This keeps step 1 simple while respecting that MO2 already owns the full list and order.

## Failure Model

### Fail Closed Conditions

- hook DLL did not load
- `TfrmModuleSelect` did not appear within timeout
- requested plugin names do not exist in the MO2-backed module tree
- invalid policy combination (`all` plus plugin args, or missing plugin args for `only`/`exclude`)
- final selected set does not match the requested policy after xEdit resolves dependencies

### Important Non-Failure State

If `exclude` tries to drop a plugin that xEdit immediately re-selects because it is still a required master, the run should not pretend the exclusion succeeded. The hook should report that as a forced dependency outcome.

### Evidence To Return

The hook and CLI should return:

- whether the hook loaded
- whether module selection was automated successfully
- requested mode and plugin names
- final selected plugin set
- forced masters or blocked exclusions
- timeout or UI-state failure reason

## Staged Roadmap

### Step 1A

Prove the no-fork hook seam works.

- load the DLL through the MO hook path
- establish handshake between `xedit-cli` and the hook

### Step 1B

Automate the simplest startup path.

- detect `TfrmModuleSelect`
- auto-confirm `--load-mode all`
- report success/failure reliably

### Step 1C

Add subset policies.

- implement `only` and `exclude`
- preserve MO2 order
- report forced masters and blocked exclusions

### Step 1D

Run targeted real-xEdit verification for `exclude` once the synthetic harness stops giving clear answers.

- start with Fallout 4 only
- test one plugin that should be safely excluded, currently `CraftingTools.esp`
- test one plugin that should be forced back on by dependency rules, currently `ArmorKeywords.esm` while `RaiderOverhaul.esp` remains enabled
- capture hook status, startup automation result, and final selected modules
- use that evidence to decide whether any remaining `exclude` bug lives in the hook logic or only in the synthetic fixture

### Step 2

Build the first elementary record-read flow.

- read a given FormID or EditorID
- read all plugins overriding that record
- persist the result in the CLI DB
- render a text diff view analogous to xEdit's compare columns
- if the hook permits it, command xEdit to jump to the target record

### Step 3

Only after step 2 is solid, build broader conflict scanning on top of that record-level read and override-diff foundation.

## Non-Goals For This Slice

- forking xEdit
- replacing MO2 as the source of truth for load order
- full live conflict scanning immediately
- write-capable patch generation

## Recommendation

Start with a very narrow first implementation:

1. prove the hook loads
2. auto-confirm MO2-backed `load all`
3. then add `only` / `exclude`

That closes the biggest automation blocker without pretending we already have full record navigation or conflict extraction solved.
