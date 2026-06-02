---
id: skyrim-vr.planck-requires-higgs-sksevr.v1
title: PLANCK layers physical character interaction on HIGGS and SKSEVR
domains: [game-specific.vr, engine]
appliesTo:
  games: [SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "PLANCK adds physically driven character interaction for Skyrim VR and lists HIGGS plus SKSEVR as requirements, so it belongs above a working VR interaction foundation."
  confidence: high
queryKeys: [PLANCK, physical animation, HIGGS requirement, Skyrim VR]
severity: high
sources:
  - kind: community-forum
    ref: Nexus Mods PLANCK
    url: https://www.nexusmods.com/skyrimspecialedition/mods/66025
    sectionPath: About this mod; Requirements
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# PLANCK layers physical character interaction on HIGGS and SKSEVR

PLANCK is part of the VR physical-interaction stack.
Its page describes physically driven animation and character interactions.

Because it requires HIGGS and SKSEVR, debug those dependencies first when PLANCK behavior fails.
It is not a replacement for VRIK or SkyUI VR.

Install and test the VR interaction stack incrementally: SKSEVR, UI/MCM, HIGGS, then PLANCK.
