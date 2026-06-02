---
id: fo4-settlement.settlement-size-budget-is-gameplay-limit.v1
title: Fallout 4 settlement size budget is a gameplay and performance limit
domains: [engine, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Settlement build limits are there to bound object counts and performance, so budget bypasses can create stability and rendering problems even if the workshop accepts the objects.
  confidence: high
queryKeys: [settlement size limit, build budget, workshop budget, scrap exploit]
severity: high
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_settlements"
    ref: Fallout Wiki Fallout 4 settlements
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 settlement size budget is a gameplay and performance limit

Settlement budgets constrain how many placed objects the workshop expects in an area.
Bypassing the limit can work in the short term but increases save, AI, draw, and physics pressure.

When diagnosing a settlement that stutters or fails to load cleanly, inspect object density before blaming plugin order.
Scrap-budget changes are modlist design decisions, not harmless quality-of-life toggles.
