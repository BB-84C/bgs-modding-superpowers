---
id: nvse-fose.johnnyguitar-showoff-are-addon-extenders.v1
title: JohnnyGuitar and ShowOff are xNVSE addon-plugin layers
domains: [engine, debugging, install-planning]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: JohnnyGuitar NVSE and ShowOff xNVSE are addon plugins that depend on the New Vegas extender stack and expose additional functions, tweaks, or runtime fixes.
  confidence: high
queryKeys: [JohnnyGuitar NVSE, ShowOff xNVSE, addon plugin, NVSE extension]
severity: high
sources:
  - kind: community-forum
    ref: JohnnyGuitar NVSE Nexus page
    url: https://www.nexusmods.com/newvegas/mods/66927
    sectionPath: Requirements
  - kind: community-forum
    ref: ShowOff xNVSE Plugin Nexus page
    url: https://www.nexusmods.com/newvegas/mods/72541
    sectionPath: About this mod and requirements
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# JohnnyGuitar and ShowOff are xNVSE addon-plugin layers

These plugins should be treated as native New Vegas extender dependencies, not as ordinary `.esp` load-order entries.
They require a compatible xNVSE baseline and may themselves have versioned requirements.

When a mod lists JohnnyGuitar or ShowOff, verify both the base xNVSE install and the addon plugin version before investigating game records.
