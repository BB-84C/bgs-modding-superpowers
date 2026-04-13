# Roadmap Control Panel Design

## Goal

Redesign `docs/roadmap.md` so it becomes the main project control panel for this repository rather than a flat status note.

## Problem

The current roadmap correctly states the plugin goal and top-level workflow coverage, but it is too one-dimensional. It does not clearly show:

- the major capability tracks the plugin must eventually implement
- the ordered phase sequence for building those capabilities
- the dependency and blocker relationships between those tracks
- what is already completed in this repository based on the actual docs and scaffold

## Chosen Approach

Use a hybrid control-panel roadmap.

The roadmap should combine three views in one document:

1. `Capability view`
   What major systems the plugin needs and what state each one is in.
2. `Phase view`
   The order the project should advance through meaningful implementation phases.
3. `Dependency view`
   What must exist before other tracks can move safely.

This keeps the roadmap richer than a flat status summary without turning it into a second full design document.

## Proposed Structure

- `## Mission`
  Durable project-owned statement of what the plugin is for.
- `## Systematic Modpack Workflow`
  Re-elaborated project scope: the end-to-end BGS modpack lifecycle the plugin is meant to support.
- `## Capability Map`
  Compact table of major capabilities, current maturity, next move, and dependencies.
- `## Phase Ladder`
  Ordered implementation phases and what each phase advances.
- `## Dependency / Blocker Map`
  Key gating relationships and external unknowns.
- `## Completed Foundations`
  What has already been completed and is verifiably present in the repo.
- `## Current Focus`
  The recommended next implementation target and why it is next.
- `## Supporting Docs`
  Durable design and implementation docs for deeper context.

## Required Content

The redesigned roadmap should explicitly include:

- project scope in durable terms, not by referring back to the transient initial prompt
- the real BGS modpack workflow surface:
  environment setup, runtime/toolchain setup, discovery, evaluation, install planning, MO2 execution, file/archive reasoning, xEdit-driven conflict work, localization, testing, and modpack-facing documentation
- capability rows for the major plugin systems already discussed in the repo design
- completed foundations grounded in actual repo content under `docs/`, `skills/`, `hooks/`, `agents/`, `templates/`, `tools/`, `mcps/`, and `tests/`
- a current-focus section that recommends the next real workflow to build

## Success Criteria

After the redesign:

- `docs/roadmap.md` stands on its own as the main project navigation surface
- the roadmap is visibly multi-dimensional, not flat
- a new session can tell what the plugin is for, what exists, what comes next, and what is blocked
- the roadmap reflects actual completed work in the repo rather than aspirational statements only
- detailed mechanics remain in `docs/plans/`, not duplicated excessively into the roadmap
