---
id: skyrim-quirks.ussep-latest-runtime-policy.v1
title: USSEP tracks the latest Steam Skyrim Special Edition release
domains: [install-planning, version-differences]
appliesTo:
  games: [SkyrimSE, SkyrimAE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "USSEP is a comprehensive Skyrim Special Edition bugfix mod whose AFK page warns to use it with the latest Steam-patched Skyrim SE release."
  confidence: high
queryKeys: [USSEP, Unofficial Skyrim Special Edition Patch, latest runtime, AE]
severity: high
sources:
  - kind: community-forum
    ref: AFK Mods Unofficial Skyrim Special Edition Patch
    url: https://www.afkmods.com/index.php?/files/file/1888-unofficial-skyrim-special-edition-patch/
    sectionPath: File description
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# USSEP tracks the latest Steam Skyrim Special Edition release

USSEP is broad bugfix infrastructure for modern Skyrim, not a small optional tweak.
Its AFK page states a goal of fixing unresolved Skyrim and DLC bugs within CK/tool limits.

The same page warns that older game versions may see bugs or missing fixes.
That makes USSEP a runtime policy decision for downgraded SE modlists.

Record the USSEP version and game runtime together.
