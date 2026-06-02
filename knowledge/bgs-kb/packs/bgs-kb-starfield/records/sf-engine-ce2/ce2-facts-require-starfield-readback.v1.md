---
id: sf-engine-ce2.ce2-facts-require-starfield-readback.v1
title: Starfield CE2 facts need Starfield-specific readback
domains: [engine, version-differences]
appliesTo:
  games: [Starfield]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV]
canonical:
  answer: Starfield is a Creation Engine 2 game with enough tooling differences that Skyrim and Fallout 4 assumptions should be treated as hypotheses until verified against Starfield sources or live readback.
  confidence: high
queryKeys: [Creation Engine 2, Starfield CE2, Starfield readback, CE1 assumptions]
severity: critical
sources:
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Home"
    ref: Starfield Wiki home
  - kind: project-internal-doc
    ref: knowledge/bgs-kb/packs/core/records/engine/creation-engine-2-starfield-caution.v1.md
    sectionPath: Core CE2 caution record
related: [engine.creation-engine-2-starfield-caution.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield CE2 facts need Starfield-specific readback

Starfield has its own wiki corpus, Creation surface, and xEdit game mode.
That is enough to make “it worked in Skyrim/FO4” a weak source for Starfield claims.

Use Starfield Wiki, Bethesda Creations, SFSE, xEdit Starfield mode, or live runtime readback for Starfield-specific assertions.
If a CE1 fact lacks Starfield evidence, leave it out of the Starfield pack.
