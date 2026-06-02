---
id: fo4-quirks.settlement-attack-state-can-stale.v1
title: Settlement attack and defense state can stale across Fallout 4 saves
domains: [engine, save-file, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Settlement attack behavior is tied to workshop state, population, defense, and quest/script updates, so stale save state can outlive the mod or setting that triggered it.
  confidence: medium
queryKeys: [settlement attack bug, defend settlement, workshop quest, stale save]
severity: medium
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_settlements"
    ref: Fallout Wiki Fallout 4 settlements
related: [fo4-settlement.workshop-scripts-are-save-state.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Settlement attack and defense state can stale across Fallout 4 saves

Settlements track population, defense, resources, and workshop ownership in save state.
Attack/defense events can therefore be affected by stale state as well as current records.

When an attack trigger behaves oddly, inspect the settlement's current data and recent script/framework changes.
Do not assume the active plugin list alone explains the event state.
