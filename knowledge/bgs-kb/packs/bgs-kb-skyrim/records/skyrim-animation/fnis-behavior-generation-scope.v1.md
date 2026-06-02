---
id: skyrim-animation.fnis-behavior-generation-scope.v1
title: FNIS generates Skyrim behavior support for custom animations
domains: [engine, install-planning]
appliesTo:
  games: [SkyrimLE, SkyrimSE]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "FNIS is a Skyrim behavior-generation tool for custom animation classes such as idles, poses, paired animations, killmoves, creatures, and furniture animations."
  confidence: high
queryKeys: [FNIS, Fores New Idles, behavior generation, custom animations]
severity: high
sources:
  - kind: community-forum
    ref: Nexus Mods Fores New Idles in Skyrim - FNIS
    url: https://www.nexusmods.com/skyrim/mods/11811
    sectionPath: About this mod
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# FNIS generates Skyrim behavior support for custom animations

FNIS exists because Skyrim behavior files need generated support for many custom animation types.
The Nexus page lists idles, poses, sequenced animations, furniture, paired animations, killmoves, creatures, and other categories.

Treat FNIS as a generator step, not as a passive asset mod.
If generated behavior output is stale or missing, the animation mod may be installed but still not active in-game.

Use the generator expected by the animation framework in the modlist.
