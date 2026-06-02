---
id: fo4-vr.fo4vr-is-separate-runtime.v1
title: Fallout 4 VR is a separate runtime, not just Fallout 4 with a headset
domains: [game-specific.vr, version-differences, install-planning]
appliesTo:
  games: [Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 VR has its own executable/runtime and VR-specific systems, so flat Fallout 4 runtime and DLL assumptions must be rechecked.
  confidence: high
queryKeys: [Fallout 4 VR runtime, FO4VR, VR enhanced VATS, HTC Vive]
severity: critical
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_VR"
    ref: Fallout Wiki Fallout 4 VR
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 VR is a separate runtime, not just Fallout 4 with a headset

Fallout 4 VR ships as its own Windows VR game with VR-specific combat, building, and V.A.T.S. presentation.
The world and story overlap with Fallout 4, but runtime compatibility is a separate question.

Do not assume a flat Fallout 4 native DLL or UI mod works in VR.
Classify every mod as data-only, script-dependent, native DLL, UI, or VR interaction before enabling it.
