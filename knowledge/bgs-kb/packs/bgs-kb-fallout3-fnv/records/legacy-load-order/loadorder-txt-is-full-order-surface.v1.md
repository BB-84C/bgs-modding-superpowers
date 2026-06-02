---
id: legacy-load-order.loadorder-txt-is-full-order-surface.v1
title: loadorder.txt carries the full Fallout 3 and New Vegas order
domains: [load-order]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: In the legacy load-order model, plugins.txt is the active list and loadorder.txt is the separate full-order surface that may include inactive plugins.
  confidence: verified-project-doc
queryKeys: [loadorder.txt, full load order, inactive plugins, legacy order]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Legacy format
related: [load-order.plugins-txt-legacy.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# loadorder.txt carries the full Fallout 3 and New Vegas order

For FO3/FNV, order and activation are split across two profile files.
Only checking `plugins.txt` can miss inactive entries whose relative order still matters when re-enabled.

When generating a custom xEdit plugin set or reconciling MO2 profile drift, reason about both surfaces together.
