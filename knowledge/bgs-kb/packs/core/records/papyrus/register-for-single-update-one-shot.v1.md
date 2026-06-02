---
id: papyrus.register-for-single-update-one-shot.v1
title: RegisterForSingleUpdate schedules one OnUpdate callback
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: RegisterForSingleUpdate schedules a one-shot Papyrus OnUpdate event, making it safer for delayed work than persistent recurring update registration when only one callback is needed.
  confidence: high
queryKeys: [RegisterForSingleUpdate, OnUpdate, one-shot update, delayed Papyrus work]
severity: medium
sources:
  - kind: wiki
    url: https://ck.uesp.net/wiki/RegisterForSingleUpdate_-_Form
    ref: Creation Kit Wiki RegisterForSingleUpdate
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# RegisterForSingleUpdate schedules one OnUpdate callback

Use a single-update registration when a script needs one delayed callback rather than a standing heartbeat.
That keeps the script from accumulating recurring work it does not need.

Agents diagnosing delayed Papyrus behavior should ask whether the code needs one callback or repeated callbacks.
For a one-shot delay, prefer the single-update pattern and re-register only when another callback is required.

This is Papyrus guidance and should not be applied to GECK scripting in Fallout 3 or Fallout New Vegas.
