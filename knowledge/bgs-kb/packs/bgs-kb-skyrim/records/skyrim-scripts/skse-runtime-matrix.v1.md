---
id: skyrim-scripts.skse-runtime-matrix.v1
title: SKSE build choice is pinned to the Skyrim runtime family
domains: [engine, papyrus, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "SKSE is not one binary for every Skyrim edition: LE, SE 1.5.97, AE 1.6.x, GOG AE, and Skyrim VR each use their matching SKSE/SKSE64/SKSEVR build."
  confidence: verified-tooling
queryKeys: [SKSE, SKSE64, SKSEVR, runtime version, Skyrim AE, Skyrim VR]
severity: critical
sources:
  - kind: tooling-docs
    ref: SKSE silverlock downloads
    url: https://skse.silverlock.org/
    sectionPath: Current classic / SE / AE / VR builds
related: [engine.xse-plugin-version-compatibility.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SKSE build choice is pinned to the Skyrim runtime family

The SKSE download page lists separate builds for classic Skyrim, SE 1.5.97, AE 1.6.x, GOG AE, and Skyrim VR.
Treat those as runtime pins, not loose recommendations.

For a modpack, record the game executable version and the matching SKSE build together.
If the game updates but SKSE or its DLL plugins do not, startup crashes are expected.

Skyrim VR is a separate runtime line with SKSEVR, not just another SE install.
