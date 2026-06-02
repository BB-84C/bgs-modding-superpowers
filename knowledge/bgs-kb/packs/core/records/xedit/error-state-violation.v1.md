---
id: xedit.error-state-violation.v1
title: state_violation means the MCP lifecycle state is wrong for the call
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "state_violation is an MCP-layer lifecycle refusal: the requested tool needs a ready daemon, a clean state, or an allowed transition that is not currently true."
  confidence: verified-project-doc
queryKeys: [state_violation, lifecycle state, daemon not ready, xedit_status]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Error code reference
  - kind: project-skill
    ref: skills/using-bgs-modding-superpowers/SKILL.md
    sectionPath: Canonical lifecycle pattern
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# state_violation means the MCP lifecycle state is wrong for the call

Treat `state_violation` as a harness-state problem, not as evidence about a plugin record.
The most common recovery is to check `xedit_status`, wait for `ready`, or route through the lifecycle tool that performs the transition.

Do not hammer domain tools hoping they will block until ready.
The MCP is non-blocking by design and domain tools fast-fail when the lifecycle state is unsuitable.

If dirty state is involved, inspect `xedit_dirty` before stop or restart.
