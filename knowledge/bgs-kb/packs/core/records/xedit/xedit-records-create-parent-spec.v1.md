---
id: xedit.xedit-records-create-parent-spec.v1
title: xEdit r6 records.create can author into a parent's ChildGroup
domains: [xedit, debugging, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.16/0.18 adds supports.createParentSpec; records.create can target a parent CELL, DIAL, QUST, or WRLD ChildGroup through a parent spec. WRLD can use subGroup:"Persistent" or coords:[X,Y], with Block/Sub-Block GRUPs auto-created as needed; master-add policy is unchanged.
  confidence: verified-project-doc
queryKeys: [supports.createParentSpec, records.create parent, parent spec, subGroup, WRLD coords, Block Sub-Block, Temporary heuristic, Persistent heuristic, master-add policy]
severity: high
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / createParentSpec
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.16 and 0.18 capability blocks
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 records.create can author into a parent's ChildGroup

Contract 0.16/0.18 adds `supports.createParentSpec`.
For `CELL`, `DIAL`, and `QUST`, use `parent:{file, formId, subGroup?}` to author into the parent's ChildGroup.

## WRLD parent shapes

For `WRLD`, use either `parent:{file, formId, subGroup:"Persistent"}` or `parent:{file, formId, coords:[X,Y]}`.
The coordinate path auto-creates the needed `Block X, Y` and `Sub-Block M, N` GRUPs.

## Default and master rules

If `subGroup` is omitted, `REFR`, `ACHR`, `PGRD`, `LAND`, and `NAVM` default to `Temporary`; other signatures default to `Persistent`.
The existing master-add policy does not change: creating into a parent does not bypass required master handling.
