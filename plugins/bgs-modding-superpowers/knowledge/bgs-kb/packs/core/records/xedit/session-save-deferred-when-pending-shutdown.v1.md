---
id: xedit.session-save-deferred-when-pending-shutdown.v1
title: session.save with savedFilesPendingShutdown > 0 is deferred, not durable
kind: rule-candidate
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "A session.save response that reports savedFilesPendingShutdown and savePendingShutdownCount is not durability proof. On automation contract 0.23, inspect the authoritative pending queue through xedit_dirty, then use lifecycle-owned xedit_flush and require a completed drain with zero remaining plus fresh-daemon readback. Restart alone and force:true are not durability paths."
  confidence: verified-project-doc
queryKeys: [session.save, session.flush, xedit_flush, savedFilesPendingShutdown, pendingShutdownFiles, savePendingShutdownCount, pending save, durability]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Save & durability semantics
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: Implications for later batches
  - kind: tooling-docs
    url: "https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.9"
    ref: "TES5Edit automation r9, contract 0.23"
lastReviewed: "2026-08-11"
schemaVersion: 1
---

# session.save with savedFilesPendingShutdown > 0 is deferred, not durable

`session.save` returns `savedFilesNow`, `savedFilesPendingShutdown`,
`savedNowCount`, and `savePendingShutdownCount`. A nonzero pending count means
xEdit queued the physical write for shutdown; `dirtyState.dirty` may already be
false and is not evidence that the queued write became durable.

The MCP retains pending files/count from a successful save result and shows
them through `xedit_dirty`. On contract 0.23, the daemon's complete
`pendingShutdownFiles` / `pendingShutdownCount` readback replaces stale local
fallback knowledge. Missing fields or a failed probe never mean zero.

If pending remains, use `xedit_flush`, not `xedit_call session.flush`. The MCP
validates `flushedFiles`, `pendingRemaining`, and the matching count, then waits
for the managed daemon's promised self-exit. Only `completed` with zero remaining,
followed by a fresh-daemon plugin readback, supports a strong durability claim.
`partial` or `outcome: unknown` remains visible as `lastFlush` residue.
For a partial drain, failed renames stay queued for one final normal process-exit
retry. Relaunch and read the plugin back before deciding whether they landed;
after relaunch the old summary is identified as `previousSessionFlush`.
`force:true` on stop/restart is auditable abandonment, never a flush.
