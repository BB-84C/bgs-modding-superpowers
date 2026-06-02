---
id: skyrim-versions.skyrimvr-ae-update-isolation.v1
title: Skyrim VR is isolated from AE runtime churn
domains: [game-specific.vr, version-differences]
appliesTo:
  games: [SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim VR remains on its own runtime and SKSEVR build, so AE update breakage should not be projected onto VR without checking VR-specific dependencies."
  confidence: verified-tooling
queryKeys: [Skyrim VR AE update, SKSEVR, runtime isolation]
severity: medium
sources:
  - kind: tooling-docs
    ref: SKSE silverlock downloads
    url: https://skse.silverlock.org/
    sectionPath: VR build
related: [skyrim-vr.sksevr-runtime-pin.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim VR is isolated from AE runtime churn

Skyrim VR does not receive the same AE executable updates as Steam Skyrim AE.
Its risk is different: VR-specific SKSEVR, Address Library, and interaction-framework compatibility.

Do not install an AE hotfix DLL into VR just because the mod name matches.
Check whether the author ships a VR build or uses a multi-runtime CommonLib path.

When a guide says AE-compatible, that is not automatically VR-compatible.
