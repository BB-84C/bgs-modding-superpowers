---
id: xedit.xedit-reverse-navigation.v1
title: xEdit r6 can include nearest-first parent relations on read commands
domains: [xedit, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.19 adds supports.reverseNavigation; includeParents:true can attach relations.parents to record and element reads. Parents are nearest-first, carry locator/object pairs, and stop at depth 16.
  confidence: verified-project-doc
queryKeys: [supports.reverseNavigation, includeParents, relations.parents, nearest-first parents, records.get includeParents, elements.children includeParents, depth cap 16]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / reverseNavigation
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.19 capability block
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 can include nearest-first parent relations on read commands

Contract 0.19 adds `supports.reverseNavigation`.
Set `includeParents:true` when the caller needs reverse navigation from an element or record back toward its owning containers.

## Covered commands

The option applies to `records.get`, `records.find_by_form_id`, `records.find_by_editor_id`, `records.master_or_self`, `records.winning_override`, `elements.get`, and `elements.children`.

`relations.parents` is emitted as `[{locator, object}, ...]`, nearest-first, with a depth cap of 16.
