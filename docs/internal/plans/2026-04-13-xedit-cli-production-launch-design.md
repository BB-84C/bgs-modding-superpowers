# xedit-cli Production Launch Design

## Goal

Make `xedit-cli` production-ready enough to launch xEdit itself from a caller-provided launcher path, report the real Windows PID, and manage multiple concurrent xEdit processes without requiring the user to manually start xEdit or hand the CLI a PID up front.

## Scope Boundary

`xedit-cli` is responsible for taking launch arguments, starting xEdit, validating launch prerequisites, reporting the launched PID, and managing later lifecycle operations by raw PID.

`xedit-cli` is not responsible for discovering Mod Organizer 2 state in this slice. A separate MO2-aware tool or agent should resolve the correct xEdit launcher path and pass it into the CLI.

## Product Position

Production readiness here means:

- the caller gives `xedit-cli` a launcher path such as `B:\WastelandBlues 2.0\Stock Game\Fallout 4\Tools\FO4Edit\runFO4EditCN.bat`
- `xedit-cli` launches the process itself
- `xedit-cli` returns the real Windows PID and enough metadata for later lifecycle commands
- the CLI can manage multiple concurrent xEdit processes by raw PID

It does not mean the CLI can inject arbitrary new work into an already-running xEdit process. xEdit's stable automation surface is launch-time command-line plus Pascal scripts, so deterministic scripted work should still use wrapper-controlled launches.

## Command Model

### `xedit-cli doctor env`

Expand `doctor env` so it validates a real launcher path instead of just an executable path.

Recommended inputs:

- `--launcher-path <path>`
- `--game-mode <mode>`
- optional `--xedit-pid <pid>`

Behavior:

- validate that the launcher path exists
- identify whether the launcher is a batch file or executable
- report a compact preflight summary
- when `--xedit-pid` is provided, validate that the PID exists and matches xEdit-related process expectations

### `xedit-cli process launch`

Launch xEdit from a caller-provided launcher path and return a compact summary including:

- launcher path
- launched PID
- resolved process image when detectable
- optional game mode hint

This command is the main production entry point for starting xEdit without manual user launching.

### `xedit-cli process status`

Accept `--xedit-pid <pid>` and return whether the process is still alive, plus compact process metadata such as process name, executable path, and command line when available.

### `xedit-cli process wait`

Accept `--xedit-pid <pid>` and wait for completion with timeout support.

This provides a clean way to monitor long-running scripts without manually polling the operating system.

### `xedit-cli process stop`

Accept `--xedit-pid <pid>` and terminate the chosen xEdit process deliberately.

Phase 1 should keep this explicit and conservative, with clear output identifying which PID was stopped.

### `xedit-cli conflicts index`

Keep fixture-backed mode for tests, but add a live launcher-driven path that takes a launcher path and performs a wrapper-controlled xEdit run for deterministic report generation.

That path should:

1. create run-scoped artifact paths
2. launch xEdit through the provided launcher path with wrapper-controlled script/report/log settings
3. capture the launched PID
4. wait for completion
5. ingest the generated report into SQLite
6. return the same compact summary shape as the fixture-backed path, plus the PID used for the run

## Multiple PID Model

Raw PIDs are the addressing model.

The CLI should not invent separate session IDs in this slice. Instead:

- launch commands return the real PID
- lifecycle commands accept raw PIDs directly
- task-oriented commands that launch their own xEdit process should also report the PID they used

This keeps the integration surface simple for agents that already reason about process IDs.

## Launch Strategy

The CLI should support both `.bat` launchers and direct `.exe` paths.

Recommended handling:

- `.bat` or `.cmd`: launch through `cmd.exe /c <launcher>`
- `.exe`: launch directly

The wrapper should capture the actual child process metadata after launch. If the launcher spawns a child xEdit process and exits, the CLI should surface the PID of the xEdit process rather than only the transient shell when that relationship can be detected reliably.

## Error Handling

Fail closed for:

- missing launcher path
- unsupported launcher extension
- launch failure or no process created
- PID mismatch when `--xedit-pid` is supplied to validation commands
- timeout while waiting for a process to complete
- missing or malformed live report after a controlled index run

All errors should stay compact and operationally useful.

## Testing Strategy

### Unit-level PowerShell tests

- `doctor env` with real launcher-path semantics
- `process launch/status/wait/stop` with a safe test launcher
- `conflicts index` live-path validation and failure handling

### Real-environment verification

Use the provided Fallout 4 launcher path to verify:

- the CLI can start xEdit without manual launch
- the CLI reports a real PID
- status and wait commands can observe that PID

Real verification should avoid destructive actions and keep the workflow read-only.

## Non-Goals

- MO2 config discovery inside `xedit-cli`
- generic attach-and-inject work submission into arbitrary already-running xEdit processes
- write-capable patch generation
- replacing the fixture-backed test path entirely
