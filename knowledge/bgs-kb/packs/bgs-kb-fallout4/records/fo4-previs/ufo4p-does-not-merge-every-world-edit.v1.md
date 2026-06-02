---
id: fo4-previs.ufo4p-does-not-merge-every-world-edit.v1
title: UFO4P is not a universal merge patch for later Fallout 4 world edits
domains: [engine, xedit, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: UFO4P is an unofficial patch project, not a compatibility patch for every mod loaded after it, so later world edits still need conflict and previs review.
  confidence: high
queryKeys: [UFO4P, Unofficial Fallout 4 Patch, compatibility patch, world edits]
severity: high
sources:
  - kind: community-forum
    url: "https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/"
    ref: AFK Mods UFO4P forum
related: [xedit.override-chain-winning-order.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# UFO4P is not a universal merge patch for later Fallout 4 world edits

The AFK Mods forum is the active discussion surface for the Unofficial Fallout 4 Patch.
That does not make UFO4P responsible for resolving every conflict introduced by a user's later mods.

If a mod overrides the same records after UFO4P, the later plugin can still win and reintroduce an issue.
Check winning overrides and purpose-built compatibility patches rather than assuming the unofficial patch covers the full stack.
