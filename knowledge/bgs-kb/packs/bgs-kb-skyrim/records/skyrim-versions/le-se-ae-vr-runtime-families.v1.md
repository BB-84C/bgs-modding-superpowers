---
id: skyrim-versions.le-se-ae-vr-runtime-families.v1
title: Skyrim LE SE AE and VR are separate compatibility targets
domains: [version-differences, engine, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim LE, SE 1.5.97, AE 1.6.x, GOG AE, and VR have different runtime and script-extender compatibility targets even when the gameplay content looks similar."
  confidence: verified-tooling
queryKeys: [Skyrim LE, Skyrim SE, Skyrim AE, Skyrim VR, runtime family]
severity: critical
sources:
  - kind: tooling-docs
    ref: SKSE silverlock downloads
    url: https://skse.silverlock.org/
    sectionPath: Current builds
related: [skyrim-scripts.skse-runtime-matrix.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim LE SE AE and VR are separate compatibility targets

Treat each Skyrim runtime family as a separate modpack target.
Texture and plugin data may overlap, but native plugins, script extender builds, and VR interaction layers do not.

The SKSE page is the fastest compatibility matrix for this distinction.
If a guide only says "Skyrim" without runtime, it is incomplete for modern modpack work.

Record the exact runtime before evaluating any SKSE DLL mod.
