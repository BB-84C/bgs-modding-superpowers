---
id: skyrim-versions.ae-update-dll-breakage.v1
title: AE runtime bumps mainly break native SKSE DLL plugins
domains: [version-differences, engine, debugging]
appliesTo:
  games: [SkyrimAE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Anniversary Edition runtime updates primarily threaten SKSE native DLL plugins; Papyrus-only mods and pure assets are not the same compatibility risk class."
  confidence: verified-tooling
queryKeys: [AE update, SKSE DLL, Address Library, runtime bump]
severity: critical
sources:
  - kind: tooling-docs
    ref: SKSE silverlock downloads
    url: https://skse.silverlock.org/
    sectionPath: Startup crash after game patch
  - kind: tooling-docs
    ref: CommonLibSSE-NG GitHub
    url: https://github.com/CharmedBaryon/CommonLibSSE-NG
    sectionPath: Runtime support
related: [skyrim-scripts.skse-plugin-dll-mismatch.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# AE runtime bumps mainly break native SKSE DLL plugins

When AE updates, do not panic-reinstall every texture and ESP mod.
Start with SKSE itself and native SKSE plugins.

CommonLibSSE NG can help plugin authors support multiple runtimes, but each mod must actually ship a compatible build.
Address Library also has to match the runtime family.

Classify mods by native DLL, Papyrus-only, plugin data, and assets before triaging breakage.
