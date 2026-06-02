---
id: engine-quirks.fnv-4gb-patcher-is-runtime-foundation.v1
title: FNV 4GB patching is a runtime foundation for modern New Vegas stacks
domains: [engine, install-planning, debugging]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Modern New Vegas guides treat 4GB patching as part of the runtime foundation, both for memory headroom and for loading xNVSE through the game executable.
  confidence: high
queryKeys: [FNV 4GB Patcher, large address aware, FalloutNV.exe patched, xNVSE autoload]
severity: critical
sources:
  - kind: community-forum
    ref: FNV 4GB Patcher Nexus page
    url: https://www.nexusmods.com/newvegas/mods/62552
    sectionPath: About this mod
  - kind: community-forum
    ref: The Best of Times Essentials
    url: https://thebestoftimes.moddinglinked.com/essentials.html
    sectionPath: Game Patcher
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# FNV 4GB patching is a runtime foundation for modern New Vegas stacks

The FNV 4GB patcher page describes making New Vegas large-address-aware.
The TTW guide also uses the patcher as the route that allows the main executable to auto-load xNVSE.

If xNVSE functions are missing or the game is memory-starved, verify patcher state before blaming plugin records.
