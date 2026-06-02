---
id: archive-precedence.loose-over-archive.v1
title: Loose files override archived assets at runtime
domains: [archive-precedence, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Loose files generally override archived assets at runtime, so plugin load order alone does not determine every asset winner.
  confidence: high
variants:
  Fallout4:
    additions:
      - BA2 packaging and precombine/previs state can be the visible winner surface even when plugin-side conflicts look clean.
    warnings:
      - code: PREVIS
        severity: high
        text: Check precombine and previs integrity before treating load order as the only likely cause.
  SkyrimSE:
    additions:
      - Generated behavior outputs from Nemesis or FNIS can dominate animation behavior after loose-file resolution.
    warnings:
      - code: GENERATED_OUTPUTS
        severity: medium
        text: Inspect generated behavior files when animation assets look correct but behavior remains wrong.
queryKeys: [loose files override, archive precedence, BSA, BA2, file conflict]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Routing matrix and validation
  - kind: tooling-docs
    url: https://tes5edit.github.io/docs/
    ref: Tome of xEdit
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Loose files override archived assets at runtime

Asset visibility is not decided only by plugin record order.
Loose files can override archived assets, so a mesh, texture, script, or generated output may win even when xEdit shows no plugin-side conflict.

For Fallout 4, also consider BA2 packaging and precombine/previs integrity before blaming only load order.
For Skyrim SE animation issues, generated behavior outputs can be the practical winner surface.

Agents should separate record conflicts from file conflicts and verify the runtime asset surface before prescribing plugin-order edits.
