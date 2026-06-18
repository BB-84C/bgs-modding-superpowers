---
id: xedit.xedit-elements-children-pagination.v1
title: xEdit r6 elements.children is paginated and reports count metadata
domains: [xedit, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.17 adds supports.elementsChildrenPagination; elements.children accepts limit 1-1000 and offset, defaults to limit 200, and returns count, total, offset, and truncated. ChildGroup stubs are emitted only on the first page.
  confidence: verified-project-doc
queryKeys: [supports.elementsChildrenPagination, elements.children limit, elements.children offset, count total offset truncated, ChildGroup first page only, pagination]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / elementsChildrenPagination
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.17 capability block
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 elements.children is paginated and reports count metadata

Contract 0.17 adds `supports.elementsChildrenPagination`.
`elements.children` now accepts `limit` from 1 to 1000 and `offset`; the default limit is 200.

## Response contract

Read `count`, `total`, `offset`, and `truncated` to decide whether another page is needed.
Do not assume a short first response means the element has no more children.

ChildGroup stubs appear only on the first page, so clients that need the synthetic ChildGroup navigation entry must inspect `offset:0`.
