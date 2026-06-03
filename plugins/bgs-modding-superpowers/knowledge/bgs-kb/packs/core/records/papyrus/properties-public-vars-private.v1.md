---
id: papyrus.properties-public-vars-private.v1
title: Papyrus properties expose script data; variables stay private
domains: [papyrus, debugging]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
  engineFamilies: [creation-engine, creation-engine-2]
  excludes: [Fallout3, FalloutNV]
canonical:
  answer: Papyrus variables are private to their script, while properties are the access surface other scripts and the editor can use to get or set script data.
  confidence: verified-tooling
queryKeys: [Papyrus property, variable private, auto property, script data]
severity: medium
sources:
  - kind: wiki
    ref: Creation Kit Wiki Variables and Properties
    url: https://ck.uesp.net/wiki/Variables_and_Properties
    sectionPath: Description
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Papyrus properties expose script data; variables stay private

Use a variable when data belongs only to the current script.
Use a property when other scripts or editor-filled data need access.

This distinction matters during mod updates because exposed properties often become part of the authored interface.
Hard-coding a FormID in source is usually less maintainable than a properly filled property.

When reviewing a script, ask whether each external dependency is intentionally exposed or accidentally hidden.
