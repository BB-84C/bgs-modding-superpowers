---
id: geck-scripting.reference-vs-base-object-data.v1
title: GECK references are placed instances, not the base object record
domains: [engine, plugin-format]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: A GECK reference is an instance of a base object placed or spawned in the world; editing base-object data affects all references, while reference data such as position is instance-local.
  confidence: high
queryKeys: [GECK reference, base object, placed reference, reference script]
severity: high
sources:
  - kind: wiki
    ref: GECK Wiki Reference
    url: https://geckwiki.com/index.php?title=Reference
    sectionPath: Overview
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# GECK references are placed instances, not the base object record

When a plugin edits a base object, every placed instance of that object can inherit the change.
When it edits a reference, the change is tied to that one placed or spawned instance.

This distinction matters for scripts and conflict audits: reference scripts, persistent references, and placed-object overrides are not interchangeable with edits to the underlying form definition.
