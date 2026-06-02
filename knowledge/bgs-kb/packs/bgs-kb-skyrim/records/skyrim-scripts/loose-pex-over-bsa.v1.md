---
id: skyrim-scripts.loose-pex-over-bsa.v1
title: Loose Skyrim PEX files can override archived scripts
domains: [papyrus, archive-precedence, file-conflicts]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim script conflicts are asset conflicts too: a loose Scripts/*.pex file can override the archived compiled script that a plugin expects."
  confidence: verified-project-doc
queryKeys: [PEX loose file, Scripts BSA, script overwrite, loose over archive]
severity: high
sources:
  - kind: project-internal-doc
    ref: knowledge/bgs-kb/packs/core/records/archive-precedence/loose-over-archive.v1.md
    sectionPath: Loose files override archived assets at runtime
  - kind: wiki
    ref: STEP Skyrim INI Archive settings
    url: https://stepmodifications.org/wiki/Guide:Skyrim_Configuration_Settings
    sectionPath: Skyrim.ini Archive
related: [archive-precedence.loose-over-archive.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Loose Skyrim PEX files can override archived scripts

Do not diagnose Skyrim Papyrus only from ESP conflicts.
The compiled script asset can be loose under `Scripts/` or packaged inside a BSA.

When a mod update ships a replacement `.pex`, MO2's file-conflict view may explain the behavior better than xEdit.
Check both the winning plugin record and the winning compiled script file.

This is especially important for patches that replace vanilla or framework scripts.
