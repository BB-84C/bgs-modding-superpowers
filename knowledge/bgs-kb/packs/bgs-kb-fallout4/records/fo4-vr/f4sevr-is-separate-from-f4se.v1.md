---
id: fo4-vr.f4sevr-is-separate-from-f4se.v1
title: F4SEVR is separate from flat Fallout 4 F4SE
domains: [game-specific.vr, version-differences, debugging]
appliesTo:
  games: [Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 VR uses the F4SEVR branch and runtime target, not the flat Fallout 4 F4SE build.
  confidence: verified-official
queryKeys: [F4SEVR, Fallout 4 VR script extender, runtime 1.2.72]
severity: critical
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
related: [fo4-vr.fo4vr-is-separate-runtime.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# F4SEVR is separate from flat Fallout 4 F4SE

The F4SE page lists a dedicated Fallout 4 VR build and runtime target.
That means native extender mods must be checked against VR support, not only Fallout 4 support.

If a mod ships a DLL for flat Fallout 4 only, assume it is incompatible with VR until the author says otherwise.
ESP-only compatibility does not prove native compatibility.
