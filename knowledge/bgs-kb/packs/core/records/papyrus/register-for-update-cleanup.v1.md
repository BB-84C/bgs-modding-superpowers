---
id: papyrus.register-for-update-cleanup.v1
title: RegisterForUpdate creates recurring callbacks that must be intentionally stopped
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: RegisterForUpdate creates recurring Papyrus OnUpdate callbacks, so scripts should unregister or switch to single-update registration when recurring work is no longer needed.
  confidence: high
queryKeys: [RegisterForUpdate, UnregisterForUpdate, recurring OnUpdate, Papyrus cleanup]
severity: high
sources:
  - kind: wiki
    url: https://ck.uesp.net/wiki/RegisterForUpdate_-_Form
    ref: Creation Kit Wiki RegisterForUpdate
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# RegisterForUpdate creates recurring callbacks that must be intentionally stopped

Recurring update registration is powerful, but it creates continuing work for the Papyrus VM.
If a script no longer needs that work, the registration should be cleaned up.

Agents should flag suspicious recurring updates in bug reports about script load, polling, or save bloat.
If the goal is a one-time delay, recommend the single-update form instead.

The practical question is whether the script has a clear stop condition for every recurring update it starts.
