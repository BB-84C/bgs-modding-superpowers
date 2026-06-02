---
id: skyrim-versions.form43-form44-record-version.v1
title: Skyrim LE records use internal version 43 and SE records use 44
domains: [plugin-format, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "UESP documents Skyrim LE record internal version 43 and Skyrim SE record internal version 44, so LE plugins should not be blindly treated as native SE files."
  confidence: high
queryKeys: [Form 43, Form 44, Skyrim LE plugin, Skyrim SE plugin]
severity: high
sources:
  - kind: wiki
    ref: UESP Skyrim Mod File Format
    url: https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format
    sectionPath: Records
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim LE records use internal version 43 and SE records use 44

Form 43 vs Form 44 is a plugin-format clue, not just folklore.
UESP's Skyrim file-format page lists record internal version 43 for LE and 44 for SE.

For SE/AE/VR modpacks, flag LE plugins for conversion review.
Do not auto-convert blindly; check the plugin, assets, and author notes.

Runtime proof comes from xEdit/CK readback, not from filename alone.
