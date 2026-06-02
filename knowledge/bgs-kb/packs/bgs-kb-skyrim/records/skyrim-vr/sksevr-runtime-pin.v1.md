---
id: skyrim-vr.sksevr-runtime-pin.v1
title: Skyrim VR uses SKSEVR pinned to runtime 1.4.15
domains: [game-specific.vr, engine, version-differences]
appliesTo:
  games: [SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim VR uses the SKSEVR build line, currently pinned on the SKSE page to SkyrimVR runtime 1.4.15, not the SE or AE SKSE64 build."
  confidence: verified-tooling
queryKeys: [SKSEVR, SkyrimVR 1.4.15, VR runtime, sksevr_2_00_12]
severity: critical
sources:
  - kind: tooling-docs
    ref: SKSE silverlock downloads
    url: https://skse.silverlock.org/
    sectionPath: VR build
related: [skyrim-scripts.skse-runtime-matrix.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim VR uses SKSEVR pinned to runtime 1.4.15

Do not install the AE or SE SKSE64 archive into Skyrim VR.
The SKSE page has a separate VR build and runtime target.

This also affects every native DLL mod in the VR profile.
If a mod only ships SE/AE DLLs and no VR-compatible build, treat it as incompatible until proven otherwise.

Skyrim VR modlists should version-pin SKSEVR alongside the executable and Address Library for SKSEVR.
