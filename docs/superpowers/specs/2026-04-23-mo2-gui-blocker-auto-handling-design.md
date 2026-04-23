# MO2 GUI Blocker Auto-Handling Design

**Date:** 2026-04-23

## Summary

Eliminate the two known Mod Organizer 2 GUI blockers that currently interrupt agent, CLI, and manual workflows:

1. `Mod Organizer is locked while the application is running.`
2. `Mod Organizer is waiting on an application to close before exiting.`

The selected design is an MO2-internal solution. We will remove the lock blocker at the settings layer where possible, then add a narrowly whitelisted dialog watcher inside the existing `mo2_agent_control.py` plugin to automatically consume only these two known dialogs and record each handling event to a runtime artifact log.

## Problem Statement

Today, MO2-backed launches can block automation in two ways:

- Raw `ModOrganizer.exe -p <profile> run ...` invocations can hang because MO2 attempts to exit while a launched child is still running, then shows the "waiting on an application to close before exiting" confirmation dialog.
- When MO2 remains open while a child process is running, the UI can enter a locked state and show the "Mod Organizer is locked while the application is running" dialog.

These blockers defeat bash-driven automation, interfere with agent workflows, and create the same interruption for manual use.

## Goals

- Remove the two known blockers as operational interruptions for agent, CLI, and manual workflows.
- Keep the solution inside MO2 and the existing `Mo2AgentControl` plugin instead of relying on external desktop clicking or screen automation.
- Ensure raw `ModOrganizer.exe ... run ...` flows and our `control-plane/OpenCodeVfsLauncher` flows both benefit.
- Emit machine-readable evidence when a blocker is auto-handled.
- Fail closed for unknown dialogs.

## Non-Goals

- Do not build a general-purpose "click any dialog" system.
- Do not auto-dismiss unknown MO2 error dialogs, destructive confirmations, or profile-management prompts.
- Do not move blocker handling into xEdit hook code, shell wrappers, or external watchdogs.
- Do not change launch protocol semantics beyond eliminating these blockers.

## Selected Approach

### Layer 1: MO2 global settings policy

The lock blocker should be prevented at the root by normalizing the live sandbox MO2 settings to disable GUI locking. The relevant sandbox configuration lives at `.artifacts/mo2/ModOrganizer.ini` in the local MO2 sandbox and historically included `lock_gui=true`. The live bridge deployment flow now normalizes that setting to `lock_gui=false` so the sandbox does not drift back into the blocker-producing state.

### Layer 2: MO2 plugin whitelist watcher

The existing `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` plugin already owns MO2-local automation concerns such as runtime bootstrap publication, the named-pipe transport, and main-thread marshalling for organizer-backed launches. It is the correct place to add a Qt-level dialog watcher that:

- enumerates top-level Qt dialog candidates from inside MO2,
- matches only the two approved blocker dialogs,
- clicks the exact whitelisted button (`Unlock` or `Exit Now`), and
- writes a runtime event record describing what happened.

No external desktop automation, OCR, or coordinate clicking is part of this design.

## Approved Runtime Behavior

### Global behavior

- Agent-driven launches, control-plane launches, `OpenCodeVfsLauncher`, and raw `ModOrganizer.exe ... run ...` launches all inherit the same blocker policy.
- Manual GUI use also inherits the same behavior.
- Only the two known blockers are auto-consumed.

### Lock blocker

When MO2 presents a dialog whose content matches:

- dialog text includes `Mod Organizer is locked while the application is running`, and
- a button labeled `Unlock` exists,

the plugin should immediately trigger the equivalent of `Unlock` and log a `handled` blocker event.

### Exit-wait blocker

When MO2 presents a dialog whose content matches:

- dialog text includes `Mod Organizer is waiting on an application to close before exiting`, and
- buttons labeled `Exit Now` and `Cancel` exist,

the plugin should immediately trigger the equivalent of `Exit Now` and log a `handled` blocker event.

## Safety Rules

The watcher is a strict whitelist.

It must match dialogs using a combination of:

- MO2/ModOrganizer title or host identity,
- known body text substrings, and
- the expected button set.

If a dialog does not match the whitelist exactly enough to identify it safely:

- it must not be auto-clicked,
- it should be recorded as `ignored` or `unrecognized`, and
- MO2 should continue to display it normally.

The watcher must not retry indefinitely. Repeated failures to handle the same dialog should be logged and then left alone instead of entering a click loop.

## Runtime Artifacts

Add a JSON-lines blocker log under the existing plugin runtime directory:

- `.artifacts/mo2/plugins/Mo2AgentControl/bootstrap/runtime/blocker-events.jsonl`

Each event record should capture enough evidence for later diagnosis, including:

- timestamp,
- blocker type (`unlock`, `exit-now`, `ignored`, `failed`),
- dialog title and matched button labels,
- target process name/PID when available from dialog text,
- result (`handled`, `ignored`, `failed`), and
- source (`global-dialog-watcher`).

The blocker log is diagnostic evidence. It is not part of the xEdit hook status contract.

## Affected Files

Primary implementation surfaces:

- `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- `tools/mo2-control-plane/live-bridge/deploy-live-bridge.ps1`
- `.artifacts/mo2/ModOrganizer.ini`

Primary verification surfaces:

- `tests/mo2-control-plane/*.ps1`
- `tools/mo2-control-plane/live-bridge/README.md`
- `tools/mo2-control-plane/live-integration.md`

## Verification Strategy

Verification must prove two things:

1. The known blockers no longer interrupt agent/bash/manual workflows.
2. Unknown dialogs are not auto-consumed.

Planned verification layers:

- unit-style PowerShell/Python harness tests for whitelist matching and dialog handling,
- deployment/settings tests proving `lock_gui=false` is enforced,
- real sandbox regression coverage for raw `ModOrganizer.exe ... run ...` launches not hanging behind the exit blocker,
- runtime log assertions proving blocker handling was recorded, and
- negative tests proving non-whitelisted dialogs remain untouched.

## Rejected Alternatives

### External desktop watchdog

Rejected because it is fragile, depends on focus and windowing state, and violates the requirement to solve the problem inside MO2.

### General auto-dismiss behavior

Rejected because it is unsafe. We only want to eliminate the two known blockers, not suppress arbitrary confirmations or errors.

### Bash-side blocker handling

Rejected because bash only sees the problem after the GUI blocker already exists. The reliable seam is the MO2 process itself.

## Final Design Decision

Implement a two-layer MO2-internal solution:

1. normalize the sandbox settings so `lock_gui` is disabled globally, and
2. add a strict whitelist dialog watcher inside `mo2_agent_control.py` that auto-handles only the two known blockers and logs every action.

This satisfies the approved behavior: global blocker removal, MO2-internal handling, explicit evidence, and safe failure for unknown dialogs.
