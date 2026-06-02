---
id: fo4-tooling.cathedral-assets-optimizer-fo4-support.v1
title: Cathedral Assets Optimizer supports Fallout 4 asset cleanup workflows
domains: [install-planning, file-conflicts]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Cathedral Assets Optimizer advertises Fallout 4 support, so it can be part of FO4 asset conversion or cleanup, but output still needs game-specific validation.
  confidence: verified-tooling
queryKeys: [Cathedral Assets Optimizer, CAO, Fallout 4 assets, mesh texture optimization]
severity: medium
sources:
  - kind: tooling-docs
    url: "https://www.nexusmods.com/skyrimspecialedition/mods/23316"
    ref: Cathedral Assets Optimizer Nexus page
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Cathedral Assets Optimizer supports Fallout 4 asset cleanup workflows

Cathedral Assets Optimizer is published from the Skyrim SE Nexus page but lists Fallout 4 among supported games.
That makes it relevant for FO4 mesh, texture, and archive preparation.

Do not run broad optimization blindly across a live modlist.
Stage outputs in a separate mod folder and verify the game-specific archive and asset behavior before release.
