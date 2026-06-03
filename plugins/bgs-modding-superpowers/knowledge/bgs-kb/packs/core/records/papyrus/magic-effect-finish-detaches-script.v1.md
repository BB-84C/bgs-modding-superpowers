---
id: papyrus.magic-effect-finish-detaches-script.v1
title: OnEffectFinish runs when the active effect is already ending
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: OnEffectFinish is a teardown callback; CK warns that the underlying active effect may already be deleted or detached, so native calls and saved state assumptions are risky.
  confidence: verified-tooling
queryKeys: [OnEffectFinish, ActiveMagicEffect, effect teardown, detached script]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki OnEffectFinish - ActiveMagicEffect
    url: https://ck.uesp.net/wiki/OnEffectFinish_-_ActiveMagicEffect
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OnEffectFinish runs when the active effect is already ending

Use `OnEffectFinish` for cleanup, not for starting new effect-dependent work.
The CK page warns that by the time this event runs, the underlying active magic effect may be deleted or the script object may be detaching.

Native calls can fail at this point.
Persist important state before teardown when possible, or guard every call.

Starfield-specific active-effect teardown behavior was not verified for this record.
