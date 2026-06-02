---
id: engine-quirks.gamebryo-era-not-creation-engine-workflow.v1
title: FO3/FNV quirks come from the older Gamebryo-era workflow
domains: [engine, version-differences, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Fallout 3 and Fallout New Vegas should be treated as legacy Gamebryo-era targets with GECK scripting, legacy load-order files, no Papyrus, and no modern ESL/light-plugin assumptions.
  confidence: verified-project-doc
queryKeys: [Gamebryo, legacy engine, no ESL, GECK workflow, old Fallout]
severity: high
sources:
  - kind: project-internal-doc
    ref: knowledge/bgs-kb/packs/core/records/engine/gamebryo-lineage-fo3-fnv.v1.md
    sectionPath: Canonical answer
related: [engine.gamebryo-lineage-fo3-fnv.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# FO3/FNV quirks come from the older Gamebryo-era workflow

This pack's records intentionally avoid Creation Engine 2, Fallout 4 BA2, Skyrim Papyrus, and Starfield assumptions.
FO3/FNV troubleshooting usually begins with legacy surfaces: GECK scripts, xNVSE/FOSE, old plugin ordering, and memory/crash fixes.

When a core record says "Creation Engine only," do not silently apply it here.
