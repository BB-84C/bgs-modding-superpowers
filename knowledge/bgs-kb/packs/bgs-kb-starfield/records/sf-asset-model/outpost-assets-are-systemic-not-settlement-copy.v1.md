---
id: sf-asset-model.outpost-assets-are-systemic-not-settlement-copy.v1
title: Starfield outpost assets are not just Fallout 4 settlement assets renamed
domains: [engine, file-conflicts, install-planning]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: Starfield outpost modules participate in Starfield-specific systems such as scanner placement, resources, production, cargo, crew, and power, so FO4 settlement asset assumptions need verification.
  confidence: high
queryKeys: [Starfield outpost modules, settlement assumptions, outpost assets]
severity: high
sources:
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Starfield:Outposts"
    ref: Starfield Wiki Outposts
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield outpost assets are not just Fallout 4 settlement assets renamed

Outpost modules have material costs and connect to power, cargo, crew, extraction, and production state.
They are part of Starfield's outpost system rather than a direct clone of Fallout 4 settlements.

When packaging outpost assets, verify Starfield paths and records.
Do not assume FO4 Workshop asset rules transfer unchanged.
