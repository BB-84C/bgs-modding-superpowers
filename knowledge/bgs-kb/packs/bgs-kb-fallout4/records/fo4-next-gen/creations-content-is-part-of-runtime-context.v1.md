---
id: fo4-next-gen.creations-content-is-part-of-runtime-context.v1
title: Bethesda Creations content is part of the Fallout 4 runtime context
domains: [version-differences, load-order, install-planning]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Creations-era official content can affect the official-master and content baseline, so agents should inspect the actual runtime rather than assuming a fixed pre-next-gen vanilla set.
  confidence: verified-project-doc
queryKeys: [Fallout 4 Creations, official content, next-gen content, vanilla masters]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Official / vanilla masters
related: [load-order.official-masters-fallout4.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Bethesda Creations content is part of the Fallout 4 runtime context

After next-gen changes, “vanilla Fallout 4” is not always the same installed content set across machines.
Official or verified content can be present before user-managed plugins enter the picture.

For load-order generation and xEdit launches, inspect the actual Data view and early loaded files.
Do not hardcode a static official-master list from memory.
