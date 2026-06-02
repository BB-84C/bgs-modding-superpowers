---
id: xedit.referenced-by-before-delete.v1
title: Call referenced_by before deleting or mark-deleting records
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: records.referenced_by is the safety readback before destructive record changes; references can survive the edit and become broken unless they are audited first.
  confidence: verified-project-doc
queryKeys: [records.referenced_by, xref, references, delete record, mark_deleted]
severity: critical
sources:
  - kind: project-skill
    ref: skills/xedit-automation/SKILL.md
    sectionPath: Do Not
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: records.* commands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Call referenced_by before deleting or mark-deleting records

`records.references` asks what the target record points to; `records.referenced_by` asks what points at the target.
For destructive operations, the second question is the important safety check.

Snapshot or save/reload proof does not magically repair referencers.
If the daemon reports referencers, the agent must surface them before deleting, mark-deleting, or replacing the record.

Treat the referenced-by list as part of the acceptance artifact for any destructive workflow.
