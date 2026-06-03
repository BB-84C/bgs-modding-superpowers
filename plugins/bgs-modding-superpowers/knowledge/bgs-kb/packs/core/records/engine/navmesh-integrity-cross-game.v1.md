---
id: engine.navmesh-integrity-cross-game.v1
title: Navmesh integrity is a cross-game engine constraint, but formats differ by game
domains: [engine, xedit, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
  engineFamilies: [gamebryo, creation-engine, creation-engine-2]
canonical:
  answer: Navmesh records control actor navigation and must remain internally coherent; each game has its own navmesh format and tooling assumptions, so cross-game fixes must be verified per target.
  confidence: high
queryKeys: [navmesh, NAVM, deleted navmesh, actor pathing, navigation mesh]
severity: critical
sources:
  - kind: tooling-docs
    url: "https://tes5edit.github.io/docs/"
    ref: Tome of xEdit
  - kind: wiki
    url: "https://ck.uesp.net/wiki/Main_Page"
    ref: Creation Kit Wiki UESP mirror
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Navmesh integrity is a cross-game engine constraint, but formats differ by game

Broken navmesh data can cause NPCs and creatures to fail pathing, ignore spaces, or behave as if reachable terrain does not exist.
That makes navmesh edits higher risk than ordinary object placement.

The concept spans Bethesda games, but the exact records and editor behavior differ by target.
Use game-aware CK/xEdit readback and avoid deleting or blindly overwriting navmesh records as a generic conflict fix.
