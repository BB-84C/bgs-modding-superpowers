---
id: geck-scripting.begin-end-blocktypes-drive-scripts.v1
title: GECK scripts execute inside begin/end blocktypes
domains: [engine, debugging]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: GECK script commands live inside begin/end blocks such as GameMode, MenuMode, OnActivate, OnEquip, OnHit, and OnDeath; the blocktype controls when the script body runs.
  confidence: high
queryKeys: [Begin, GameMode, OnActivate, OnEquip, OnHit, blocktype]
severity: high
sources:
  - kind: wiki
    ref: GECK Wiki Begin
    url: https://geckwiki.com/index.php?title=Begin
    sectionPath: Blocktype table
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# GECK scripts execute inside begin/end blocktypes

In GECK scripting, variable declarations are separate, but executable commands are placed inside `begin ... end` blocks.
The blocktype is the event or loop boundary: `GameMode` runs during ordinary play, `MenuMode` runs in menus, and one-shot blocks such as `OnActivate`, `OnEquip`, or `OnHit` react to their matching gameplay event.

When debugging a script, first identify which block can actually fire in the observed scenario.
