---
id: tooling.xedit-fo3-fnv-modes-target-legacy-records.v1
title: xEdit FO3/FNV work must launch against the matching legacy game mode
domains: [xedit, debugging, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: FO3Edit/FNVEdit-style xEdit work is only meaningful when launched against the intended Fallout 3 or New Vegas Data/load-order view, not a modern game mode or stale registry path.
  confidence: verified-tooling
queryKeys: [FO3Edit, FNVEdit, xEdit gmFO3, xEdit gmFNV, Fallout 3 xEdit, New Vegas xEdit]
severity: critical
sources:
  - kind: tooling-docs
    ref: Tome of xEdit
    url: https://tes5edit.github.io/docs/
    sectionPath: FO3Edit and FNVEdit training-manual lineage
related: [engine.gamebryo-lineage-fo3-fnv.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit FO3/FNV work must launch against the matching legacy game mode

xEdit documentation preserves FO3Edit and FNVEdit lineage, which is the relevant family for Fallout 3 and Fallout: New Vegas plugin inspection.
An xEdit session in the wrong game mode can still show records, but the evidence will describe the wrong runtime.

For MO2-backed tests, prove the selected profile, active legacy plugin list, and game-specific xEdit mode before auditing conflicts.
