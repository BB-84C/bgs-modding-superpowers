---
id: tooling.new-vegas-body-replacers-are-asset-ecosystems.v1
title: New Vegas body replacers are asset ecosystems with mesh/animation compatibility consequences
domains: [file-conflicts, install-planning]
appliesTo:
  games: [FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: New Vegas body replacer families such as Type 3, Type 6-derived bodies, and BBB-style animation bodies are asset ecosystems; mixing armor, skeleton, and animation assumptions across them can produce visual or equipment conflicts.
  confidence: medium
queryKeys: [Type3, Type 6, T6M, BBB, Bouncing Natural Breasts, body replacer, armor replacer]
severity: medium
sources:
  - kind: community-forum
    ref: Type3 Body and Armor replacer Nexus page
    url: https://www.nexusmods.com/newvegas/mods/34825
    sectionPath: Page metadata
  - kind: community-forum
    ref: Type 6 Modification Body NV Nexus page
    url: https://www.nexusmods.com/newvegas/mods/45162
    sectionPath: Page metadata
  - kind: community-forum
    ref: Bouncing Natural Breasts Nexus page
    url: https://www.nexusmods.com/newvegas/mods/35047
    sectionPath: Page metadata
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# New Vegas body replacers are asset ecosystems with mesh/animation compatibility consequences

The New Vegas body-replacer space contains distinct mesh and armor families rather than one universal body standard.
Type 3, Type 6-derived, and BBB-style pages describe different body/armor/animation assumptions.

For modpack curation, keep body meshes, armor conversions, skeletons, and animation support aligned.
If a visual bug appears only on equipped armor, treat it as an asset-stack compatibility problem before editing gameplay records.
