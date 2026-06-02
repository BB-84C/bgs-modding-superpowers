---
id: plugin-format.onam-overridden-cell-children.v1
title: ONAM lists overridden cell-child forms in master-flagged plugins
domains: [plugin-format, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: ONAM is a TES4-header subrecord used by master-flagged plugins to list overridden cell-child forms, making it a header-level side effect to preserve when rebuilding masters or compacting plugins.
  confidence: high
queryKeys: [ONAM, overridden forms, cell children, ACHR, LAND, NAVM, REFR]
severity: high
sources:
  - kind: wiki
    ref: UESP Skyrim Mod File Format / TES4
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format/TES4
    sectionPath: ONAM (Overridden forms)
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ONAM lists overridden cell-child forms in master-flagged plugins

ONAM is not a normal gameplay record; it is header-side metadata.
The Skyrim-format reference describes it as an array of overridden cell-child FormIDs, present in ESM-flagged files that override masters' cell children.

Agents should treat ONAM as a preservation concern during header edits, master cleanup, and plugin conversion.
If a tool rebuilds masters or compacts FormIDs, re-read the header and confirm ONAM-sensitive overrides were not lost.

For non-Skyrim games, verify with the active tooling before assuming identical field layout.
