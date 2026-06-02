---
id: engine.gamebryo-lineage-fo3-fnv.v1
title: Fallout 3 and New Vegas sit on the older Gamebryo-era toolchain
domains: [engine, version-differences, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: Fallout 3 and Fallout New Vegas workflows are closer to Gamebryo-era GECK modding than to modern Skyrim or Fallout 4 assumptions, especially around load-order format, script extender expectations, and missing ESL support.
  confidence: high
queryKeys: [Gamebryo, Fallout 3 engine, New Vegas engine, GECK, legacy modding]
severity: high
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_3"
    ref: Independent Fallout Wiki Fallout 3
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout:_New_Vegas"
    ref: Independent Fallout Wiki Fallout New Vegas
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Legacy format
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 3 and New Vegas sit on the older Gamebryo-era toolchain

FO3 and FNV should be treated as legacy-engine targets when moving between modding communities.
They use GECK-era workflows and the legacy active-only `plugins.txt` plus `loadorder.txt` split.

Do not import Skyrim SE or Fallout 4 assumptions about ESL/light plugins, Papyrus, or modern archive behavior without a game-specific check.
For agents, this record is a routing warning: old Fallout often needs old-engine answers.
