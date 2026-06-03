---
id: load-order.plugins-txt-modern-asterisk.v1
title: Modern BGS plugins.txt uses leading asterisk to mark active plugins
domains: [load-order]
appliesTo:
  games: [SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [SkyrimLE, Fallout3, FalloutNV]
canonical:
  answer: Modern Bethesda plugins.txt files keep active and inactive plugin entries together, using a leading asterisk to mark active plugins while preserving inactive positions without the prefix.
  confidence: verified-project-doc
queryKeys: [plugins.txt asterisk, active plugin, modern load order, MO2 plugins.txt]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Asterisk format reference
related: [load-order.plugins-txt-legacy.v1]
seeAlso: [xedit.files-list-object-shape.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Modern BGS plugins.txt uses leading asterisk to mark active plugins

For Skyrim Special Edition and later Creation Engine targets, `plugins.txt` is both an ordering surface and an activation surface.
A leading `*` means active; no prefix means the plugin is tracked but inactive.

Top lines load earlier and bottom lines win later conflicts, after the game has already handled its official masters.
Agents should toggle activation by changing the prefix, not by asking xEdit to activate a plugin.

This does not apply to Skyrim LE, Fallout 3, or Fallout New Vegas, which use the legacy active-only format.
