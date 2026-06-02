---
id: skyrim-quirks.cao-do-not-process-live-data.v1
title: Run Cathedral Assets Optimizer on mod copies, not the live Skyrim Data folder
domains: [archive-precedence, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Cathedral Assets Optimizer documents that BSA processing is not supported directly against the game's Data folder; use mod copies or MO2-managed folders instead."
  confidence: high
queryKeys: [Cathedral Assets Optimizer, CAO, Data folder, BSA processing]
severity: critical
sources:
  - kind: community-forum
    ref: Nexus Mods Cathedral Assets Optimizer
    url: https://www.nexusmods.com/skyrimspecialedition/mods/23316
    sectionPath: BSA / BA2 handling
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Run Cathedral Assets Optimizer on mod copies, not the live Skyrim Data folder

CAO is useful for conversion, but it is still a mutating asset tool.
The Nexus page notes BSA processing is not supported when working directly with the game's Data folder.

Use a copy, a staging folder, or an MO2 mod directory.
Keep backups until meshes, textures, animations, and archives are verified in-game.

This follows the repo-wide rule: game Data is not a scratch workspace.
