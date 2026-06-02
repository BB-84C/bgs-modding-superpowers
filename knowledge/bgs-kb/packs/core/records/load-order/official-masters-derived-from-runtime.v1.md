---
id: load-order.official-masters-derived-from-runtime.v1
title: Official masters are derived from the current runtime, not hardcoded lists
domains: [load-order, xedit]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Agents should infer official masters from the actual target runtime and earliest xEdit-loaded files instead of hardcoding a static per-game master list.
  confidence: verified-project-doc
queryKeys: [official masters, vanilla masters, files.list, game root Data]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Official / vanilla masters
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Official masters are derived from the current runtime, not hardcoded lists

Official master sets vary by game, DLC, installed content, and managed runtime.
A static list in an agent workflow will eventually miss a local fact.

The safer path is to inspect MO2's game configuration, then use xEdit `files.list` or the managed Data root to identify the earliest official files.
Those files load before user-managed plugin entries and should not be reordered by an agent-authored `plugins.txt`.

Use this record whenever a generated load order needs to decide what to omit or treat as immutable.
