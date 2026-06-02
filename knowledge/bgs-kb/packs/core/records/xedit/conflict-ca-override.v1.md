---
id: xedit.conflict-ca-override.v1
title: caOverride means an override without a detected conflict
domains: [xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: caOverride indicates a plugin intentionally overrides a master record while xEdit does not classify the change as a conflicting loser/winner situation.
  confidence: verified-tooling
queryKeys: [caOverride, override no conflict, yellow green, conflict verdict]
severity: low
sources:
  - kind: tooling-docs
    ref: xEdit Docs / Tome of xEdit
    url: https://tes5edit.github.io/docs/5-conflict-detection-and-resolution.html
    sectionPath: "5.2 Differences between Conflicts and Overrides"
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: Glossary
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# caOverride means an override without a detected conflict

Map `caOverride` to a non-breaking/no-conflict style MCP result unless field readback says otherwise.
xEdit's own guidance separates ordinary overrides from conflicts.

This does not mean the record is semantically desirable; it means the conflict algorithm is not flagging competing divergent overrides.
Agents should still report the winning file and user-visible field change when the user asks why behavior changed.

Do not clean `caOverride` records merely because they are overrides.
