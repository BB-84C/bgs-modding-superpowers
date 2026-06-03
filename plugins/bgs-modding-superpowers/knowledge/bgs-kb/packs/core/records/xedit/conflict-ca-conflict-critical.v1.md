---
id: xedit.conflict-ca-conflict-critical.v1
title: caConflictCritical should halt automatic resolution
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: caConflictCritical is the high-severity xEdit conflict class; map it to the MCP breaking verdict and stop automatic resolution until the divergent fields are inspected.
  confidence: verified-project-doc
queryKeys: [caConflictCritical, critical conflict, breaking verdict, halt conflict audit]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-conflict-audit/SKILL.md
    sectionPath: Workflow
  - kind: tooling-docs
    ref: xEdit Docs / Tome of xEdit
    url: https://tes5edit.github.io/docs/5-conflict-detection-and-resolution.html
    sectionPath: "5.5 Color Schemes and Display Order"
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# caConflictCritical should halt automatic resolution

Map `caConflictCritical` to `breaking` in the MCP conflict verdict layer.
It is the enum that should stop a fixer from silently treating the record as routine cleanup.

The next action is field-level readback: base record, each override, and winning override.
Only after naming the divergent fields can an agent recommend patching, reordering, or leaving the winner alone.

If a summary only says "critical conflict" without field names, it is not acceptance evidence.
