---
id: fo4-previs.precombines-and-previs-are-one-minefield.v1
title: Fallout 4 precombines and previs form a coupled install minefield
domains: [engine, file-conflicts, debugging]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: In Fallout 4, precombined geometry and previs visibility data must be treated together; mods that invalidate one side can produce FPS loss, flicker, pop-in, or missing geometry.
  confidence: medium
queryKeys: [Fallout 4 precombines, previs, PRVS, PRECOMB, broken precombines, mod evaluation, precombine breaking, placed objects, object density, visibility culling]
severity: critical
sources:
  - kind: community-forum
    url: "https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/"
    ref: AFK Mods UFO4P forum
related: [engine.fo4-precombined-meshes-propagate-breakage.v1, engine.fo4-previs-prvs-couples-to-precombines.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 precombines and previs form a coupled install minefield

The core pack already records that precombines and previs are coupled.
For FO4 modlists, this becomes an install rule: cell-editing mods need to be checked for rebuilt data, not just sorted late.

Treat broad world edits, settlement expansions, scrapping mods, and lighting overhauls as precombine/previs suspects.

Precombine/previs recovery only restores the modified mods themselves. Any mod that places NEW objects in the worldspace bypasses visibility culling unconditionally — even after a precombine fix — so limit placed-object-density mods (decoration and settlement clutter) rather than assuming a recovery pass covers them.

AFK UFO4P provides an active FO4 patching forum, but this record does not claim a specific fix list from the index alone.
