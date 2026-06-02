---
id: fo4-previs.scrap-mods-can-break-previs.v1
title: Scrap and cleanup mods are common Fallout 4 precombine risk factors
domains: [engine, file-conflicts, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Mods that make many static objects scrappable or delete visible clutter can invalidate Fallout 4 precombined geometry unless they provide compatible rebuilt data.
  confidence: medium
queryKeys: [scrap everything, scrap mods, broken precombines, settlement cleanup]
severity: critical
sources:
  - kind: community-forum
    url: "https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/"
    ref: AFK Mods UFO4P forum
related: [engine.fo4-precombined-meshes-propagate-breakage.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Scrap and cleanup mods are common Fallout 4 precombine risk factors

Fallout 4's optimization assumes many statics remain bundled into precombined geometry.
Mods that let players scrap broad object sets change that assumption.

If a cleanup mod touches many cells without matching precombine/previs output, expect performance or visibility symptoms.
Do not diagnose these as ordinary plugin conflicts until the optimization data is checked.
