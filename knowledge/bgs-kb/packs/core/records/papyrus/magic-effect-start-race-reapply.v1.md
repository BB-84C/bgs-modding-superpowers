---
id: papyrus.magic-effect-start-race-reapply.v1
title: OnEffectStart can fire again when race changes reapply ability effects
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: OnEffectStart runs when an active magic effect starts, and CK notes that ability effects may be reapplied when an actor's race changes.
  confidence: verified-tooling
queryKeys: [OnEffectStart, ActiveMagicEffect, race change, ability effect, magic effect lifecycle]
severity: medium
sources:
  - kind: wiki
    ref: Creation Kit Wiki OnEffectStart - ActiveMagicEffect
    url: https://ck.uesp.net/wiki/OnEffectStart_-_ActiveMagicEffect
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OnEffectStart can fire again when race changes reapply ability effects

Treat `OnEffectStart` as an active-effect lifecycle callback, not a guaranteed once-ever initializer.
The CK page notes that changing an actor's race can reapply ability effects and call the event again.

Scripts attached to ability effects should be idempotent or explicitly guard one-time work.
Otherwise race changes, transformations, or similar rebuilds can duplicate setup.

Starfield-specific magic-effect semantics were not verified for this record, so Starfield is not in scope here.
