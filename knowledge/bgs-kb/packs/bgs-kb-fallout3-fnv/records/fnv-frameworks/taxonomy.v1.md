---
id: fnv-frameworks.taxonomy.v1
title: Framework taxonomy for Fallout 3, New Vegas, and TTW
kind: explanation
domains: [engine, install-planning]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Treat Fallout 3 and New Vegas frameworks as a layered runtime stack: extender first, native extender plugins next, UI/runtime frameworks after that, and TTW only as a New Vegas-runtime conversion layer."
  confidence: high
queryKeys: [FNV frameworks, NVSE, JIP LN NVSE, JohnnyGuitar, yUI, lStewieAl, FNV4GB, FOSE, TTW]
severity: high
sources:
  - kind: community-forum
    ref: JIP LN NVSE Plugin Nexus page
    url: https://www.nexusmods.com/newvegas/mods/58277
    sectionPath: Requirements and description
  - kind: community-forum
    ref: lStewieAl's Tweaks Nexus page
    url: https://www.nexusmods.com/newvegas/mods/66347
    sectionPath: About this mod
  - kind: community-forum
    ref: Tale of Two Wastelands site
    url: https://taleoftwowastelands.com/
    sectionPath: Requirements
  - kind: project-internal-doc
    ref: BB84 corpus FNV framework adoption note
lastReviewed: "2026-06-24"
schemaVersion: 1
---

# Framework taxonomy for Fallout 3, New Vegas, and TTW

## Perspective: OBJECTIVE

New Vegas frameworks are layered. The executable/memory baseline comes first: 4GB-aware launch plus xNVSE. Native extender plugins then expand the runtime: JIP LN NVSE, JohnnyGuitar NVSE, ShowOff-style add-ons, and lStewieAl's Tweaks are common examples. UI and menu layers such as yUI sit above that. TTW is not a universal framework for every FO3 mod; it is a conversion/runtime stack that brings Fallout 3 content into New Vegas and imposes its own version and master-order expectations.

Framework traps are objective: abandoned native plugins, hardcoded game versions, no changelog, dependencies that no longer load, and frameworks that claim broad compatibility while replacing the same menus, scripts, or DLL hooks as another framework. Fallout 3 has a different baseline: remove GFWL assumptions, use FOSE only where the mod requires it, and do not expect New Vegas NVSE plugins to load in raw Fallout 3.

## Perspective: SUBJECTIVE — BB84 curator reference (not a universal rubric)

BB84's reference FNV stack prioritizes xNVSE, JIP LN NVSE, JohnnyGuitar NVSE, lStewieAl's Tweaks, yUI, FNV4GB, and TTW where the pack is intentionally TTW-shaped. The subjective lesson is not "install exactly these forever." It is to keep frameworks boring, maintained, and layered so content mods can rely on them without turning the foundation into the experiment.
