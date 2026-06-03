---
id: plugin-format.create-record-header-side-effects.v1
title: Creating records can require header next-object and master-list follow-up
domains: [plugin-format, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: "records.create is not just a new record body: tools must preserve header invariants such as next object ID and required masters, then prove the new record survives save and reload."
  confidence: verified-project-doc
queryKeys: [records.create, next object id, HEDR, create record, required masters]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: records.* commands
  - kind: wiki
    ref: UESP Skyrim Mod File Format / TES4
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format/TES4
    sectionPath: HEDR
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Creating records can require header next-object and master-list follow-up

`records.create` produces a new major record, but the file-level invariants still matter.
The header tracks next available object ID in the Skyrim-format reference, and any copied or linked data may require masters.

After creation, read the record by FormID or EditorID and inspect the file header if the operation should have advanced header state.
If the record references external plugins, confirm the required masters list before saving.

The semantic proof is create, save, restart if pending, and read back the record plus relevant header/master state.
