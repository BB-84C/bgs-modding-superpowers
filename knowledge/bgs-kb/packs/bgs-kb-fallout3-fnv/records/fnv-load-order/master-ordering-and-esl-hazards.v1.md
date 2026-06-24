---
id: fnv-load-order.master-ordering-and-esl-hazards.v1
title: Fallout 3 and New Vegas have no ESL system; master order still matters
kind: rule
domains: [load-order, plugin-format]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Fallout 3, Fallout: New Vegas, and TTW do not support ESL/light-plugin mechanics; preserve strict master ordering and never import modern ESL advice into these legacy load orders."
  confidence: high
queryKeys: [FNV ESL, Fallout 3 ESL, TTW master order, missing master, master cycle, light plugin]
severity: critical
sources:
  - kind: community-forum
    ref: Viva New Vegas guide
    url: https://vivanewvegas.moddinglinked.com/
    sectionPath: Requirements and setup
  - kind: community-forum
    ref: Tale of Two Wastelands site
    url: https://taleoftwowastelands.com/
    sectionPath: Installation and load order
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Fallout 3 and New Vegas have no ESL system; master order still matters

Fallout 3, Fallout: New Vegas, and TTW have no ESL/light-plugin system. There is no ESL flagging, compacted light FormID range, medium-plugin tier, or safe way to borrow Skyrim SE/Fallout 4 advice about turning small ESPs into ESLs. Any guide, tool output, or forum answer that talks about ESL conversion must be treated as belonging to a later Creation Engine game unless it explicitly says otherwise.

The hard rule for these games is master correctness. A plugin's masters must load before it. Missing masters can block startup or make xEdit show unresolved references. Master cycles are invalid design: if plugin A requires plugin B and plugin B requires plugin A, the load order cannot be made coherent without changing one plugin's dependencies or splitting patches. Do not "fix" this by random reordering; inspect the header and patch structure.

TTW adds a strict dual-game constraint. It is not a loose pile of Fallout 3 assets inside New Vegas; it is a curated conversion stack with an expected master sequence. Preserve the TTW guide's ordering for Fallout 3, New Vegas, DLC, and TTW masters before placing optional mods. Fallout 3 mods normally need TTW-aware conversion before they belong in that runtime. If a mod says it is for raw Fallout 3, assume it is not TTW-safe until the author or a compatibility patch says so.
