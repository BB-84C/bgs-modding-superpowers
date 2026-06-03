---
id: load-order.xedit-cannot-change-load-order.v1
title: xEdit cannot change plugin load order; edit plugins.txt or use LOOT
domains: [load-order, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: xEdit can inspect plugin contents and headers, but activation and ordering live in load-order files or external sorters such as LOOT.
  confidence: verified-project-doc
queryKeys: [xEdit load order, reorder plugins, LOOT, plugins.txt edit]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Routing matrix
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# xEdit cannot change plugin load order; edit plugins.txt or use LOOT

The xEdit daemon operates on plugin files and records.
It is not the activation or sort owner for the user's load-order files.

For activation, deactivation, removal, and manual reordering, edit the appropriate `plugins.txt` / `loadorder.txt` surface.
For automatic sorting, route through LOOT rather than inventing an xEdit command.

This distinction prevents agents from asking the daemon to do work outside its domain.
