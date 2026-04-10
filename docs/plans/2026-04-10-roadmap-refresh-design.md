# Roadmap Refresh Design

## Goal

Refresh `docs/roadmap.md` so it becomes a durable project-level navigation document for the plugin itself, rather than a thin placeholder or a pointer back to the original conversation.

## Problem

The current roadmap correctly records that bootstrap exists, but it still under-explains the actual product goal and the capability surface the plugin is meant to cover. The original prompt was only a transient conversation artifact. The roadmap must absorb the durable meaning of that prompt in its own words.

## Chosen Approach

Use `docs/roadmap.md` as a light but authoritative project charter and status board.

The roadmap should do three jobs:

1. Restate the plugin's durable goal in project-owned language.
2. Re-elaborate the major modpack-curation workflow coverage the plugin must eventually support.
3. Show what is already real in the repo, what comes next, and what is intentionally deferred or externally blocked.

## Roadmap Structure

The refreshed roadmap should contain these sections:

- `## Goal`
  Restate that this project is building an OpenCode plugin for professional BGS modpack curation across Skyrim, Fallout 4, and Starfield.
- `## Workflow Coverage`
  Re-elaborate the end-to-end modpack workflow the plugin is supposed to support:
  environment setup, mod discovery, evaluation, installation planning, install execution, file/archive conflict analysis, plugin/data conflict analysis with xEdit, localization, in-game testing, and strategic modpack logging.
- `## Current Baseline`
  State what is real today after bootstrap.
- `## Next Major Tracks`
  Name the next implementation tracks at a high level.
- `## Deferred / Blocked`
  Record intentionally later or externally gated work.
- `## Supporting Docs`
  Point to the detailed design and bootstrap plan.

## Key Constraint

The roadmap must not simply say "see `docs/initial_pormpt.md`". That file can remain as preserved context, but the roadmap itself must stand on its own.

## Success Criteria

After the refresh:

- a new session can understand the project goal from `docs/roadmap.md` alone
- the roadmap clearly states what the plugin needs to cover at the top level
- the roadmap accurately distinguishes current baseline, next work, and deferred work
- detailed design remains in the plan documents, not duplicated into the roadmap
