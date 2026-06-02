---
id: skyrim-versions.texture-bc7-se-cao-flow.v1
title: Skyrim SE texture conversion often targets BC7 through CAO
domains: [archive-precedence, version-differences, install-planning]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Cathedral Assets Optimizer documents BC7 as a high-quality compression target used by SSE and FO4, making it a common SE asset-conversion step for LE texture packs."
  confidence: high
queryKeys: [BC7, Cathedral Assets Optimizer, texture conversion, Skyrim SE]
severity: medium
sources:
  - kind: community-forum
    ref: Nexus Mods Cathedral Assets Optimizer
    url: https://www.nexusmods.com/skyrimspecialedition/mods/23316
    sectionPath: About this mod
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim SE texture conversion often targets BC7 through CAO

Skyrim LE texture packs may not be ready for SE/AE/VR without asset conversion.
CAO documents texture conversion and compression workflows, including BC7 use for SSE.

Run conversion on a copy or MO2 mod folder, not directly in the game Data directory.
Then verify meshes/textures in-game or with an asset viewer.

Texture conversion is separate from plugin Form 43/Form 44 conversion.
