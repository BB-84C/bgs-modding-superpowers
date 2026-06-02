---
id: load-order.official-masters-starfield.v1
title: Starfield official masters are runtime-derived and start from Starfield.esm
domains: [load-order]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Starfield's official layer starts from `Starfield.esm`, but update, DLC, and Creations-era official content can change the set that loads before user plugins.
  confidence: high
queryKeys: [Starfield official masters, Starfield.esm, Constellation.esm, Starfield load order]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Official / vanilla masters
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Home"
    ref: Starfield Wiki
related: [load-order.official-masters-derived-from-runtime.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield official masters are runtime-derived and start from Starfield.esm

For Starfield, `Starfield.esm` is the stable base anchor, but the official set is more update-sensitive than older fixed DLC stacks.
Bethesda-supplied content, DLC, and Creations-era files can appear in the early loaded layer depending on install state.

Agents should not project FO4 or Skyrim DLC naming patterns onto Starfield.
Read the runtime's earliest loaded files and treat those official masters as fixed before editing user-managed plugin order.
