---
id: nvse-fose.jip-ln-adds-functions-and-engine-fixes.v1
title: JIP LN NVSE Plugin extends xNVSE with functions and engine fixes
domains: [engine, debugging, install-planning]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: JIP LN NVSE Plugin is an xNVSE extension for New Vegas that adds many GECK-callable functions and engine fixes, making it a frequent hard requirement for modern FNV and TTW setups.
  confidence: high
queryKeys: [JIP LN, JIP NVSE, NVSE plugin, GECK functions, TTW essentials]
severity: critical
sources:
  - kind: community-forum
    ref: JIP LN NVSE Plugin Nexus page
    url: https://www.nexusmods.com/newvegas/mods/58277
    sectionPath: About this mod and requirements
  - kind: community-forum
    ref: The Best of Times Essentials
    url: https://thebestoftimes.moddinglinked.com/essentials.html
    sectionPath: JIP LN NVSE Plugin
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# JIP LN NVSE Plugin extends xNVSE with functions and engine fixes

JIP LN is not a standalone script extender.
It is an NVSE/xNVSE plugin layered on top of the New Vegas extender, adding a large function surface and engine-level fixes used by many current mods.

When a script compiles but fails in game, check whether the function comes from vanilla GECK, xNVSE, or a plugin such as JIP LN.
