---
id: load-order.official-masters-fallout4.v1
title: Fallout 4 official masters include Fallout4.esm plus installed official DLC masters
domains: [load-order]
appliesTo:
  games: [Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
canonical:
  answer: Fallout 4 starts from `Fallout4.esm` and then loads installed official DLC or verified content before user-managed plugins; the exact visible set should be read from the runtime.
  confidence: high
queryKeys: [Fallout 4 official masters, Fallout4.esm, DLCRobot.esm, DLCCoast.esm, DLCNukaWorld.esm]
severity: high
sources:
  - kind: project-skill
    ref: skills/writing-bgs-load-order/SKILL.md
    sectionPath: Official / vanilla masters
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4"
    ref: Independent Fallout Wiki Fallout 4
related: [load-order.official-masters-derived-from-runtime.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 official masters include Fallout4.esm plus installed official DLC masters

For Fallout 4, `Fallout4.esm` is the base official-master anchor.
Common official DLC masters include Automatron, Far Harbor, Nuka-World, and the Workshop DLC files, but next-gen and Creation content can change what the runtime exposes.

Treat those official files as a pre-user layer that the engine and tooling inject before the agent-authored plugin list.
If a generated load order needs to be self-describing, record the inferred official set, but do not reorder those files like normal user mods.
