---
id: xedit.xedit-references-recursive.v1
title: xEdit r6 references can opt into recursive ChildGroup descendant union
domains: [xedit, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.15 adds supports.referencesRecursive; recursive:true unions outgoing references across ChildGroup descendants, deduplicates by FormID, and applies limit after the union. Leave recursive unset or false for the legacy direct-record reference shape.
  confidence: verified-project-doc
queryKeys: [supports.referencesRecursive, references recursive, recursive true, ChildGroup descendants, outgoing references, dedup by FormID, post-union limit]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / referencesRecursive
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.15 capability block
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 references can opt into recursive ChildGroup descendant union

Contract 0.15 adds `supports.referencesRecursive`.
When a references command supports `recursive:true`, it unions outgoing references from the record and its ChildGroup descendants.

## Agent rules

Results are deduplicated by FormID before return.
The `limit` applies after the recursive union, so a small limit can hide later descendant hits even though traversal succeeded.

Use this when a CELL, WRLD, DIAL, or QUST reference query appears incomplete because child records were not included by the non-recursive path.
