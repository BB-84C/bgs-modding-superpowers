---
id: xedit.error-mcp-mode-required.v1
title: mcp_mode_required means the daemon refused a non-MCP mutation path
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: mcp_mode_required is a safety refusal for direct or incorrectly routed mutating calls; recovery is to use the bundled MCP path with the required launch mode, not to bypass the harness.
  confidence: verified-project-doc
queryKeys: [mcp_mode_required, mcp mode, direct pipe refused, mutation gate]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/SKILL.md
    sectionPath: Do Not
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Error code reference
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# mcp_mode_required means the daemon refused a non-MCP mutation path

`mcp_mode_required` is not a bug to work around.
It is the daemon protecting mutating operations from direct, unaudited access.

The fix is to route through the xEdit MCP, preserve audit and permission checks, and ensure the daemon was launched in the expected MCP-aware mode.
If the operation is mutating, user consent and `-IKnowWhatImDoing` still apply.

Never respond to this code by spawning xEdit directly or writing plugin files with ad hoc scripts.
