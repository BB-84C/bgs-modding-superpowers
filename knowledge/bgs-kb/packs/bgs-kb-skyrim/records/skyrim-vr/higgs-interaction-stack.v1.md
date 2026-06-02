---
id: skyrim-vr.higgs-interaction-stack.v1
title: HIGGS adds Skyrim VR hand interaction and weapon collision semantics
domains: [game-specific.vr, engine]
appliesTo:
  games: [SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "HIGGS adds Skyrim VR hand and weapon collision, two-handing, object grabbing, and gravity-glove style interaction, with SKSEVR as a requirement."
  confidence: high
queryKeys: [HIGGS, Skyrim VR interaction, hand collision, gravity gloves]
severity: high
sources:
  - kind: community-forum
    ref: Nexus Mods HIGGS - Enhanced VR Interaction
    url: https://www.nexusmods.com/skyrimspecialedition/mods/43930
    sectionPath: About this mod; Requirements
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# HIGGS adds Skyrim VR hand interaction and weapon collision semantics

HIGGS changes how the player interacts with objects and weapons in VR.
Its feature surface includes hand/weapon collision, two-handing, grabbing, and gravity-glove style mechanics.

Treat it as an interaction framework, not a simple animation replacer.
Compatibility checks should include SKSEVR version, other VR interaction mods, and physics/animation changes.

Do not assume flat-screen weapon or activation patches cover this interaction layer.
