---
id: fo4-quirks.power-armor-frame-state-is-persistent.v1
title: Power Armor frame state is persistent gameplay data in Fallout 4
domains: [engine, save-file, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Power Armor frames combine placed references, equipped parts, fusion-core state, and actor interaction, so frame bugs often involve persistent save state rather than a single item record.
  confidence: high
queryKeys: [Power Armor frame, fusion core, stuck power armor, persistent frame]
severity: medium
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Power_armor_(Fallout_4)"
    ref: Fallout Wiki Power armor Fallout 4
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Power Armor frame state is persistent gameplay data in Fallout 4

Fallout 4 power armor is built from a frame, armor pieces, and a fusion core-driven interaction model.
Once placed, entered, modified, or abandoned, a frame can become part of the save's persistent world state.

When diagnosing frame oddities, check the specific placed frame and current save context.
Do not assume replacing an armor-piece record will repair every stuck frame.
