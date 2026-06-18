---
id: xedit.xedit-r6-contract-summary.v1
title: TES5Edit automation r6 bumps contract support from 0.12 to 0.20 with eight additive blocks
domains: [xedit, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: TES5Edit v4.1.6-automation.6, commit 4a2304b5, is the r6 additive capability release that moves the automation contract from 0.12 to 0.20. The eight new supports.* blocks cover ChildGroup navigation, apply_filter extensions, recursive references, ChildGroup conflict status, parent-spec creation, children pagination, reverse navigation, and the final 0.20 filter refinements.
  confidence: verified-project-doc
queryKeys: [v4.1.6-automation.6, 4a2304b5, r6 contract, contract 0.20, supports.childGroupNavigation, supports.applyFilterExtensions, supports.referencesRecursive, supports.conflictStatusChildGroup, supports.createParentSpec, supports.elementsChildrenPagination, supports.reverseNavigation]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / r6-contract-summary
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: Release tag and commit 4a2304b5
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# TES5Edit automation r6 bumps contract support from 0.12 to 0.20 with eight additive blocks

Release `v4.1.6-automation.6` at commit `4a2304b5` is the r6 automation contract release.
It is strictly additive: existing 0.12 clients should continue to rely on field-presence checks while newer clients can detect the new `supports.*` keys.

## Capability map

- 0.13: `supports.childGroupNavigation`
- 0.14: `supports.applyFilterExtensions`
- 0.15: `supports.referencesRecursive` and `supports.conflictStatusChildGroup`
- 0.16 and 0.18: `supports.createParentSpec`
- 0.17: `supports.elementsChildrenPagination`
- 0.19: `supports.reverseNavigation`
- 0.20: final `supports.applyFilterExtensions` refinements for regex and multi-pattern OR

Use the dedicated r6 records for per-command argument and response-shape details.
