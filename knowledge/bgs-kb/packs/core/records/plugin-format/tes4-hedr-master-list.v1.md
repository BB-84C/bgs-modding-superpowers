---
id: plugin-format.tes4-hedr-master-list.v1
title: TES4/HEDR header data owns plugin metadata and master indexing
domains: [plugin-format, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: The TES4 header record carries metadata such as flags, author/description, HEDR values, and the ordered MAST/DATA master list that FormID master indices resolve against.
  confidence: high
queryKeys: [TES4, HEDR, MAST, DATA, master list, next object id, header flags]
severity: critical
sources:
  - kind: wiki
    ref: UESP Skyrim Mod File Format / TES4
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format/TES4
    sectionPath: HEDR; MAST / DATA
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: files.*
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# TES4/HEDR header data owns plugin metadata and master indexing

The TES4 header is where plugin-level metadata lives.
HEDR includes version-style header data, record/group count, and next available object ID in the Skyrim-format source.

The MAST/DATA pairs form an ordered master list.
That order matters because FormID master-index bits are interpreted relative to the saved master list.

When xEdit changes masters or header flags, verify with `files.get_header` and `files.get_masters`, not just a successful mutation envelope.
