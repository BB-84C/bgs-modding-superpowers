---
id: load-order.alternative-start-cascade-audit.v1
title: Alternative-start mods require a cascade audit of startup quest dependencies
kind: workflow
domains: [load-order, xedit, papyrus]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
canonical:
  answer: When a pack uses an alternative-start mod, audit every startup quest and script path that depends on vanilla main-quest triggers; compatibility patches should avoid making unrelated mods depend on the alternative-start plugin as a master.
  confidence: verified-project-doc
queryKeys: [alternative start, startup quest, main quest hook, quest injection, non-master injection]
severity: high
sources:
  - kind: project-internal-doc
    ref: BB84 Lane 3 audit synthesis
    sectionPath: alternative-start trigger recon
related: [load-order.cross-cutting-record-audit.v1]
lastReviewed: "2026-06-29"
schemaVersion: 1
---

# Alternative-start mods require a cascade audit of startup quest dependencies

Alternative-start mods can suspend, replace, or make optional the vanilla opening and main-quest progression. Any mod that expects a vanilla MQ stage, scene, alias fill, or Papyrus callback may never initialize along the alternative-start route.

Audit by listing startup `QUST` records, their conditions, scenes, aliases, script fragments, and Papyrus hooks such as stage-change listeners. Search for direct or indirect references to vanilla MQ FormIDs and early-game player-state assumptions.

For each affected mod, design an early injection path that preserves independence: vanilla quest indirect hooks, player keywords, globals, startup watcher quests, or script-extender events are preferred. Do not make downstream mods list the alternative-start plugin as a master unless the curator explicitly accepts that hard dependency.

Reference case: Starfield alternative-start stacks such as `adwryos` can affect mods whose startup logic assumes vanilla MQ progression; the patch design should not make those mods hard-require the alternative-start mod.
