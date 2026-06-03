---
id: xedit.contract-version-field-presence.v1
title: xEdit automation clients should branch on fields, not contract version strings
domains: [xedit, debugging, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The xEdit automation contract version can drift between source and docs, so clients should prefer field-presence checks over branching on the exact version string.
  confidence: verified-project-doc
queryKeys: [contract version, version drift, field presence, "0.10", "0.9"]
severity: medium
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Daemon protocol essentials
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Known drift
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit automation clients should branch on fields, not contract version strings

The docs and fork source have disagreed on the displayed contract version string.
That mismatch is not itself a semantic failure if the fields an MCP tool needs are present.

Adapters should detect support from response shape and capability fields rather than hard-failing on one exact string.
Version strings still belong in diagnostics and drift reports.

Use this record when deciding whether a daemon is incompatible or merely reporting a stale label.
