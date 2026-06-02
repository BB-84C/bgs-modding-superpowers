---
id: sf-sfse.sfse-plugins-are-native-runtime-risk.v1
title: SFSE plugins are native runtime compatibility risks
domains: [debugging, version-differences]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: SFSE plugin failures should be triaged as native runtime compatibility issues before record conflicts, because the extender layer loads before normal plugin semantics matter.
  confidence: verified-official
queryKeys: [SFSE plugin, native DLL, runtime mismatch, Starfield crash]
severity: critical
sources:
  - kind: official
    url: "https://sfse.silverlock.org/"
    ref: Starfield Script Extender home
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# SFSE plugins are native runtime compatibility risks

SFSE extends Starfield through native runtime integration.
That gives SFSE plugins a different risk profile from data-only Creations or plugin records.

For startup crashes or missing extender functions, verify the executable, SFSE build, and plugin DLL support first.
Only after that should an agent inspect ordinary load-order conflicts.
