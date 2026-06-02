---
id: fo4-settlement.settler-ai-needs-navmesh-and-reachable-work.v1
title: Settler AI needs reachable navmesh and sane workshop assignments
domains: [engine, debugging]
appliesTo:
  games: [Fallout4]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: Settlers can fail assignments when beds, jobs, routes, or placed objects are unreachable, so settlement AI bugs are often navmesh and layout problems rather than actor-record conflicts.
  confidence: high
queryKeys: [settler pathing, settlement AI, unreachable bed, workshop assignment]
severity: high
sources:
  - kind: wiki
    url: "https://fallout.wiki/wiki/Fallout_4_settlements"
    ref: Fallout Wiki Fallout 4 settlements
related: [engine.navmesh-integrity-cross-game.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Settler AI needs reachable navmesh and sane workshop assignments

Settlements combine actor AI, workshop ownership, and player-built geometry.
If a settler will not reach food, guard posts, beds, or shops, the problem may be physical reachability.

Check navmesh, object placement, stair access, and assignment state before changing load order.
Player-built clutter can create pathing failures even when every plugin record looks valid.
