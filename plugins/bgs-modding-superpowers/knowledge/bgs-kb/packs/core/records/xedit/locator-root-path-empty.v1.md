---
id: xedit.locator-root-path-empty.v1
title: Root xEdit record locators use file, formId, and an empty path
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: A root record locator names the plugin file and load-order-resolved FormID, with path set to an empty string; nested element addressing extends path from that root.
  confidence: verified-project-doc
queryKeys: [record locator, root locator, path empty, formId path]
severity: medium
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Locator shape
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Root xEdit record locators use file, formId, and an empty path

The common locator shape is a plugin `file`, a load-order-resolved `formId`, and `path: ""` for the record root.
Element-level operations extend the path from there.

Agents should not omit `path` if a native command expects the full locator shape.
An empty string is a deliberate root marker, not missing data.

This convention makes record and element operations composable across daemon commands.
