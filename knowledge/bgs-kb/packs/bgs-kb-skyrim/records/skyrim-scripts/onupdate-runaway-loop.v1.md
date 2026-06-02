---
id: skyrim-scripts.onupdate-runaway-loop.v1
title: Skyrim OnUpdate polling needs a stop condition
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: "Skyrim OnUpdate loops are safe only when the script has a clear unregister or re-register policy; runaway polling accumulates VM work and looks like script lag."
  confidence: verified-tooling
queryKeys: [OnUpdate loop, RegisterForUpdate, UnregisterForUpdate, script lag]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki OnUpdate - Form
    url: https://ck.uesp.net/wiki/OnUpdate_-_Form
    sectionPath: Example; Notes
related: [papyrus.register-for-update-cleanup.v1, papyrus.update-events-relay-to-same-object-scripts.v1]
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Skyrim OnUpdate polling needs a stop condition

Skyrim mods often use `OnUpdate` as a polling loop.
That pattern is acceptable only when the script knows when to stop or when to re-register once.

The CK example unregisters when the condition is satisfied.
If a script never unregisters, it can keep creating Papyrus work long after the gameplay condition ended.

Audit recurring updates during script-lag and save-bloat investigations.
