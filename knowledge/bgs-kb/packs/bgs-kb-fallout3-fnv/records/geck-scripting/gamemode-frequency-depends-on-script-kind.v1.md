---
id: geck-scripting.gamemode-frequency-depends-on-script-kind.v1
title: GameMode frequency differs between quest and object/effect scripts
domains: [engine, debugging]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: In GECK scripting, GameMode on quest scripts runs on the quest processing delay, while object and effect scripts can run every rendered frame.
  confidence: high
queryKeys: [GameMode, script processing delay, quest script, object script, effect script]
severity: high
sources:
  - kind: wiki
    ref: GECK Wiki GameMode
    url: https://geckwiki.com/index.php?title=GameMode
    sectionPath: Execution frequency
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# GameMode frequency differs between quest and object/effect scripts

GECK `GameMode` is not a single fixed-rate callback.
Quest scripts use their configured processing delay, while object and effect scripts can evaluate once per rendered frame.

Avoid expensive polling in high-frequency blocks.
If a condition only needs periodic evaluation, prefer a quest-script cadence or add explicit timers instead of doing retrieval work every frame.
