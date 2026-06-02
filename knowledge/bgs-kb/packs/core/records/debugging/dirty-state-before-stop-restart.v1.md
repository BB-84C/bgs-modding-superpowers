---
id: debugging.dirty-state-before-stop-restart.v1
title: Check xEdit dirty state before stop or restart
kind: rule-candidate
domains: [debugging, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Before stopping or restarting xEdit, agents should check dirty state so unsaved plugin edits are surfaced rather than silently abandoned.
  confidence: verified-project-doc
queryKeys: [xedit_dirty, session.get_dirty_state, unsaved changes, stop restart]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Dirty-state checks
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Check xEdit dirty state before stop or restart

Stopping a daemon with unsaved work is a real state boundary.
The MCP exposes dirty-state helpers so agents do not need to remember the raw daemon command each time.

Use `xedit_dirty` before lifecycle operations, and let `xedit_stop` or `xedit_restart` refuse when unsaved edits exist unless force is explicitly chosen.
That keeps save decisions visible instead of hidden in cleanup code.

This record is especially important after mutating jobs and header edits.
