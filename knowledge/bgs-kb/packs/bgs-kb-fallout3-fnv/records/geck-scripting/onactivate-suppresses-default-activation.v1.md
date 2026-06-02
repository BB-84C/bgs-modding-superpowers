---
id: geck-scripting.onactivate-suppresses-default-activation.v1
title: OnActivate object scripts can suppress default activation
domains: [engine, debugging]
appliesTo:
  games: [Fallout3, FalloutNV]
  engineFamilies: [gamebryo]
  excludes: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Starfield]
canonical:
  answer: A GECK object script using OnActivate can intercept normal activation; call Activate when the default behavior should still occur.
  confidence: high
queryKeys: [OnActivate, Activate, default activation, action ref, GetActionRef]
severity: high
sources:
  - kind: wiki
    ref: GECK Wiki OnActivate
    url: https://geckwiki.com/index.php?title=OnActivate
    sectionPath: Notes
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# OnActivate object scripts can suppress default activation

`OnActivate` is a common source of false bug reports because adding the block can change the activation path itself.
If the mod still wants the original door/container/book behavior, the script must explicitly hand control back with `Activate` when appropriate.

For conditional activator logic, collect activation context inside the activation block rather than later blocks where the action reference may no longer be meaningful.
