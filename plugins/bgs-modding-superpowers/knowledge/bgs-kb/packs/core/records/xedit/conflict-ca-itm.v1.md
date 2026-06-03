---
id: xedit.conflict-ca-itm.v1
title: caITM means the override is identical to its master
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "caITM is xEdit's Identical To Master condition: an override record exists, but its contents match the master it overrides, so the override is usually redundant cleaning noise."
  confidence: verified-tooling
queryKeys: [caITM, ITM, identical to master, dirty edit, conflict verdict]
severity: medium
sources:
  - kind: tooling-docs
    ref: xEdit Docs / Tome of xEdit
    url: https://tes5edit.github.io/docs/5-conflict-detection-and-resolution.html
    sectionPath: "5.5 Color Schemes and Display Order"
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Glossary
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# caITM means the override is identical to its master

Map `caITM` to the MCP verdict `itm`, not to a generic breaking conflict.
xEdit treats this as an override whose data is the same as the master record.

The practical response is cleaning or ignoring it after context review, not conflict patching.
It can still matter if the user intentionally keeps an override as a placeholder, so agents should describe it as redundant rather than automatically deleting it.

Use readback against the base record and override before claiming it is safe to remove.
