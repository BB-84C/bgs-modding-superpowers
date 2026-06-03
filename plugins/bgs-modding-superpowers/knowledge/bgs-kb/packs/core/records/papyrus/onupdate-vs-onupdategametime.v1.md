---
id: papyrus.onupdate-vs-onupdategametime.v1
title: OnUpdate uses real-time intervals; OnUpdateGameTime uses game-time intervals
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: OnUpdate and OnUpdateGameTime are separate Papyrus event families; choose real-time updates for wall-clock polling and game-time updates for in-world elapsed time.
  confidence: verified-tooling
queryKeys: [OnUpdate, OnUpdateGameTime, RegisterForUpdateGameTime, real time, game time]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki OnUpdate - Form
    url: https://ck.uesp.net/wiki/OnUpdate_-_Form
    sectionPath: Notes
  - kind: wiki
    ref: Creation Kit Wiki OnUpdateGameTime - Form
    url: https://ck.uesp.net/wiki/OnUpdateGameTime_-_Form
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OnUpdate uses real-time intervals; OnUpdateGameTime uses game-time intervals

`OnUpdate` fires from real-time update registration.
`OnUpdateGameTime` fires from game-time update registration.

Both pages note that menu mode matters and that quests, aliases, and active magic effects have cleanup behavior tied to their lifetime.
The wrong family creates bugs that look like lag, skipped timers, or timers advancing on the wrong clock.

Pick the clock first, then pick the registration function.
