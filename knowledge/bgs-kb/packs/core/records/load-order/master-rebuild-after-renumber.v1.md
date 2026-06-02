---
id: load-order.master-rebuild-after-renumber.v1
title: After FormID renumbering, update plugin masters through xEdit rather than load-order edits
domains: [load-order, plugin-format, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: FormID renumbering and required-master updates are plugin-header/content operations; use xEdit master-management commands instead of trying to repair dependencies by moving lines in plugins.txt.
  confidence: verified-project-doc
queryKeys: [FormID renumber, add master, files.add_required_masters, missing master, compact plugin]
severity: critical
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Routing matrix
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: files.add_required_masters
seeAlso: [load-order.load-order-validation-combines-file-and-header-checks.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# After FormID renumbering, update plugin masters through xEdit rather than load-order edits

Renumbering records or compacting a plugin can change what other files need to reference.
The load-order file can place plugins, but it cannot rebuild a plugin's master list or repair header dependencies.

Use xEdit master-management operations, such as adding required masters, then verify with header readback.
If a plugin fails because a required master is missing, fix the dependency surface before blaming sort order.
