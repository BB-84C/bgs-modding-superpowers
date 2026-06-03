---
id: engine.frame-budget-script-throttling.v1
title: fUpdateBudgetMS-style settings throttle script work by frame budget
domains: [engine, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Starfield]
canonical:
  answer: Skyrim and Fallout 4 expose Papyrus frame-budget settings such as `fUpdateBudgetMS`, so script backlog symptoms can be an engine scheduling issue rather than a single bad script.
  confidence: medium
queryKeys: [fUpdateBudgetMS, Papyrus budget, script throttling, frame budget, script lag]
severity: high
sources:
  - kind: wiki
    url: "https://ck.uesp.net/wiki/Main_Page"
    ref: Creation Kit Wiki UESP mirror
  - kind: wiki
    url: "https://en.uesp.net/wiki/Main_Page"
    ref: UESP main page
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# fUpdateBudgetMS-style settings throttle script work by frame budget

Creation Engine Papyrus does not run unlimited script work every frame.
Budget settings such as `fUpdateBudgetMS` define how much script update work the runtime attempts before yielding.

Increasing budgets can hide backlog symptoms but may trade against frame time and stability.
This record deliberately excludes Starfield because the equivalent CE2 scheduling surface was not verified for this A4 pass.
