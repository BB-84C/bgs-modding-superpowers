---
id: debugging.dirty-state-before-stop-restart.v1
title: Check xEdit dirty state before stop or restart
kind: rule-candidate
domains: [debugging, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Before stopping or restarting xEdit, agents should inspect both daemon dirty state and MCP-tracked pending-shutdown saves. A save can set dirty:false while its physical write remains queued; normal lifecycle operations must refuse either state.
  confidence: verified-project-doc
queryKeys: [xedit_dirty, session.get_dirty_state, pending shutdown save, unsaved changes, stop restart]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Dirty-state checks
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Check xEdit dirty state before stop or restart

Stopping a daemon with unsaved work is a real state boundary.
The MCP exposes dirty-state helpers so agents do not need to remember the raw daemon command each time.

Use `xedit_dirty` before lifecycle operations. Its `pendingShutdownSave` field is
local MCP state derived from successful `session.save` responses, not a daemon
dirty-state inference. Let `xedit_stop` or `xedit_restart` refuse when either
unsaved edits or pending saves exist unless `force:true` is explicitly chosen.
Force is an auditable abandonment, never a flush or durability claim.

This record is especially important after mutating jobs and header edits.
