---
id: fo4-vr.fo4vr-next-gen-does-not-track-flat.v1
title: Fallout 4 VR does not track flat Fallout 4 next-gen branches one-to-one
domains: [game-specific.vr, version-differences]
appliesTo:
  games: [Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 VR has its own runtime and F4SEVR target, so next-gen advice for flat Fallout 4 must not be copied into VR without checking the VR branch.
  confidence: verified-official
queryKeys: [FO4VR next-gen, F4SEVR, VR runtime, flat Fallout 4]
severity: high
sources:
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_VR"
    ref: Fallout Wiki Fallout 4 VR
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 VR does not track flat Fallout 4 next-gen branches one-to-one

Flat Fallout 4 and Fallout 4 VR have different runtime targets and F4SE entries.
That makes next-gen DLL, archive, and Creation content advice branch-specific.

When a guide says “Fallout 4 next-gen,” do not assume it applies to VR.
Check F4SEVR support and the actual VR executable before porting the fix.
