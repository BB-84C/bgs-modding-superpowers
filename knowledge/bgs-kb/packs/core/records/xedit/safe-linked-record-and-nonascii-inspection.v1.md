---
id: xedit.safe-linked-record-and-nonascii-inspection.v1
title: Inspect linked-record identity and avoid raw non-ASCII Pascal comparisons
kind: gotcha
domains: [xedit, plugin-format, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: In xEdit automation scripts, inspect a link through LinksTo and compare a stable identifier such as EditorID instead of comparing a non-ASCII display value directly. For nested arrays, walk below the struct wrapper before declaring a link absent, then verify the linked record's owner and signature.
  confidence: verified-project-doc
queryKeys: [xEdit LinksTo, EditorID linked record, non-ASCII Pascal comparison, struct array INDX, element children]
severity: high
sources:
  - kind: github-issue
    url: "https://github.com/BB-84C/bgs-modding-superpowers/issues/27"
    ref: "Issue #27: xEdit Pascal inspection traps"
    sectionPath: "Part 6 — Wrong turns, non-ASCII edit values and elements.children struct arrays"
related:
  - plugin-format.xedit-mojibake-cp1252-default.v1
  - xedit.foreign-formid-local-space-resolution.v1
  - xedit.scripts-constrained-runtime.v1
lastReviewed: "2026-08-02"
schemaVersion: 1
---

# Inspect linked-record identity and avoid raw non-ASCII Pascal comparisons

In the observed automation runtime, a non-ASCII Pascal string literal and the value returned by `GetEditValue` did not compare equal even when the visible text described the same value. Do not use that comparison as a verification gate. Resolve the link with `LinksTo(element)` and compare a stable identifier such as `EditorID` instead; also verify the linked record's signature and owning file when identity matters.

Nested arrays need the same discipline. `elements.children` can display a struct-array wrapper as a bare `INDX` with an empty value, which can look like an empty array. Walk into the struct and its linked child before declaring a reference missing.

This is script-level inspection guidance, not a replacement for the broader plugin-string encoding policy. See `plugin-format.xedit-mojibake-cp1252-default.v1` when the issue is how xEdit reads or writes inline translated strings.
