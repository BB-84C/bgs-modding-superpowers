---
id: legacy-load-order.boss-advice-is-historical-not-current-default.v1
title: BOSS-era load-order advice should be checked against current LOOT and mod guidance
domains: [load-order, tooling.loot]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: BOSS is historically important load-order tooling, but its own public documentation now points users toward LOOT for maintained sorting behavior.
  confidence: verified-tooling
queryKeys: [BOSS, old load order sorter, LOOT replacement, legacy guide]
severity: medium
sources:
  - kind: tooling-docs
    ref: BOSS documentation landing page
    url: https://boss-developers.github.io/
    sectionPath: Maintenance status and LOOT recommendation
  - kind: tooling-docs
    ref: LOOT supported games
    url: https://loot.github.io/
    sectionPath: Supported games list
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# BOSS-era load-order advice should be checked against current LOOT and mod guidance

Older FO3/FNV mod guides may still mention BOSS-era sorting habits.
Before turning those habits into an agentic rule, compare them against current LOOT metadata and the mod's present documentation.

For TTW specifically, prefer current TTW guide guidance and live profile readback over generic historical sorter assumptions.
