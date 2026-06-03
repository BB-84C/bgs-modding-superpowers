---
id: load-order.esl-flag-lives-in-header.v1
title: ESL conversion changes the plugin header, not plugins.txt
domains: [load-order, plugin-format, xedit]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [SkyrimLE, Fallout3, FalloutNV]
canonical:
  answer: Light-plugin conversion is a plugin-header operation; activating or reordering plugins.txt does not set the ESL flag.
  confidence: verified-project-doc
queryKeys: [ESL flag, light plugin, plugin.esl.analyze, plugin.esl.apply, header flag]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: ESL conversion
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: jobs.* commands
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# ESL conversion changes the plugin header, not plugins.txt

The load-order file decides whether a plugin is active and where it loads.
It does not decide whether an ESP is light-flagged.

Analyze ESL suitability through xEdit, then apply the light flag through the daemon when the verdict permits it.
The extension may remain `.esp`; the flag is what changes engine slot behavior.

Legacy Skyrim LE, Fallout 3, and Fallout New Vegas do not use this modern ESL workflow.
