# xedit-cli Load-Only Session Plugins Design

## Goal

Shrink the current `xedit-cli` live-launch path back to one supported runtime semantic: `load`.

The caller or agent provides the desired plugin set for a launch, `xedit-cli` materializes that set into a session-scoped `plugins.txt`, xEdit consumes it through its native `-P:` command-line seam, and the hook bridge only auto-confirms the `Module Selection` dialog and records diagnostics.

This design is scoped to the active worktree:

- `D:\awesome-bgs-mod-master\.worktrees\xedit-step1-hooks`

It continues to use the shared project assets under the repository root for real verification:

- `D:\awesome-bgs-mod-master\.artifacts\mo2`
- `D:\awesome-bgs-mod-master\.artifacts\TES5Edit-source` only as a source reference, not as the primary implementation target for this slice

## Problem Statement

The current worktree contains two diverging ideas:

1. A no-fork hook path that is already good enough to automate `load all`
2. A later model-layer experiment proving that `only` and `exclude` semantics are expressible in xEdit's internals, but only through an xEdit-side patch

The user boundary has now changed:

- patching and redistributing a custom xEdit executable is not acceptable for this repository's deliverable
- the acceptable boundary is a no-fork integration only
- the hook is allowed to remain only if it stays narrow and low-risk

At the same time, the desired plugin subset can still vary per launch. The wrapper therefore needs a way to override the active plugin list without touching the real MO2 profile `plugins.txt` and without relying on xEdit model-layer patches.

## Source-Grounded Insight

xEdit already exposes a native seam for an alternate `plugins.txt` path.

In `xEdit\xeInit.pas`, xEdit assigns `wbPluginsFileName` from command-line switch `-P:` before falling back to the default `%LOCALAPPDATA%\...\Plugins.txt` location.

In `Core\wbLoadOrder.pas`, xEdit later loads `wbPluginsFileName` and marks modules active in `plugins.txt` via `mfActiveInPluginsTxt` / `mfActive`.

In `xEdit\xeModuleSelectForm.pas`, the `<plugins.txt>` preset seeds selection from `mfActiveInPluginsTxt` and then calls `SimulateLoad`.

That means a session-specific `plugins.txt` is already a first-class xEdit input. The wrapper does not need to patch xEdit in order to vary the requested load set.

## Design Decision

Replace the current `all` / `only` / `exclude` command semantics with a single launch semantic: `load`.

The caller decides what should be loaded by providing or implying a plugin set. The wrapper writes that plugin set into a session-scoped `plugins.txt`, launches xEdit with `-P:<session plugins.txt>`, and relies on xEdit's native load-order behavior plus the existing hook bridge's auto-confirm behavior.

The hook bridge will no longer own or simulate subset semantics. It becomes a narrow automation/diagnostic component again.

## Runtime Model

### Single semantic: `load`

The launch request no longer means:

- `all`
- `only`
- `exclude`

It only means:

- `load the plugin set described by this launch's session plugins file`

### Session-scoped plugin file

For every launch, `xedit-cli` creates a unique session directory and writes one canonical file:

- `plugins.txt`

xEdit always receives that session file path through `-P:`.

The real MO2 profile `plugins.txt` is never touched, even transiently.

### Session directory layout

Recommended layout:

```text
<agent-root>\sessions\<session-id>\
  plugins.txt
  launch-request.json
  launch-response.json
  mo2-launch-state.json
  hook-status.txt
```

The session directory is the only location where launch-specific mutable files should be written.

## Interface Shape

The command surface should move away from `--load-mode` and `--plugin` as runtime semantics.

The wrapper should instead resolve a plugin set input source and always synthesize the session copy that xEdit consumes.

Recommended shape:

```text
xedit-cli process launch \
  --launcher-path <path> \
  --game-mode <mode> \
  --mo-profile <name> \
  [--plugins-file <path>]
```

Wrapper behavior:

- if `--plugins-file` is provided, read and normalize it
- if omitted, derive the plugin set from the current MO2-backed active profile view
- in both cases, write the canonical session `plugins.txt`
- always pass `-P:<session plugins.txt>` to xEdit

This guarantees one stable runtime seam regardless of the original input source.

## Hook Scope After Shrink

The hook bridge should retain only these responsibilities:

- detect the `Module Selection` dialog
- auto-confirm the current selection without manual clicks
- report launch/session diagnostics
- optionally record the final selected modules that xEdit proceeded with

The hook bridge should stop owning or advertising:

- `only`
- `exclude`
- model-layer selection policy
- `selection_method=model-layer`
- `forced_dependencies`
- `blocked_exclusions`

Those fields belonged to the abandoned patch-oriented subset path and should not remain as part of the no-fork contract.

## Error Handling

The wrapper should fail closed before launch if any of these checks fail:

- session directory cannot be created
- session `plugins.txt` cannot be written
- plugin file is empty
- entries cannot be normalized
- `-P:` path cannot be formed as an absolute path

Session `plugins.txt` should be written atomically:

- write temporary file in session directory
- rename into final `plugins.txt`

At runtime, success should require all of the following:

1. xEdit launched successfully
2. the hook detected `Module Selection`
3. the hook confirmed the dialog without user action
4. hook/session artifacts were written

If any step is missing, the wrapper should fail and preserve the full session directory for diagnosis.

## Verification Model

The main real verification path should prove:

1. wrapper wrote the session `plugins.txt`
2. xEdit was launched with `-P:<session plugins.txt>`
3. the hook auto-confirmed `Module Selection`
4. the final selected modules match the selection xEdit actually proceeded with

Different plugin-set scenarios may still be tested, but they should be treated as different `load` inputs rather than separate `all` / `only` / `exclude` product features.

## Target File Boundaries

### Active implementation targets in the worktree

- `tools\xedit-cli\lib\common.ps1`
- `tools\xedit-cli\lib\hook-session.ps1`
- `tools\xedit-cli\lib\process.ps1`
- `tools\xedit-cli\lib\mo2-launch.ps1`
- `tools\xedit-hook-bridge\src\HookMain.pas`
- `tools\xedit-hook-bridge\src\HookStatus.pas`
- `tools\xedit-cli\README.md`
- `tools\xedit-cli\CONTRACT.md`
- `tools\xedit-cli\live-integration.md`
- affected tests under `tests\xedit-cli\`

### Shared verification assets, not primary edit targets

- `D:\awesome-bgs-mod-master\.artifacts\mo2`
- `D:\awesome-bgs-mod-master\.artifacts\TES5Edit-source`

### Explicit non-target for this slice

- `D:\TES5Edit-contrib`

That clean xEdit fork is for future upstream contribution work and should not be mixed into this repository slice.

## Advantages

- no xEdit patch required
- no need to modify the real MO2 profile `plugins.txt`
- no need to preserve the fragile `all` / `only` / `exclude` hook semantics
- leverages xEdit's native `-P:` seam
- keeps the hook narrow and diagnosable
- preserves flexibility for agents because any desired plugin set can be materialized in the session file

## Trade-Offs

- the no-fork hook remains vulnerable to major UI/startup changes in xEdit
- this does not expose deep internal xEdit automation APIs
- the wrapper still depends on MO2/VFS for the actual available plugin universe; a session `plugins.txt` can only activate what exists in the chosen MO2-backed environment

## Explicit Non-Goals

- patching xEdit to preserve internal model-layer subset semantics in this repository
- redistributing a custom xEdit executable from this repository
- keeping `all` / `only` / `exclude` as first-class product concepts in the current worktree
- touching the real profile `plugins.txt` even temporarily

## Recommendation

Implement the load-only shrink in the active worktree.

Use session-scoped `plugins.txt` plus xEdit native `-P:` as the sole semantic seam for varying what gets loaded. Keep the hook only as an auto-confirm and diagnostic component.
