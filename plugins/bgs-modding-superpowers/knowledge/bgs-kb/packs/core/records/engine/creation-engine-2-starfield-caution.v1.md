---
id: engine.creation-engine-2-starfield-caution.v1
title: Starfield uses Creation Engine 2, so CE1 plugin assumptions need verification
domains: [engine, version-differences, plugin-format]
appliesTo:
  games: [Starfield]
  engineFamilies: [creation-engine-2]
canonical:
  answer: Starfield is a Creation Engine 2 target, so agents should verify record-format and tooling assumptions against Starfield-specific readback instead of projecting Skyrim or Fallout 4 behavior forward.
  confidence: high
queryKeys: [Creation Engine 2, Starfield engine, Starfield plugin format, CE2]
severity: high
sources:
  - kind: wiki
    url: "https://starfieldwiki.net/wiki/Home"
    ref: Starfield Wiki home
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Starfield uses Creation Engine 2, so CE1 plugin assumptions need verification

Starfield belongs in the Creation Engine 2 family, not the older Creation Engine bucket used by Skyrim and Fallout 4.
That matters when an agent is tempted to copy CE1 expectations about records, forms, archives, or scripting surfaces.

Use Starfield-aware tooling and live readback for claims about Starfield plugin behavior.
If a fact was only verified on Skyrim or Fallout 4, omit Starfield from scope until the CE2 variant is checked.
