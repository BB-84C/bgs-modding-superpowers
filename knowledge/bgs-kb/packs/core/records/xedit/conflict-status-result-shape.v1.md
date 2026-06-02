---
id: xedit.conflict-status-result-shape.v1
title: records.conflict_status returns the conflict label under result.conflict.all
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The records.conflict_status daemon response carries the xEdit caXxx conflict enum under result.conflict.all, not as a flat result.status field.
  confidence: verified-project-doc
queryKeys: [conflict_status, result.conflict.all, caConflict, caITM, caITPO]
severity: medium
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# records.conflict_status returns the conflict label under result.conflict.all

Conflict-status readback uses xEdit's own `caXxx` enum labels, such as `caConflict`, `caITM`, `caITPO`, `caConflictCritical`, and `caOnlyOne`.
The durable field is nested at `result.conflict.all`.

Agents should not look for a top-level `result.status` unless they are handling legacy unit-test mocks.
Verdict mapping belongs in one shared adapter so every conflict-audit tool interprets the enum consistently.

When a conflict verdict looks empty, inspect the nested response object before assuming the daemon omitted the data.
