# Live xEdit Integration

This document describes how a later Phase 1 task should add a controlled live xEdit invocation alongside the current fixture-backed flow.

## Phase 1 Launch Arguments

The wrapper should launch xEdit explicitly rather than relying on a manually opened session.

The caller-provided launcher path is the production entry point for this later Phase 1 task, and MO2 discovery stays outside the CLI.

Launcher-driven live commands require authoritative `--game-mode` as the primary trust and control signal for mode selection, not executable-name-derived guessing. Direct `.exe` launchers and simple `.bat`/`.cmd` wrappers should be normalized to explicit launch commands with mapped xEdit mode arguments using `Fallout4 -> -FO4`, `Skyrim -> -TES5`, `SkyrimSE -> -SSE`, and `Starfield -> -SF1`, including `SkyrimSE` to `-SSE`, while complex wrappers fail closed.

Recommended Phase 1 arguments:

- `-script:<script-name>` to run the wrapper-owned Pascal report script
- `-autoload` to load the chosen environment without interactive steps
- `-autoexit` to close the xEdit process when the script finishes
- `-R:<log-path>` to capture a run-scoped session log
- `-S:<script-path>` when the wrapper needs to override the script search location
- deterministic path overrides such as `-D:` and `-P:` when the environment must be pinned

## Report-Script Execution Flow

1. Run `xedit-cli doctor env` as explicit-mode-launch preflight for the caller-provided launcher path and authoritative `--game-mode`.
2. Materialize or select the wrapper-owned read-only report script.
3. Create run-scoped output paths for the intermediate report and xEdit log.
4. Launch xEdit with the Phase 1 argument set and capture the raw PID used for that run.
5. Wait for the launched process to exit before deciding whether the run succeeded.
6. Check the log and intermediate report before ingesting the run into SQLite.
7. Serve later `conflicts index` and `conflicts inspect` results from the ingested artifact set.

The first live `conflicts index` launch path requires both `--launcher-path` and authoritative `--game-mode`, uses the same explicit mapping `Fallout4 -> -FO4`, `Skyrim -> -TES5`, `SkyrimSE -> -SSE`, and `Starfield -> -SF1`, including `SkyrimSE` to `-SSE`, creates deterministic run-scoped artifact paths before launch, reports the PID it launched, and fails closed when the launched process exits non-zero or the expected report file never appears.

## Log Capture And Timeout Handling

Every live run should capture a log through `-R:` and preserve the raw intermediate report beside the SQLite artifact.

When the live launch path ships, operational summaries should expose raw PID outputs so callers can use the same addressing model across launch, status, wait, and stop commands.

The wrapper should enforce a timeout so hung GUI-first automation does not stall unattended workflows forever. A timeout should terminate the launched process, mark the run as incomplete, and surface the log path in the error output for diagnosis.

## Read-Only Constraints

Phase 1 remains read-only even when live xEdit invocation is enabled.

The wrapper should only launch report scripts that inspect conflicts, override chains, and related metadata. It should not trigger save prompts, write plugins, mutate fields, or attach any patch-generation workflow.

## Known Unknowns

- xEdit success signaling may depend on both process exit behavior and log/report evidence
- some environments may need stricter path overrides than a simple executable launch
- a manually opened xEdit session may already exist, but the wrapper should not assume that process is safe to reuse for read-only automation
- timeout thresholds may vary by game and load-order size

## Fallback Behavior

If live launch preflight fails, the wrapper should stop before opening xEdit and return a compact error.

If the live run starts but the report is missing or incomplete, fallback behavior should preserve the log, preserve any partial artifacts, and return a clear failure summary instead of pretending the scan succeeded.

Until live invocation is proven reliable, the fixture-backed flow remains the fallback contract for local development and test coverage.
