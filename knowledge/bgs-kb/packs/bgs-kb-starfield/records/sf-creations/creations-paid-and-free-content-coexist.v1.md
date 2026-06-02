---
id: sf-creations.creations-paid-and-free-content-coexist.v1
title: Starfield Creations can include both free and paid content
domains: [install-planning, version-differences]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: The Starfield Creations listing shows both zero-cost entries and entries with a listed Creations cost, so modlist instructions must distinguish free content from paid Creations requirements.
  confidence: verified-official
queryKeys: [paid Creations, Starfield Creations cost, BethesdaGameStudios creations]
severity: medium
sources:
  - kind: official
    url: "https://creations.bethesda.net/en/starfield/all"
    ref: Bethesda Creations Starfield listing
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Starfield:DLC#Official_Creations"
    ref: Starfield Wiki Official Creations
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield Creations can include both free and paid content

The Bethesda Creations listing includes zero-cost Bethesda Game Studios entries and a paid Trackers Alliance bounty bundle entry.
Starfield Wiki's DLC page also separates official DLC from Official Creations.

When a modlist requires a Creation, specify whether it is free, paid, bundled, or optional.
Do not hide paid-content assumptions inside a generic “install Creations” step.
