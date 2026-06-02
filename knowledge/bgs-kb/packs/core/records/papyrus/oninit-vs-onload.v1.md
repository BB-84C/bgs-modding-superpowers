---
id: papyrus.oninit-vs-onload.v1
title: OnInit fires once per script init; use OnGameReload for reload detection
domains: [papyrus, version-differences]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Papyrus OnInit is an initialization event, not a general save-load callback; use reload-aware events or update registration patterns when a script must respond after loading a game.
  confidence: high
queryKeys: [OnInit, OnGameReload, reload detection, Papyrus load event]
severity: medium
sources:
  - kind: wiki
    url: https://ck.uesp.net/wiki/OnInit
    ref: Creation Kit Wiki OnInit
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OnInit fires once per script init; use OnGameReload for reload detection

`OnInit` is for script initialization, so it is the wrong mental model for ordinary save reload detection.
Papyrus code that needs to refresh state after a load should use reload-aware events where available or register updates intentionally.

This is a Papyrus record and therefore excludes Fallout 3 and Fallout New Vegas, whose scripting substrate is different.
Agents should not offer this as advice for GECK-era games.

When diagnosing a reload bug, ask whether the script is waiting on initialization when it really needs a load or update path.
