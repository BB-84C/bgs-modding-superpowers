---
id: xedit.xedit-childgroup-navigation.v1
title: xEdit r6 exposes CELL, WRLD, DIAL, and QUST ChildGroups as read-only stubs
domains: [xedit, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.13 adds supports.childGroupNavigation; elements.children can return virtual kind:"child_group" stubs for CELL, WRLD, DIAL, and QUST ChildGroup siblings. Those synthetic paths are read-only navigation aids, so mutation verbs still need flat FormID locators.
  confidence: verified-project-doc
queryKeys: [supports.childGroupNavigation, child_group stub, Child Group locator, "\\Child Group", CELL child group, WRLD child group, DIAL child group, QUST child group]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / childGroupNavigation
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.13 capability block
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 exposes CELL, WRLD, DIAL, and QUST ChildGroups as read-only stubs

Contract 0.13 adds `supports.childGroupNavigation` for `elements.children` traversal.
For `CELL`, `WRLD`, `DIAL`, and `QUST`, the daemon may expose the ChildGroup sibling as a virtual `kind:"child_group"` stub.

## Locator vocabulary

Use ShortName-aligned labels under `\Child Group`: `\Child Group\Persistent`, `\Child Group\Temporary`, `\Child Group\Visible when Distant`, `\Child Group\Block X, Y`, and `\Child Group\Block X, Y\Sub-Block M, N`.
The `Visible when Distant` label uses lowercase `when`.

## Read-vs-write asymmetry

Synthetic ChildGroup paths are for read navigation only.
For `records.copy_into`, `records.delete`, and other mutation verbs, locate the real target with flat FormID locators instead of writing through the synthetic path.
