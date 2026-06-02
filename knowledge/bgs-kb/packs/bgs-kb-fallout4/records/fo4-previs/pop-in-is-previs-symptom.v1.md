---
id: fo4-previs.pop-in-is-previs-symptom.v1
title: Rock and building pop-in is a Fallout 4 previs symptom to investigate
domains: [engine, debugging]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Sudden object or terrain-piece pop-in around edited Fallout 4 cells is a practical symptom that previs or precombine data may be stale, missing, or losing conflicts.
  confidence: medium
queryKeys: [rocks pop in, building pop in, previs broken, visibility pop-in, FO4 flicker]
severity: high
sources:
  - kind: community-forum
    url: "https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/"
    ref: AFK Mods UFO4P forum
related: [fo4-previs.precombines-and-previs-are-one-minefield.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Rock and building pop-in is a Fallout 4 previs symptom to investigate

Previs problems often surface visually before they are obvious in xEdit.
Objects may appear too late, disappear from certain angles, flicker, or load in chunks as the player moves.

When the symptom is location-specific, inspect the cell stack and any generated visibility assets for that area.
If it appears only after adding a settlement or scrap mod, prioritize precombine/previs review.
