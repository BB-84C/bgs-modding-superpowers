---
id: papyrus.base-form-vs-reference-script-scope.v1
title: Base-form scripts and reference scripts have different runtime scope
domains: [papyrus, engine, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: A script attached to a base form and a script attached to a placed reference are not the same runtime scope; agents must identify which object owns the script instance before diagnosing lifecycle behavior.
  confidence: high
queryKeys: [base form script, reference script, ObjectReference, Papyrus lifecycle]
severity: medium
sources:
  - kind: wiki
    url: https://ck.uesp.net/wiki/ObjectReference_Script
    ref: Creation Kit Wiki ObjectReference Script
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Base-form scripts and reference scripts have different runtime scope

Papyrus script behavior depends on what object owns the script instance.
A base object, an placed reference, a quest, and an alias can have different lifecycle and persistence implications.

Before diagnosing an event that did or did not fire, identify the attachment site.
Looking only at the script source can hide the runtime owner that controls when the instance exists.

This record is for Papyrus-using games only; FO3/FNV GECK scripts use a different model.
