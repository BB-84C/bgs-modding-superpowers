---
id: archive-precedence.bsa-vs-ba2-by-game.v1
title: BSA and BA2 archive formats are game-family specific
domains: [archive-precedence, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Older Bethesda games and Skyrim-family titles use BSA archives, while Fallout 4 and Starfield use BA2-style archives; pack assets for the target game's runtime, not just for the file extension you know.
  confidence: high
queryKeys: [BSA, BA2, archive format, Bethesda archive, asset packaging]
severity: high
sources:
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
  - kind: wiki
    url: "https://stepmodifications.org/wiki/Main_Page"
    ref: STEP Wiki
related: [archive-precedence.loose-over-archive.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# BSA and BA2 archive formats are game-family specific

Archive advice is not portable across every BGS game.
Fallout 3, Fallout New Vegas, and Skyrim-family titles use BSA archives, while Fallout 4 and Starfield use BA2-family packaging.

The runtime, archive tool, and asset type decide what can be packed safely.
When diagnosing a missing asset, confirm the archive format matches the game before treating plugin load order as the likely cause.
