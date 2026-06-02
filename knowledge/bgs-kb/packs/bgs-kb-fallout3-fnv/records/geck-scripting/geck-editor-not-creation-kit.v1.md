---
id: geck-scripting.geck-editor-not-creation-kit.v1
title: Fallout 3 and New Vegas use GECK scripting, not Papyrus
domains: [engine, debugging]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Fallout 3 and Fallout New Vegas mod authoring centers on the Garden of Eden Creation Kit and its result-script/block model, not the Creation Kit Papyrus VM used by later games.
  confidence: high
queryKeys: [GECK, Creation Kit, Papyrus, Fallout 3 scripting, New Vegas scripting]
severity: critical
sources:
  - kind: wiki
    ref: GECK Wiki Main Page
    url: https://geckwiki.com/index.php?title=Main_Page
    sectionPath: Garden of Eden Creation Kit overview
related: [load-order.plugins-txt-legacy.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 3 and New Vegas use GECK scripting, not Papyrus

The GECK Wiki describes the Garden of Eden Creation Kit as the editor and help surface for making Fallout 3 and Fallout: New Vegas mods.
Do not apply Papyrus lifecycle, property, or fragment assumptions from Skyrim or Fallout 4 to these games.

For agents, this changes both terminology and verification: inspect GECK script blocks, result scripts, quest delays, and NVSE/FOSE function availability instead of Papyrus source and compiled `.pex` behavior.
