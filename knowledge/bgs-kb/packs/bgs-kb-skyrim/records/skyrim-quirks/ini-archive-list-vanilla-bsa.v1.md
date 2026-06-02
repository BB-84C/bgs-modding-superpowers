---
id: skyrim-quirks.ini-archive-list-vanilla-bsa.v1
title: Skyrim.ini archive lists affect vanilla BSA visibility to tools and runtime
domains: [archive-precedence, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "STEP documents Skyrim.ini Archive entries needed for vanilla BSA visibility; missing archive lists can make tools and runtime miss official assets."
  confidence: high
queryKeys: [Skyrim.ini Archive, sResourceArchiveList, vanilla BSA, Esbern voice]
severity: high
sources:
  - kind: wiki
    ref: STEP Skyrim Configuration Settings
    url: https://stepmodifications.org/wiki/Guide:Skyrim_Configuration_Settings
    sectionPath: Recommended changes > Skyrim INI > Archive
related: [archive-precedence.ini-archive-list-per-game.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim.ini archive lists affect vanilla BSA visibility to tools and runtime

Archive-list problems can look like missing voice, mesh, texture, or xEdit visibility problems.
STEP documents required vanilla Skyrim archive list values when launcher-generated INIs are missing them.

Before blaming a mod, check whether the profile INIs load the official BSAs correctly.
This is especially relevant for portable MO2 profiles and copied INI templates.

Do not hardcode another user's archive list without checking edition and installed content.
