---
id: load-order.plugins-txt-vs-modlist.v1
title: plugins.txt lists plugin activation while modlist.txt lists MO2 mod folders
domains: [load-order, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: In MO2 profiles, plugins.txt controls plugin-file activation and load order, while modlist.txt controls enabled mod folders; their prefix meanings are different.
  confidence: verified-project-doc
queryKeys: [plugins.txt, modlist.txt, MO2 profile, foreign mod, active plugin]
severity: critical
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: plugins.txt vs modlist.txt
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# plugins.txt lists plugin activation while modlist.txt lists MO2 mod folders

`plugins.txt` is about `.esp`, `.esm`, and `.esl` plugin files.
`modlist.txt` is about MO2 mod folders under `mods/`.

The prefix conventions are not interchangeable: a `*` in modern `plugins.txt` means active plugin, while a `*` in MO2 `modlist.txt` indicates a foreign mod.
Copying lines or prefix logic between the two files can corrupt profile reasoning.

Agents should inspect the right surface for the question being asked.
