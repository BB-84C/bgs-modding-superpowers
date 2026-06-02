---
id: legacy-load-order.loot-supports-fo3-fnv-sorting.v1
title: LOOT supports Fallout 3 and Fallout New Vegas sorting
domains: [load-order, tooling.loot]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: LOOT lists both Fallout 3 and Fallout New Vegas among its supported games and can provide sorting, warnings, and metadata-driven messages for those targets.
  confidence: verified-tooling
queryKeys: [LOOT Fallout 3, LOOT New Vegas, sorter, metadata, masterlist]
severity: medium
sources:
  - kind: tooling-docs
    ref: LOOT supported games
    url: https://loot.github.io/
    sectionPath: Supported games list
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# LOOT supports Fallout 3 and Fallout New Vegas sorting

LOOT's supported-game list includes Fallout 3 and Fallout: New Vegas.
It can be used as a sorting and metadata warning source for these legacy Gamebryo targets.

Treat LOOT output as a planning aid rather than final proof.
For TTW or heavily patched FNV stacks, confirm the intended plugin order through MO2 and xEdit readback.
