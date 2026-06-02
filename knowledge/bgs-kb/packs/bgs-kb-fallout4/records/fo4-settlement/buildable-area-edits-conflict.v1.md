---
id: fo4-settlement.buildable-area-edits-conflict.v1
title: Settlement buildable-area edits conflict at the worldspace and workshop layers
domains: [engine, xedit, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Mods that change settlement boundaries, workshops, or nearby cells can collide even if they add different build objects, because the shared substrate is the settlement worldspace and workshop setup.
  confidence: high
queryKeys: [buildable area, settlement boundary, workshop conflict, Fallout 4 cell edit]
severity: high
sources:
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_settlements"
    ref: Fallout Wiki Fallout 4 settlements
related: [xedit.override-chain-winning-order.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Settlement buildable-area edits conflict at the worldspace and workshop layers

Settlement mods can overlap through location, cell, workshop, and placed-reference edits.
Two mods may appear unrelated in the build menu while still touching the same workshop boundary or cell data.

Use xEdit to inspect the shared records and winning overrides.
If both mods edit the same settlement substrate, load order decides only the winner; it does not merge intent.
