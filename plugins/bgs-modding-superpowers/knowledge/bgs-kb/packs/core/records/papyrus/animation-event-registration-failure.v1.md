---
id: papyrus.animation-event-registration-failure.v1
title: RegisterForAnimationEvent can fail when the animation graph is not ready
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR]
  engineFamilies: [creation-engine]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: RegisterForAnimationEvent returns a bool; CK notes that false can mean the animation graph is not loaded yet, so scripts must handle registration failure.
  confidence: verified-tooling
queryKeys: [RegisterForAnimationEvent, AnimationEvent, graph not loaded, animation event]
severity: medium
sources:
  - kind: wiki
    ref: Creation Kit Wiki RegisterForAnimationEvent - Form
    url: https://ck.uesp.net/wiki/RegisterForAnimationEvent_-_Form
    sectionPath: Return Value
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# RegisterForAnimationEvent can fail when the animation graph is not ready

Animation-event registration is not guaranteed to succeed.
The CK page documents a boolean return and names an unloaded animation graph as a reason for failure.

Always branch on the return value and either retry later or degrade cleanly.
Do not assume missing animation callbacks mean the event name is wrong until registration success is proven.

Starfield animation-event behavior was not verified for this record.
