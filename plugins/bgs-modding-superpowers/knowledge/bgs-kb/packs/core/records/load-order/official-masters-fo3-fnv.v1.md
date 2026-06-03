---
id: load-order.official-masters-fo3-fnv.v1
title: Fallout 3 and New Vegas official masters are legacy-era base and DLC ESMs
domains: [load-order]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
canonical:
  answer: Fallout 3 and Fallout New Vegas use legacy load-order handling, with the base game ESM and installed official DLC ESMs forming the official layer before user plugins.
  confidence: high
queryKeys: [Fallout 3 official masters, FalloutNV.esm, Fallout3.esm, DeadMoney.esm, BrokenSteel.esm]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Legacy format
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_3"
    ref: Independent Fallout Wiki Fallout 3
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout:_New_Vegas"
    ref: Independent Fallout Wiki Fallout New Vegas
related: [load-order.plugins-txt-legacy.v1, load-order.official-masters-derived-from-runtime.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 3 and New Vegas official masters are legacy-era base and DLC ESMs

Fallout 3 anchors on `Fallout3.esm`; New Vegas anchors on `FalloutNV.esm`.
Installed official DLC masters belong to the same low, immutable official layer for that runtime.

Because these games use the legacy `plugins.txt` plus `loadorder.txt` split, do not import modern asterisk-format assumptions when representing active state.
Use the actual game installation and xEdit readback to decide which official DLC masters are present.
