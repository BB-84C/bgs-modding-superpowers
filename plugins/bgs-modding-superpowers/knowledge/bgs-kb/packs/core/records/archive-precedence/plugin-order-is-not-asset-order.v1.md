---
id: archive-precedence.plugin-order-is-not-asset-order.v1
title: Plugin order and asset deployment order are related but separate decisions
domains: [archive-precedence, load-order, file-conflicts, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Plugin load order decides record winners, while asset deployment and archive/loose-file precedence decide file winners; agents must diagnose the right layer before prescribing a fix.
  confidence: verified-project-doc
queryKeys: [asset order, plugin order, file winner, record winner, archive precedence]
severity: high
sources:
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: Systematic Modpack Workflow
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Routing matrix
related: [archive-precedence.loose-over-archive.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Plugin order and asset deployment order are related but separate decisions

Record conflicts and file conflicts can produce similar symptoms, but they are not the same substrate.
Plugin order determines which record override wins in xEdit.

Asset deployment, archive packing, loose-file precedence, and generated outputs determine which file the runtime sees.
Changing plugin order will not necessarily fix a mesh, texture, animation, script, or LOD file winner.

Agents should classify the symptom layer first, then pick the corresponding load-order, archive, or install-planning action.
