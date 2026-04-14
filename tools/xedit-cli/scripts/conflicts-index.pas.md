# conflicts-index.pas Contract

This document defines the Phase 1 contract for the wrapper-owned `conflicts-index.pas` script that `xedit-cli` passes to xEdit.

## Scope

The script is strictly read-only. Its job is to walk xEdit's conflict APIs, collect stable conflict-index information, and emit an intermediate report for wrapper ingestion.

## xEdit Launch Assumptions

- xEdit is launched externally by `xedit-cli`
- the wrapper provides the target game mode and load-order context
- the script runs unattended with `-script`, `-autoload`, and `-autoexit`
- the wrapper controls output and log paths

## Lifecycle Hooks

### Initialize

Validate the expected script parameters, initialize report state, and prepare any run metadata required before record traversal starts.

### Process

Visit candidate records, inspect override and conflict state through xEdit APIs, and append compact intermediate report rows.

### Finalize

Flush any buffered report rows, write final scan metadata, and return cleanly without attempting any save or mutation workflow.

## Expected Intermediate Report Fields

The intermediate report should include scan metadata, file and plugin rows, group and signature summaries, record and conflict index rows, and override chain rows needed by the SQLite-backed wrapper.

## Prohibited Behavior

The script must not call mutation-oriented APIs or behaviors such as editing fields, creating overrides, writing plugins, changing load order, or saving changes. Any mutation-capable helper is prohibited in this Phase 1 contract.
