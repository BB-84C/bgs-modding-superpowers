---
id: papyrus.update-events-relay-to-same-object-scripts.v1
title: Update events can be received by other scripts on the same object
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: CK notes for OnUpdate warn that update events registered by one script can be relayed to other scripts attached to the same object, so registrations should be isolated and handlers guarded.
  confidence: verified-tooling
queryKeys: [OnUpdate relay, same object scripts, update registration, multiple scripts]
severity: high
sources:
  - kind: wiki
    ref: Creation Kit Wiki OnUpdate - Form
    url: https://ck.uesp.net/wiki/OnUpdate_-_Form
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Update events can be received by other scripts on the same object

An update registration is not always as isolated as the registering function suggests.
CK notes say an update event can be relayed to other scripts attached to the same object.

That means handlers should check whether the current script actually owns the polling work.
On quest forms with multiple scripts, unguarded `OnUpdate` bodies can accidentally run together.

When debugging duplicate polling, inspect every script attached to the same object.
