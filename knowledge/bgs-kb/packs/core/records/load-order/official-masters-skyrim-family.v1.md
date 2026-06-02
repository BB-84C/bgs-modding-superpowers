---
id: load-order.official-masters-skyrim-family.v1
title: Skyrim official masters start with the game and official update or DLC files
domains: [load-order]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
canonical:
  answer: Skyrim-family official masters are the engine-loaded game and official update or DLC files, with `Skyrim.esm` as the base anchor and runtime-installed official content loading before user-managed plugins.
  confidence: high
queryKeys: [Skyrim official masters, Skyrim.esm, Update.esm, Dawnguard.esm, HearthFires.esm, Dragonborn.esm]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Official / vanilla masters
  - kind: wiki
    url: "https://en.uesp.net/wiki/Skyrim:Files"
    ref: UESP Skyrim files
related: [load-order.official-masters-derived-from-runtime.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim official masters start with the game and official update or DLC files

For Skyrim targets, use `Skyrim.esm` as the base official-master anchor.
Official update and DLC masters such as `Update.esm`, `Dawnguard.esm`, `HearthFires.esm`, and `Dragonborn.esm` are also part of the vanilla/DLC layer when present in the runtime.

Skyrim SE, AE, and VR can add bundled official or Creation Club content, so do not treat the visible list as universal across machines.
When generating a `plugins.txt`, infer the official set from the managed runtime and keep user-managed plugins after it.
