---
id: papyrus.utility-waitgametime-clock-jumps.v1
title: Utility.WaitGameTime follows game time and can stretch across clock jumps
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Utility.WaitGameTime waits in game hours, and CK notes that total wait time can be longer when the game clock jumps ahead, such as during fast travel.
  confidence: verified-tooling
queryKeys: [Utility.WaitGameTime, game time wait, fast travel, clock jump]
severity: medium
sources:
  - kind: wiki
    ref: Creation Kit Wiki WaitGameTime - Utility
    url: https://ck.uesp.net/wiki/WaitGameTime_-_Utility
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Utility.WaitGameTime follows game time and can stretch across clock jumps

`Utility.WaitGameTime` is for in-world elapsed hours, not real seconds.
It is latent and returns after at least the requested amount of game time.

CK notes that large clock jumps can make the total wait longer than expected.
Fast travel is the classic example of a player action that changes the timing shape.

Do not use game-time waits for real-time UI or combat timing assumptions.
