---
id: geck-scripting.formlist-editing-uses-drag-drop-membership.v1
title: GECK FormList editing changes list membership, not the listed forms
domains: [engine, plugin-format]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: GECK FormLists are edited by adding/removing member forms from the list; removing an entry from the list does not delete the underlying object record.
  confidence: high
queryKeys: [FormList, formlist membership, drag drop, list edit]
severity: medium
sources:
  - kind: wiki
    ref: GECK Wiki FormList
    url: https://geckwiki.com/index.php?title=FormList
    sectionPath: Editing Form Lists
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# GECK FormList editing changes list membership, not the listed forms

FormLists collect references to other forms for categories such as recipes, repair lists, residents, or item groups.
In the GECK interface, membership is managed by dragging objects into the list and deleting list entries.

For conflict review, treat list-member changes as list semantics.
They are not the same as deleting or replacing the underlying form record itself.
