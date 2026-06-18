---
id: xedit.xedit-apply-filter-extensions.v1
title: xEdit r6 apply_filter adds parentFormId, regex fields, and bounded multi-pattern OR
domains: [xedit, debugging, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Contract 0.14/0.20 extends apply_filter with parentFormId, per-field regex filters, and scalar-or-array OR patterns capped at 32 values per field. Pattern and Regex variants are mutually exclusive per field, empty arrays are rejected, and regex pressure is reported by RegexSlotsExhausted.
  confidence: verified-project-doc
queryKeys: [supports.applyFilterExtensions, apply_filter parentFormId, parentFormId, RegexSlotsExhausted, apply_filter regex, scalar-or-array OR, empty array rejection, pattern vs regex]
severity: medium
sources:
  - kind: github-issue
    ref: BB-84C/bgs-modding-superpowers#4
    url: https://github.com/BB-84C/bgs-modding-superpowers/issues/4
    sectionPath: Issue body / applyFilterExtensions
  - kind: official
    ref: TES5Edit v4.1.6-automation.6 release
    url: https://github.com/BB-84C/TES5Edit/releases/tag/v4.1.6-automation.6
    sectionPath: r6 contract 0.14 and 0.20 capability blocks
lastReviewed: "2026-06-17"
schemaVersion: 1
---

# xEdit r6 apply_filter adds parentFormId, regex fields, and bounded multi-pattern OR

`supports.applyFilterExtensions` appears across contract 0.14 and 0.20.
`parentFormId` means the candidate record's ancestor chain contains that parent FormID, not that the record's direct ID equals the parent.

## Regex and pattern rules

The five `*Regex` fields use `System.RegularExpressions.TRegEx`, with a 100ms per-record timeout and a 4-worker semaphore.
Pattern-vs-Regex is exclusive per field: do not send both variants for the same field in one filter.

## Multi-pattern OR

Scalar fields may also be arrays for OR matching, with at most 32 patterns per field.
Empty arrays are invalid, and regex saturation is surfaced by the response counter `RegexSlotsExhausted`.
