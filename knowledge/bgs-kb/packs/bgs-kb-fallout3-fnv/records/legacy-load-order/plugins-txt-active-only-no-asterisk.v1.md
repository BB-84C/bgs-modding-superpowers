---
id: legacy-load-order.plugins-txt-active-only-no-asterisk.v1
title: Fallout 3 and New Vegas plugins.txt is active-only with no asterisk marker
domains: [load-order]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Fallout 3 and Fallout New Vegas use the legacy plugins.txt convention where entries are active plugins and no leading asterisk activation marker is used.
  confidence: verified-project-doc
queryKeys: [plugins.txt, no asterisk, active only, Fallout 3 load order, New Vegas load order]
severity: critical
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Legacy format
related: [load-order.plugins-txt-legacy.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 3 and New Vegas plugins.txt is active-only with no asterisk marker

Do not write modern `*Plugin.esp` activation lines for Fallout 3 or Fallout: New Vegas.
For these legacy targets, a plugin is active because it appears in `plugins.txt`.

Agents should cross-check this record with the core legacy load-order record before editing any FO3/FNV profile state.
