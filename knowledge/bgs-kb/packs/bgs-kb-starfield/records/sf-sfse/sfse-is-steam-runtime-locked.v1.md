---
id: sf-sfse.sfse-is-steam-runtime-locked.v1
title: SFSE supports only the matching latest Steam Starfield runtime
domains: [version-differences, debugging]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: SFSE is version-locked to the latest Steam Starfield runtime it supports, so native SFSE plugin troubleshooting starts with executable and SFSE version checks.
  confidence: verified-official
queryKeys: [SFSE, Starfield Script Extender, Steam runtime, native plugin]
severity: critical
sources:
  - kind: official
    url: "https://sfse.silverlock.org/"
    ref: Starfield Script Extender home
related: [engine.xse-plugin-version-compatibility.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SFSE supports only the matching latest Steam Starfield runtime

The SFSE page lists its current build and target Starfield version, and states support is for the latest Steam version only.
That makes runtime drift a first-order debugging issue.

If an SFSE plugin fails, record Starfield executable version, SFSE version, and storefront before inspecting plugin records.
Native incompatibility is not solved by load-order sorting.
