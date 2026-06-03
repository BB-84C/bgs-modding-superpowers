---
id: load-order.esl-extension-vs-header-flag.v1
title: Light-plugin behavior comes from the header flag, not only the .esl extension
domains: [load-order, plugin-format]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [SkyrimLE, Fallout3, FalloutNV]
canonical:
  answer: A true `.esl` and an ESL-flagged `.esp` are both light-plugin cases for slot accounting, but the `.esp` filename does not by itself prove full-plugin behavior.
  confidence: verified-project-doc
queryKeys: [ESL flagged ESP, light plugin, .esl extension, FE slot, plugin header]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: ESL conversion
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
related: [load-order.esl-flag-lives-in-header.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Light-plugin behavior comes from the header flag, not only the .esl extension

Modern engines can treat an `.esp` as light when its plugin header carries the ESL flag.
The file extension is therefore not enough to decide slot accounting or FormID constraints.

Use xEdit header readback or an ESL analysis command to determine light status.
Do not rename files or edit `plugins.txt` as a substitute for setting or verifying the header flag.
