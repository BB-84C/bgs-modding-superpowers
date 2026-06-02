---
id: xedit.conflict-ca-conflict.v1
title: caConflict marks a divergent override conflict that needs review
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: caConflict means xEdit found divergent values in an override chain; map it to an MCP minor/conflict verdict and inspect actual fields before deciding whether it is harmless or patch-worthy.
  confidence: verified-tooling
queryKeys: [caConflict, minor conflict, conflict loser, conflict winner, divergent override]
severity: high
sources:
  - kind: tooling-docs
    ref: xEdit Docs / Tome of xEdit
    url: https://tes5edit.github.io/docs/5-conflict-detection-and-resolution.html
    sectionPath: "5.2 Differences between Conflicts and Overrides"
  - kind: project-skill
    ref: skills/xedit-conflict-audit/SKILL.md
    sectionPath: Workflow
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# caConflict marks a divergent override conflict that needs review

Map `caConflict` to an MCP verdict that forces human-readable field review, usually `minor` unless the audited field is known to be game-breaking.
The label says there are competing edits, not which edit is correct.

The readback must include the participant chain and the winning override.
Patch decisions come from the actual values, not from the enum label alone.

For concise reports, surface `caConflict` records with file, FormID, winning file, and the changed fields.
