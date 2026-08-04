---
id: xedit.session-save-deferred-when-pending-shutdown.v1
title: session.save with savedFilesPendingShutdown > 0 is deferred, not durable
kind: rule-candidate
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "A session.save response that reports savedFilesPendingShutdown and savePendingShutdownCount is not durability proof. Do not restart to force or prove a flush: the MCP must retain the pending state and refuse normal stop/restart. Current xEdit automation exposes no authoritative pending-queue inspection or flush command; force is explicit abandonment, not a durability path."
  confidence: verified-project-doc
queryKeys: [session.save, savedFilesPendingShutdown, savePendingShutdownCount, pending save, durability, stop restart refusal]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Save & durability semantics
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: Implications for later batches
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# session.save with savedFilesPendingShutdown > 0 is deferred, not durable

`session.save` returns `savedFilesNow`, `savedFilesPendingShutdown`,
`savedNowCount`, and `savePendingShutdownCount`. A nonzero pending count means
xEdit queued the physical write for shutdown; `dirtyState.dirty` may already be
false and is not evidence that the queued write became durable.

The MCP must retain pending files/count from a successful save result and show
them through `xedit_dirty`. It must refuse normal `xedit_stop` and
`xedit_restart` while that state exists. `force:true` is an auditable
abandonment of the pending save, never a flush or durability assertion.

Current automation lacks an authoritative pending-queue inspection or flush
operation. Keep the daemon alive and treat the result as an upstream capability
gap; do not prescribe restart-plus-readback as a generic workaround.
