---
id: tooling.new-vegas-mcm-is-not-skyui-mcm.v1
title: New Vegas MCM is its own menu framework, not SkyUI MCM
domains: [engine, install-planning]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Fallout New Vegas has its own Mod Configuration Menu framework that adds a Mod Configuration button to the pause menu and depends on NVSE/xNVSE, not Skyrim SkyUI.
  confidence: high
queryKeys: [MCM, Mod Configuration Menu, New Vegas MCM, SkyUI MCM, pause menu]
severity: medium
sources:
  - kind: community-forum
    ref: The Mod Configuration Menu Nexus page
    url: https://www.nexusmods.com/newvegas/mods/42507
    sectionPath: About this mod and requirements
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# New Vegas MCM is its own menu framework, not SkyUI MCM

New Vegas MCM is a separate UI/modder-resource ecosystem.
It supplies an in-game configuration surface for MCM-aware New Vegas mods and depends on the New Vegas script extender stack.

Do not route New Vegas MCM issues through Skyrim SkyUI records or SWF assumptions without a game-specific check.
