---
id: debugging.load001-active-load-order-refusal.v1
title: LOAD001 refuses record operations against files outside the active load order
domains: [debugging, xedit, load-order]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The xEdit MCP seed rule LOAD001 blocks read-side and passthrough operations that target a plugin not present in the active load order.
  confidence: verified-project-doc
queryKeys: [LOAD001, active load order, state_violation, file not loaded]
severity: critical
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What Batch 1 actually delivered
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-05-31 — Batch 1 closeout
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# LOAD001 refuses record operations against files outside the active load order

LOAD001 is the first rule-layer protection in the xEdit MCP.
It prevents agents from reading or composing operations against plugin files that xEdit did not actually load.

When this rule refuses a call, the recovery is to inspect the active load order and launch shape, not to bypass through raw CLI.
The refusal is a signal that the target state is not visible to the daemon.

This rule helps distinguish missing plugin visibility from record-level lookup failure.
