# Plugin Roadmap

This document is the lightweight status board for the plugin itself. It summarizes durable direction and current status without repeating the design docs.

## Goal

- Build an OpenCode plugin for BGS modpack curation across Skyrim, Fallout 4, and Starfield.
- Keep the project centered on curator workflows and decision support, not general mod authoring.

## Workflow Coverage

- Cover the top-level curation loop: environment setup, runtime/toolchain setup, mod discovery, evaluation, install planning, MO2 execution, conflict review, xEdit-driven data inspection, localization, testing, and modpack-facing documentation.
- Keep file/archive reasoning, plugin/data conflict analysis, and release-quality logging in scope as the workflow matures.

## Current Baseline

- The repository is still in bootstrap phase.
- Today it provides repository standards, verification scripts, workflow skeleton content, and integration placeholder specs rather than working end-user automation.
- The baseline is useful for repo structure and guardrails, but the actual curation workflows still need implementation.

## Next Major Tracks

- Turn the scaffolded skills, hooks, agents, templates, and tooling specs into usable curator workflows.
- Start the first practical tooling track around read-only xEdit orchestration and structured conflict inspection.
- Define the first shipped documentation flows for modpack dev logs and player-facing changelogs.

## Deferred / Blocked

- Defer save-safety and other higher-risk policy automation until the core curator loop is implemented and tested.
- Block install metadata and packaging work until the OpenCode plugin format is verified.
- Keep heavier integrations and write-capable patching work later than the current bootstrap baseline.

## Supporting Docs

- See `docs/plans/` for the approved design and implementation plans behind this roadmap.
- See `docs/standards/repo-hygiene.md` for repository cleanliness and artifact-handling rules.
