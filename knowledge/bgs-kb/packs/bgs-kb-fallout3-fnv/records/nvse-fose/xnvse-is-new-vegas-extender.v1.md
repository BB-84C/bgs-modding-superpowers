---
id: nvse-fose.xnvse-is-new-vegas-extender.v1
title: xNVSE is the Fallout New Vegas script extender line
domains: [engine, install-planning, version-differences]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: xNVSE is the maintained New Vegas Script Extender line for Fallout New Vegas; it is not a Fallout 3 extender and not a normal plugin file.
  confidence: verified-official
queryKeys: [xNVSE, NVSE, New Vegas Script Extender, nvse_loader, FalloutNV]
severity: critical
sources:
  - kind: official
    ref: xNVSE GitHub repository
    url: https://github.com/xNVSE/NVSE
    sectionPath: README and releases
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xNVSE is the Fallout New Vegas script extender line

xNVSE expands Fallout: New Vegas engine and scripting behavior at runtime.
It is separate from xEdit, separate from FOSE, and separate from GECK editor authoring.

When diagnosing a mod that requires xNVSE, verify the New Vegas executable/runtime path and extender installation first.
Do not assume a FO3 FOSE setup or a later-game xSE pattern is interchangeable.
