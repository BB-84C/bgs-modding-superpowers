---
id: xedit.override-chain-winning-order.v1
title: Override chains resolve by load-order priority, with the winner last
domains: [xedit, plugin-format]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: In an override chain, earlier files provide the base and prior overrides, while the highest-priority loaded override is the winning record the game uses.
  confidence: verified-tooling
queryKeys: [override chain, winning override, load order priority, records.winning_override]
severity: high
sources:
  - kind: tooling-docs
    ref: Mutagen Docs — Winning Override Iteration
    url: https://mutagen-modding.github.io/Mutagen/loadorder/Winning-Overrides/
    sectionPath: Winning Overrides
  - kind: tooling-docs
    ref: xEdit Docs / Tome of xEdit
    url: https://tes5edit.github.io/docs/5-conflict-detection-and-resolution.html
    sectionPath: "5.5 Color Schemes and Display Order"
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Override chains resolve by load-order priority, with the winner last

`records.base_record` and `records.winning_override` answer different questions.
The base/master record supplies the original data; each later override may replace fields; the final high-priority override is what wins at runtime.

xEdit's View tab shows this left-to-right: earlier loaded files left, winner on the right.
Mutagen's `PriorityOrder` documentation describes the same winner concept from the programmatic side.

When diagnosing a missing change, report both the intended plugin and the actual winning file.
