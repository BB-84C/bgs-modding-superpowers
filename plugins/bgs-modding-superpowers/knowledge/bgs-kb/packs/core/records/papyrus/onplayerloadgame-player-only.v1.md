---
id: papyrus.onplayerloadgame-player-only.v1
title: OnPlayerLoadGame is sent to the player actor, not arbitrary scripts
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: OnPlayerLoadGame is a reload hook tied to the player actor path; scripts that need save-load refresh must be attached where that event is actually delivered.
  confidence: verified-tooling
queryKeys: [OnPlayerLoadGame, reload callback, player actor, save load event]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki OnPlayerLoadGame - Actor
    url: https://ck.uesp.net/wiki/OnPlayerLoadGame_-_Actor
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OnPlayerLoadGame is sent to the player actor, not arbitrary scripts

Use `OnPlayerLoadGame` when a Papyrus script truly needs to react after loading a save.
Do not assume every quest, alias, or form script receives it just because it compiled.

The CK page documents delivery on the player actor path and warns about first-load alias timing.
That makes attachment site part of the design, not a detail to debug later.

For Starfield, verify the current Creation Kit page or runtime before relying on identical delivery semantics.
