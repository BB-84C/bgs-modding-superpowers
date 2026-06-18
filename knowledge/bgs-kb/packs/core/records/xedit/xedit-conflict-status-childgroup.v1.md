---
id: xedit.xedit-conflict-status-childgroup.v1
title: xEdit r6 conflict_status can include ChildGroup conflict summaries
domains: [xedit, debugging, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.15 adds supports.conflictStatusChildGroup; records.conflict_status may include result.childGroup with per-signature total/conflicting counts and up to 20 conflictingHits. The childGroup block is omitted when the ChildGroup is empty.
  confidence: verified-project-doc
queryKeys: [supports.conflictStatusChildGroup, result.childGroup, conflict_status child group, conflictingHits, per-signature conflict, total conflicting]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / conflictStatusChildGroup
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.15 capability block
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 conflict_status can include ChildGroup conflict summaries

Contract 0.15 adds `supports.conflictStatusChildGroup`.
For records with ChildGroups, `records.conflict_status` may include `result.childGroup` in addition to the existing record-level conflict data.

## Result shape

The ChildGroup summary is grouped by record signature, with `{total, conflicting}` counts per signature.
`conflictingHits` is capped at 20 examples.

If `result.childGroup` is missing, first check whether the ChildGroup is empty before treating the response as an incompatible daemon.
