---
id: papyrus.gametime-registration-after-controls.v1
title: Game-time update registration is not available before full player controls
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: RegisterForUpdateGameTime schedules periodic game-time events, but Skyrim CK notes that game-time update registration is only possible after the player has full controls.
  confidence: verified-tooling
queryKeys: [RegisterForUpdateGameTime, player controls, Helgen, game-time update]
severity: medium
sources:
  - kind: wiki
    ref: Creation Kit Wiki RegisterForUpdateGameTime - Form
    url: https://ck.uesp.net/wiki/RegisterForUpdateGameTime_-_Form
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Game-time update registration is not available before full player controls

Game-time registration is a poor choice for very early startup logic.
The CK page documents that Skyrim cannot register game-time updates until the player has received full controls.

Use this when diagnosing scripts that work after a normal save but fail during a new-game intro or startup scene.
For early initialization, prefer an event or real-time path that is valid at that lifecycle point.

Verify the exact early-game gate per target game, especially outside Skyrim.
