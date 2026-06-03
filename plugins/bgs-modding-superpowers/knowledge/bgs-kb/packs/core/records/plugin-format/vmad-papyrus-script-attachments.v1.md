---
id: plugin-format.vmad-papyrus-script-attachments.v1
title: VMAD stores Papyrus script attachments and properties
domains: [plugin-format, xedit, papyrus]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: VMAD is the plugin field that stores Papyrus script attachments, initial property values, and script-fragment metadata for records that carry scripts.
  confidence: high
queryKeys: [VMAD, Papyrus script data, script attachments, properties, fragments]
severity: high
sources:
  - kind: wiki
    ref: UESP Skyrim Mod File Format / VMAD Field
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format/VMAD_Field
    sectionPath: Primary Scripts Section
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# VMAD stores Papyrus script attachments and properties

VMAD is where plugin data connects records to Papyrus scripts.
The Skyrim-format reference describes direct script names, property values, and optional fragment sections with record-type-specific layouts.

This field is sequential and variable-length, so agents should avoid partial, ad hoc parsing.
Use xEdit, Mutagen, or another real parser when inspecting or changing VMAD.

Do not apply this to Fallout 3 or Fallout New Vegas; they use the older GECK scripting model, not Papyrus VMAD data.
