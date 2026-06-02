---
id: engine.fo4-previs-prvs-couples-to-precombines.v1
title: Fallout 4 previs data is coupled to precombined geometry decisions
domains: [engine, file-conflicts, debugging]
appliesTo:
  games: [Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
canonical:
  answer: Fallout 4 previs data and precombined geometry should be reasoned about together; changing one side without rebuilding the matching visibility data can create occlusion, pop-in, or performance problems.
  confidence: medium
queryKeys: [previs, PRVS, precombines, occlusion, Fallout 4 visibility]
severity: critical
sources:
  - kind: community-forum
    url: "https://www.afkmods.com/index.php?/forum/350-unofficial-fallout-4-patch/"
    ref: AFK Mods Unofficial Fallout 4 Patch forum
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4"
    ref: Independent Fallout Wiki Fallout 4
related: [engine.fo4-precombined-meshes-propagate-breakage.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 previs data is coupled to precombined geometry decisions

Previs is the visibility side of the same broad optimization story as precombined geometry.
If an area edit invalidates precombines but leaves stale visibility data, the runtime can cull or show the wrong things.

Do not prescribe only a plugin-order change for FO4 cell visibility defects.
Check whether the mod deliberately rebuilds precombines and previs for the edited area.
