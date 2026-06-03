---
id: tooling-mo2.stock-game-data-read-only.v1
title: The MO2 Stock Game Data tree is read-only; use mod overlays for game-local changes
domains: [install-planning, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Game-local changes must be expressed as MO2 mod overlays or overwrite outputs, not by writing directly into the Stock Game Data tree.
  confidence: verified-project-doc
queryKeys: [Stock Game Data, MO2 overlay, mods folder, overwrite, game tree protection]
severity: critical
sources:
  - kind: project-internal-doc
    ref: .opencode/memory/70-stock-game-protection.md
    sectionPath: Rules
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# The MO2 Stock Game Data tree is read-only; use mod overlays for game-local changes

The Stock Game tree is treated as real game state, not scratch space.
Even test fixtures should not be copied directly into its Data directory.

If a change must appear in the game Data view, package it as an MO2 mod overlay under `mods/<name>/Data/...` or use overwrite for generated runtime spill.
The only narrow exception in this repo is syncing the xEdit executable into its existing tool directory.

This is a hard safety invariant, not a preference.
