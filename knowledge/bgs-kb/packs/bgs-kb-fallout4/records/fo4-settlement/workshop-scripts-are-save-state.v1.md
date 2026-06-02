---
id: fo4-settlement.workshop-scripts-are-save-state.v1
title: Settlement workshop scripts become part of Fallout 4 save state
domains: [engine, save-file, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 settlement systems are script- and save-state-heavy, so removing or replacing workshop frameworks mid-playthrough can leave persistent state behind.
  confidence: high
queryKeys: [Fallout 4 settlement scripts, workshop save state, settlement mod removal]
severity: high
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_settlements"
    ref: Fallout Wiki Fallout 4 settlements
related: [engine.persistent-vs-temporary-references.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Settlement workshop scripts become part of Fallout 4 save state

Fallout 4 settlements track ownership, population, assignments, supply links, objects, and workshop resources across saves.
Large settlement mods often extend that system with scripts and persistent references.

Treat settlement frameworks as save-affecting infrastructure, not as simple asset swaps.
Before removing one, check the author's uninstall guidance and preserve a rollback save.
