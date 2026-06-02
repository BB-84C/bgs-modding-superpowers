---
id: load-order.compact-formid-light-range.v1
title: ESL-compact FormIDs must fit the light-plugin subrange
domains: [load-order, plugin-format, xedit]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [SkyrimLE, Fallout3, FalloutNV]
canonical:
  answer: ESL-flagged plugins use the compact light-plugin FormID space, so candidates must be compacted into the valid low FormID subset before they can safely behave as light plugins.
  confidence: verified-project-doc
queryKeys: [compact FormID, xx000800, xx000FFF, ESL compact, light master limit]
severity: critical
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: ESL conversion
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
related: [load-order.esl-flag-lives-in-header.v1, load-order.esl-extension-vs-header-flag.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ESL-compact FormIDs must fit the light-plugin subrange

Light plugins are not just “full plugins counted differently.”
Their records must fit the compact light-plugin FormID range, commonly described for compacted records as the usable `xx000800` through `xx000FFF` subset.

Run xEdit analysis before applying an ESL flag so out-of-range records are caught before runtime.
The 4096 light-plugin count is separate from the 255 full-plugin ceiling, but each light plugin still has its own compact record-space constraint.
