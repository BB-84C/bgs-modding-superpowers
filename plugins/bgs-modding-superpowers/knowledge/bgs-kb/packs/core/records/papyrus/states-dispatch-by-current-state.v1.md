---
id: papyrus.states-dispatch-by-current-state.v1
title: Papyrus states choose which event or function body runs
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Papyrus scripts can be in only one state at a time, and the current state controls which state-bound function or event implementation runs.
  confidence: verified-tooling
queryKeys: [Papyrus states, state-bound events, empty state, auto state, GotoState]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki States (Papyrus)
    url: https://ck.uesp.net/wiki/States_(Papyrus)
    sectionPath: Overview; How Functions Are Picked
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Papyrus states choose which event or function body runs

Papyrus state blocks are dispatch logic, not comments.
The script has one current state, and calls/events resolve against that state before falling back to the empty state.

This is a common source of bugs where a function exists but the active state routes to a different body or no body.
When behavior changes after `GotoState`, inspect the active state before blaming load order.

Keep default-state behavior explicit when state transitions are part of the design.
