---
id: fo4-tooling.ba2-asset-tools-need-runtime-awareness.v1
title: FO4 BA2 asset tooling must match the target runtime branch
domains: [archive-precedence, version-differences, install-planning]
appliesTo:
  games: [Fallout4, Fallout4VR]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 BA2 packaging and extraction tools must be checked against the target runtime branch, especially around next-gen archive compatibility assumptions.
  confidence: medium
queryKeys: [BA2, BSA Browser, archive2, FO4 next-gen BA2, asset archive]
severity: high
sources:
  - kind: project-internal-doc
    ref: knowledge/bgs-kb/packs/core/records/archive-precedence/fo4-next-gen-ba2-version-bump.v1.md
    sectionPath: Core archive-precedence record
related: [archive-precedence.fo4-next-gen-ba2-version-bump.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# FO4 BA2 asset tooling must match the target runtime branch

BA2 archives are part of Fallout 4's asset delivery layer.
If archive tools were built around an older runtime assumption, next-gen-era compatibility can become the failure point.

When packed textures or meshes disappear, verify archive version, tool output, and runtime branch.
Do not solve a BA2 packaging error by changing plugin order.
