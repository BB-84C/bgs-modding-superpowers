---
id: debugging.dirty-state-before-stop-restart.v1
title: Check xEdit dirty state before stop or restart
kind: rule-candidate
domains: [debugging, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Before stopping or restarting xEdit, inspect both unsaved dirty files and pending-shutdown renames. Contract 0.23 supplies authoritative pending readback; the MCP keeps a local fail-closed fallback for older daemons. A failed dirty-state probe must refuse normal lifecycle operations, and a live pending queue should be resolved with xedit_flush rather than restart.
  confidence: verified-project-doc
queryKeys: [xedit_dirty, xedit_flush, session.get_dirty_state, pendingShutdownFiles, pending shutdown save, unsaved changes, stop restart]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Dirty-state checks
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout
lastReviewed: "2026-08-11"
schemaVersion: 1
---

# Check xEdit dirty state before stop or restart

Stopping a daemon with unsaved work is a real state boundary.
The MCP exposes dirty-state helpers so agents do not need to remember the raw daemon command each time.

Use `xedit_dirty` before lifecycle operations. On contract 0.23 its
`pendingShutdownSave` projection comes from authoritative daemon queue readback;
successful `session.save` observations remain as a fail-closed fallback when the
field is unavailable. Missing fields and failed probes do not clear the guard.

Let `xedit_stop` or `xedit_restart` refuse when unsaved edits, pending saves, or
an unavailable dirty-state probe make the boundary unsafe. Resolve a live pending
queue through `xedit_flush`. Force is an auditable abandonment, never a flush or
durability claim.

An unavailable probe returns `dirty_state_unavailable`. Retry `xedit_dirty`;
do not collapse that code into `dirty_state` or assume the session is clean.

This record is especially important after mutating jobs and header edits.
