---
id: xedit.files-list-object-shape.v1
title: files.list returns objects, not strings
domains: [xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: files.list returns file metadata objects such as name, loadOrder, fileName, isESM, and isLight; callers must extract the canonical plugin name instead of treating the response as string[].
  confidence: verified-project-doc
queryKeys: [files.list, load order objects, plugin metadata, isESM, isLight]
severity: medium
sources:
  - kind: project-internal-doc
    ref: docs/internal/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
    sectionPath: What was learned
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# files.list returns objects, not strings

The daemon's file list is a structured metadata array, not a bare list of plugin names.
Each entry can carry fields such as `name`, `loadOrder`, `fileName`, `isESM`, and `isLight`.

An agent or MCP adapter should extract the canonical name deliberately and keep the rest of the metadata available for checks.
String-only assumptions lose useful state and can break when the daemon returns the richer shape.

Use this record when implementing load-order visibility or LOAD001-style active-file checks.
