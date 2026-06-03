---
id: engine.xse-plugin-version-compatibility.v1
title: SKSE F4SE and SFSE plugins are version-locked to supported runtimes
domains: [engine, version-differences, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Script extender DLL ecosystems are tied to specific game runtimes; SKSE, F4SE, and SFSE builds must match the installed executable branch before extender plugins can be trusted.
  confidence: verified-official
queryKeys: [SKSE version, F4SE version, SFSE version, script extender DLL, runtime mismatch]
severity: critical
sources:
  - kind: official
    url: "https://skse.silverlock.org/"
    ref: Skyrim Script Extender home
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: Fallout 4 Script Extender home
  - kind: official
    url: "https://sfse.silverlock.org/"
    ref: Starfield Script Extender home
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SKSE F4SE and SFSE plugins are version-locked to supported runtimes

xSE plugins are native-code extensions, so they are sensitive to game executable changes.
The Silverlock pages publish separate builds for Skyrim editions, Fallout 4 branches including VR, and Starfield, with explicit runtime targets and unsupported storefront notes.

When a modpack breaks after a game update, check extender and DLL compatibility before investigating ordinary plugin conflicts.
Runtime pinning is part of the engine layer, not cosmetic version hygiene.
