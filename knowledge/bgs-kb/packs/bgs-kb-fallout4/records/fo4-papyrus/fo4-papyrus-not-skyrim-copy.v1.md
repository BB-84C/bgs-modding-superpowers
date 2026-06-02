---
id: fo4-papyrus.fo4-papyrus-not-skyrim-copy.v1
title: Fallout 4 Papyrus is close to Skyrim Papyrus but not a copy-paste target
domains: [papyrus, engine, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Fallout 4 Papyrus shares many Creation Engine concepts with Skyrim, but scripts, base classes, game APIs, and extender functions must be verified against FO4 documentation and runtime.
  confidence: medium
queryKeys: [Fallout 4 Papyrus, Skyrim Papyrus difference, FO4 script]
severity: high
sources:
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
  - kind: official
    url: "https://f4se.silverlock.org/"
    ref: F4SE home
related: [papyrus.properties-are-save-state.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Fallout 4 Papyrus is close to Skyrim Papyrus but not a copy-paste target

The syntax family is familiar, but the game surface is different.
FO4 scripts may involve different native classes, quests, events, and extender APIs than Skyrim scripts.

When porting a Papyrus fix, verify the function and base type in FO4 context.
Do not assume a Skyrim CK page proves a Fallout 4 script behavior.
